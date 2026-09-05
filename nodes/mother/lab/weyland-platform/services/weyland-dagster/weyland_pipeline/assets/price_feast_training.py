"""Feast training-set retrieval for the finance ML lane (B113 Phase 5) — the point-in-time CONSUMER.

Builds the volatility model's training set *from Feast*, mirroring genre_feast_training.py: an entity_df of
(ticker, date, **forward 5-day realized-vol target**) → `FeatureStore.get_historical_features` (a point-in-time
join over the `price_features` view, whose offline store is the STRICT-mTLS `feast` Postgres) → written to
lakeFS as parquet. The external finance-trainer (rogueone) then reads it and fits both a regressor and a
classifier on the same table.

**Why in-cluster + MESHED (not in the trainer):** identical to genre — `get_historical_features` connects to
the STRICT-mTLS `feast` Postgres, reachable only from a mesh member; the remote trainer + hostNetwork Ray head
cannot. So the join runs here (Dagster is meshed + carries `feast_repo/`) and lands the result in lakeFS.

**The target is forward-looking and lives in the entity_df, NOT in Feast** — Feast only serves the trailing
as-of-date features (no leakage). fwd_vol_5d[t] = stddev of the daily returns on days t+1..t+5.

To keep the point-in-time join + training tractable (and focused on the modern regime), the entity_df is
capped to the most recent ~10 years of each ticker's history — a deliberate scoping choice, logged.
"""
import io as _bio
import os
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib import io
from .datasets_lib.ml_targets import forward_vol_target

_REPO = "finance"
_DATASET = "price_feast_training"
_PRICE_FEATS = ["ret_1d", "ret_5d", "ret_20d", "vol_5d", "vol_10d", "vol_20d",
                "volume_ratio", "range_20d", "sma_ratio_20d"]
_TRAIN_YEARS = 10   # cap the entity_df to the last ~N years so the Feast join + fit stay tractable


def _read_price_daily(mc, log) -> pd.DataFrame:
    """(ticker, date, adj_close) from the price_daily silver — the entity keys + the raw series the forward
    target is computed from. Only the three columns are read; the FEATURES come from Feast."""
    log.info("reading price_daily silver from lakeFS (ticker, date, adj_close)…")
    frames = []
    for obj in mc.list_objects(_REPO, prefix=f"{io.branch()}/parquet/price_daily/", recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        t = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        t.close()
        try:
            mc.fget_object(_REPO, obj.object_name, t.name)
            frames.append(pd.read_parquet(t.name, columns=["ticker", "date", "adj_close"]))
        finally:
            os.unlink(t.name)
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    df["ticker"] = df["ticker"].astype(str)
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna(subset=["ticker", "date", "adj_close"])


@asset(group_name="datasets_finance_ml",
       description="Feast CONSUMER (B113 Phase 5): build the volatility model's training set via Feast "
                   "get_historical_features (point-in-time join over price_features; offline store = the "
                   "STRICT-mTLS feast Postgres) → lakeFS finance/parquet/price_feast_training/. Entity_df carries "
                   "the forward 5-day realized-vol target (no leakage — Feast serves trailing features only). "
                   "Runs MESHED in-cluster; the external rogueone finance-trainer then fits regressor + classifier.")
def price_feast_training_set(context):
    from feast import FeatureStore

    mc = io.client()
    prices = _read_price_daily(mc, context.log)
    tgt = (forward_vol_target(prices, n=5)
           .rename(columns={"fwd_vol": "fwd_vol_5d"})
           .dropna(subset=["fwd_vol_5d"]))
    cutoff = tgt["date"].max() - pd.DateOffset(years=_TRAIN_YEARS)
    tgt = tgt[tgt["date"] >= cutoff]
    context.log.info(f"entity_df: {len(tgt):,} (ticker,date) rows since {cutoff.date()} "
                     f"({tgt['ticker'].nunique()} tickers) with a forward-vol target")

    edf = pd.DataFrame({
        "ticker": tgt["ticker"].values,
        "event_timestamp": pd.to_datetime(tgt["date"].values, utc=True),
        "fwd_vol_5d": tgt["fwd_vol_5d"].values,
    })

    fs = FeatureStore(repo_path=os.environ.get("FEAST_REPO", "/app/feast_repo"))
    context.log.info(f"Feast get_historical_features — point-in-time join over {len(edf):,} ticker/date entities "
                     "(the SLOW step; Feast emits no per-row progress; minutes at scale)…")
    feats = fs.get_historical_features(
        entity_df=edf, features=[f"price_features:{c}" for c in _PRICE_FEATS]).to_df()

    feats["ticker"] = feats["ticker"].astype(str)
    for c in _PRICE_FEATS:
        feats[c] = pd.to_numeric(feats[c], errors="coerce")
    df = feats.dropna(subset=_PRICE_FEATS + ["fwd_vol_5d"])[["ticker", "event_timestamp", *_PRICE_FEATS, "fwd_vol_5d"]]
    if df.empty:
        raise RuntimeError("Feast returned zero usable training rows — refusing to commit an empty training set "
                           "(check that scripts/feast_setup.py loaded price_features + feast apply ran).")
    context.log.info(f"Feast returned {len(feats):,} rows → {len(df):,} training rows")

    buf = _bio.BytesIO()
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), buf)
    io.put(mc, _REPO, f"parquet/{_DATASET}/part.parquet", buf.getvalue())

    import lakefs

    lc = lakefs.Client(host=io.endpoint(), username=os.environ["LAKEFS_ACCESS_KEY_ID"],
                       password=os.environ["LAKEFS_SECRET_ACCESS_KEY"])
    br = lakefs.Repository(_REPO, client=lc).branch(io.branch())
    committed, cid = False, ""
    if list(br.uncommitted()):
        ref = br.commit(message="price_feast_training_set (Feast point-in-time retrieval)",
                        metadata={"producer": "dagster:price_feast_training_set"})
        cid = ref.get_commit().id
        committed = True
        context.log.info(f"lakeFS {_REPO}/{io.branch()}: committed → {cid[:12]}")

    out = {"rows": len(df), "tickers": int(df["ticker"].nunique()),
           "path": f"lakefs://{_REPO}/{io.branch()}/parquet/{_DATASET}/", "committed": committed}
    return Output(out, metadata={"rows": MetadataValue.int(out["rows"]),
                                 "tickers": MetadataValue.int(out["tickers"]),
                                 "path": MetadataValue.text(out["path"]),
                                 "commit": MetadataValue.text(cid or "—")})
