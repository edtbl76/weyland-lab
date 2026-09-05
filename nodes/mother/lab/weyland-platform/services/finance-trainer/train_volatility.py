"""Remote finance volatility trainer → weyland MLflow (B113 Phase 5).

The finance analogue of genre-trainer: reads the Feast-retrieved training set from lakeFS
(`finance/parquet/price_feast_training/` — produced IN-CLUSTER + MESHED by the Dagster
`price_feast_training_set` asset, because Feast's offline store is STRICT-mTLS Postgres, unreachable from this
external trainer) and fits BOTH shapes of the volatility model over the SAME table:

  * regress  — RandomForestRegressor on `fwd_vol_5d` (next-5-day realized vol). Metrics RMSE + R².
               Registered as `price_volatility_regressor`.
  * classify — RandomForestClassifier on the vol REGIME (fwd_vol_5d above/below THIS ticker's median →
               HIGH/LOW). Metrics accuracy + F1. Registered as `price_volatility_classifier`.
  * both     — default: fit + register both.

Modes per task:
  * default (single fit) — one model, one MLflow run, registered.
  * --tune (Ray Tune)    — a hyperparameter sweep on a Ray cluster; every trial is its own MLflow run, and the
                           BEST config is retrained + registered.

Same infra contract as genre-trainer: artifacts go DIRECT to MinIO (`s3://mlflow/…`, bypassing the
serve-artifacts proxy); config comes from env (LAKEFS_*, MLFLOW_TRACKING_URI, MLFLOW_S3_ENDPOINT_URL, AWS_*);
`entrypoint.sh` opens the port-forwards. Nothing secret on the CLI.
"""
import argparse
import os
import sys
import time

import mlflow
import mlflow.sklearn
import pandas as pd
from minio import Minio
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split

FEATURES = ["ret_1d", "ret_5d", "ret_20d", "vol_5d", "vol_10d", "vol_20d",
            "volume_ratio", "range_20d", "sma_ratio_20d"]
TARGET = "fwd_vol_5d"
_REPO = "finance"
_DATASET = "price_feast_training"


def log(msg):
    print(f"[train_volatility] {msg}", flush=True)


def _envflag(name):
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _lakefs_client() -> Minio:
    ep = os.environ.get("LAKEFS_ENDPOINT", "http://localhost:8000")
    return Minio(ep.replace("https://", "").replace("http://", ""),
                 access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
                 secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
                 secure=ep.startswith("https://"))


def _read_training() -> pd.DataFrame:
    """The Feast point-in-time training set landed by the Dagster `price_feast_training_set` asset."""
    import tempfile
    branch = os.environ.get("LAKEFS_BRANCH", "main")
    mc = _lakefs_client()
    log(f"reading Feast training set from lakeFS ({branch}/parquet/{_DATASET}/)…")
    frames = []
    for obj in mc.list_objects(_REPO, prefix=f"{branch}/parquet/{_DATASET}/", recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        t = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        t.close()
        try:
            mc.fget_object(_REPO, obj.object_name, t.name)
            frames.append(pd.read_parquet(t.name))
        finally:
            os.unlink(t.name)
    if not frames:
        sys.exit(f"no training set in lakeFS ({_REPO}/{branch}/parquet/{_DATASET}/). Materialize the Dagster "
                 "`price_feast_training_set` asset first (it runs the meshed get_historical_features retrieval).")
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    for c in FEATURES + [TARGET]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=FEATURES + [TARGET, "ticker"])
    log(f"training set: {len(df):,} rows / {df['ticker'].nunique()} tickers")
    return df


def regime_label(df: pd.DataFrame) -> pd.Series:
    """HIGH(1)/LOW(0) next-5d vol regime, split at EACH ticker's own median fwd_vol_5d — so the classifier learns
    a per-name regime (vol clustering), not merely 'which ticker is a high-vol name'."""
    med = df.groupby("ticker")[TARGET].transform("median")
    return (df[TARGET] > med).astype(int)


# --- mlflow ------------------------------------------------------------------------------------------------

def ensure_experiment(client: MlflowClient, name: str) -> None:
    """Artifacts DIRECT to MinIO (s3://), not the serve-artifacts proxy (which times out on a big model)."""
    loc = os.environ.get("MLFLOW_ARTIFACT_LOCATION", f"s3://mlflow/{name}")
    exp = client.get_experiment_by_name(name)
    if exp is None:
        client.create_experiment(name, artifact_location=loc)
        log(f"created experiment {name!r} → artifacts at {loc}")
    elif not exp.artifact_location.startswith("s3://"):
        sys.exit(f"experiment {name!r} exists with a PROXY artifact_location ({exp.artifact_location!r}). Purge "
                 "it (mlflow gc) so it's recreated with a direct s3:// location.")
    else:
        log(f"experiment {name!r} → artifacts at {exp.artifact_location}")


def _register(model, params, metrics, run_name, registered_model):
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({"n_features": len(FEATURES), **params})
        mlflow.log_metrics(metrics)
        t0 = time.time()
        mlflow.sklearn.log_model(model, "model", registered_model_name=registered_model)
        log(f"model registered as {registered_model!r} in {time.time() - t0:.1f}s — "
            + " ".join(f"{k}={v:.4f}" for k, v in metrics.items()))


# --- fits ----------------------------------------------------------------------------------------------------

def _split(df):
    return df[FEATURES].to_numpy(), df[TARGET].to_numpy(), regime_label(df).to_numpy()


def _fit_regressor(df, args):
    X, y, _ = _split(df)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    log(f"[regress] RandomForestRegressor ({args.n_estimators} trees, depth {args.max_depth}) on {len(Xtr):,} rows…")
    m = RandomForestRegressor(n_estimators=args.n_estimators, max_depth=args.max_depth,
                              random_state=42, n_jobs=-1).fit(Xtr, ytr)
    pred = m.predict(Xte)
    rmse, r2 = float(root_mean_squared_error(yte, pred)), float(r2_score(yte, pred))
    log(f"[regress] rmse={rmse:.5f} r2={r2:.4f}")
    _register(m, {"model": "RandomForestRegressor", "task": "regress", "mode": "single",
                  "n_estimators": args.n_estimators, "max_depth": args.max_depth, "n_rows": len(df)},
              {"rmse": rmse, "r2": r2}, "vol-regressor", f"{args.registered_model}_regressor")


def _fit_classifier(df, args):
    X, _, y = _split(df)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    log(f"[classify] RandomForestClassifier ({args.n_estimators} trees, depth {args.max_depth}) on {len(Xtr):,} rows…")
    m = RandomForestClassifier(n_estimators=args.n_estimators, max_depth=args.max_depth,
                               random_state=42, n_jobs=-1).fit(Xtr, ytr)
    pred = m.predict(Xte)
    acc, f1 = float(accuracy_score(yte, pred)), float(f1_score(yte, pred))
    log(f"[classify] accuracy={acc:.4f} f1={f1:.4f}")
    _register(m, {"model": "RandomForestClassifier", "task": "classify-vol-regime", "mode": "single",
                  "n_estimators": args.n_estimators, "max_depth": args.max_depth, "n_rows": len(df)},
              {"accuracy": acc, "f1": f1}, "vol-classifier", f"{args.registered_model}_classifier")


# --- ray tune ------------------------------------------------------------------------------------------------

def _tune(df, args, task):
    """Ray Tune sweep for one task ('regress'|'classify'). Each trial logs its own MLflow run; the best config is
    retrained on the driver + registered. Mirrors genre-trainer's worker-env shipping (external workers have
    neither MLflow nor MinIO creds in their own env)."""
    import ray
    from ray import train, tune

    X, yr, yc = _split(df)
    y = yr if task == "regress" else yc
    strat = None if task == "regress" else y
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=strat)
    if os.environ.get("RAY_ADDRESS"):
        ray.init(address="auto")
    else:
        # nosec B104 — the LOCAL Ray dashboard binds 0.0.0.0 INSIDE the container; the ephemeral run publishes it
        # loopback-only (`-p 127.0.0.1:8265:8265`, never the host's 0.0.0.0), same accepted pattern as genre-trainer.
        ray.init(include_dashboard=True, dashboard_host="0.0.0.0", ignore_reinit_error=True)  # nosec B104
    log(f"[tune:{task}] Ray up — {int(ray.cluster_resources().get('CPU', 0))} CPUs, {args.trials} trials…")
    data_ref = ray.put((Xtr, Xte, ytr, yte))
    experiment = args.experiment
    wenv = {k: os.environ[k] for k in ("MLFLOW_TRACKING_URI", "MLFLOW_S3_ENDPOINT_URL",
                                       "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
    wenv["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    metric = "r2" if task == "regress" else "f1"
    _pk = ("n_estimators", "max_depth", "max_features", "min_samples_leaf")

    def trainable(config):
        import os as o
        import mlflow as m
        import ray as r
        from sklearn.ensemble import RandomForestClassifier as RFC, RandomForestRegressor as RFR
        from sklearn.metrics import accuracy_score as a_s, f1_score as f_s, r2_score as r_s, root_mean_squared_error as rm_s
        o.environ.update(wenv)
        a_tr, a_te, y_tr, y_te = r.get(data_ref)
        Model = RFR if task == "regress" else RFC
        mdl = Model(random_state=42, n_jobs=4, **{k: config[k] for k in _pk}).fit(a_tr, y_tr)
        pred = mdl.predict(a_te)
        if task == "regress":
            mets = {"rmse": float(rm_s(y_te, pred)), "r2": float(r_s(y_te, pred))}
        else:
            mets = {"accuracy": float(a_s(y_te, pred)), "f1": float(f_s(y_te, pred))}
        try:
            m.set_tracking_uri(wenv["MLFLOW_TRACKING_URI"])
            m.set_experiment(experiment)
            with m.start_run(run_name=f"tune-{task}"):
                m.log_params({**{k: config[k] for k in _pk}, "task": task, "mode": "ray-tune"})
                m.log_metrics(mets)
        except Exception as e:  # noqa: BLE001
            print(f"[trainable] mlflow log skipped: {e}", flush=True)
        train.report(mets)

    space = {
        "n_estimators": tune.choice([100, 200]),
        "max_depth": tune.choice([8, 12, 16]),
        "max_features": tune.choice(["sqrt", "log2"]),
        "min_samples_leaf": tune.choice([1, 2, 4]),
    }
    tuner = tune.Tuner(tune.with_resources(trainable, {"cpu": 4}), param_space=space,
                       tune_config=tune.TuneConfig(num_samples=args.trials, metric=metric, mode="max"))
    best = tuner.fit().get_best_result(metric=metric, mode="max")
    bc = {k: best.config[k] for k in _pk}
    log(f"[tune:{task}] best {metric}={best.metrics[metric]:.4f} — {bc}. Retraining winner + registering…")
    Model = RandomForestRegressor if task == "regress" else RandomForestClassifier
    mdl = Model(random_state=42, n_jobs=-1, **bc).fit(Xtr, ytr)
    pred = mdl.predict(Xte)
    if task == "regress":
        mets = {"rmse": float(root_mean_squared_error(yte, pred)), "r2": float(r2_score(yte, pred))}
        rm = f"{args.registered_model}_regressor"
    else:
        mets = {"accuracy": float(accuracy_score(yte, pred)), "f1": float(f1_score(yte, pred))}
        rm = f"{args.registered_model}_classifier"
    _register(mdl, {"task": task, "mode": "ray-tune", "n_rows": len(df), **bc}, mets, f"tune-{task}-best", rm)


def main():
    ap = argparse.ArgumentParser(description="Remote finance volatility trainer → weyland MLflow")
    ap.add_argument("--task", default=os.environ.get("TASK", "both"), choices=["regress", "classify", "both"])
    ap.add_argument("--n-estimators", type=int, default=int(os.environ.get("N_ESTIMATORS", "200")))
    ap.add_argument("--max-depth", type=int, default=int(os.environ.get("MAX_DEPTH", "12")))
    ap.add_argument("--experiment", default=os.environ.get("EXPERIMENT", "price-volatility"))
    ap.add_argument("--registered-model", default=os.environ.get("REGISTERED_MODEL", "price_volatility"))
    ap.add_argument("--tune", action="store_true", default=_envflag("TUNE"))
    ap.add_argument("--trials", type=int, default=int(os.environ.get("TRIALS", "16")))
    args = ap.parse_args()

    df = _read_training()
    ensure_experiment(MlflowClient(), args.experiment)
    mlflow.set_experiment(args.experiment)
    tasks = ["regress", "classify"] if args.task == "both" else [args.task]
    log(f"training {tasks}{' — Ray Tune' if args.tune else ''} (target={TARGET})…")
    for task in tasks:
        if args.tune:
            _tune(df, args, task)
        elif task == "regress":
            _fit_regressor(df, args)
        else:
            _fit_classifier(df, args)


if __name__ == "__main__":
    main()
