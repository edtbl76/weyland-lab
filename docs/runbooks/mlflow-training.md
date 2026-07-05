# Runbook — MLflow training: one model, two feature sources, three use cases

This is the grid's **MLflow = "experiment tracking"** made concrete. It trains **one model** — a music **genre
classifier** — **two ways**, and tracks both in MLflow so the two paths are directly comparable. That deliberately
demonstrates **three distinct, documentable use cases**. The whole point: **the choice of feature source is an
architecture decision, not an accuracy one** — same task, same features, same result; different plumbing with
different guarantees.

Assets: `mlflow_genre_from_silver`, `mlflow_genre_from_feast` (group `datasets_music_ml`,
`weyland_pipeline/assets/mlflow_genre.py`). MLflow: `mlflow.weyland.lab`, experiment `genre-classifier`,
registered model `genre_classifier`. Diagram context: [../diagrams/flow-feast.md](../diagrams/flow-feast.md).

---

## Use case 1 — the ML task (genre classification)

**What:** predict a track's `track_genre` from its Spotify **audio features** (`danceability, energy, key,
loudness, mode, speechiness, acousticness, instrumentalness, liveness, valence, tempo`). A standard supervised
classification problem — `RandomForestClassifier`, 200 trees, an 80/20 stratified split, scored on **accuracy**
and **macro-F1**. Genres with < 20 samples are dropped so the stratified split and per-class metrics are
well-defined.

**What MLflow captures** (the "experiment tracking" the grid means): every run logs **params** (model type,
`n_estimators`, `feature_source`, `n_features`, `n_classes`, `n_rows`), **metrics** (`accuracy`, `f1_macro`), the
**fitted model** (`mlflow.sklearn.log_model` — the sklearn *flavor*, reloadable), and **registers** it as a
versioned `genre_classifier` in the Model Registry. So every experiment is reproducible, comparable, and the
model is retrievable — not a number in a log that scrolls away.

> Accuracy is **modest by nature** (audio features → genre across many genres is genuinely hard). That's the
> honest task — the value here is the *tracking + registry + comparison*, not a leaderboard score.

---

## Use case 2 — FEAST as the feature source (`mlflow_genre_from_feast`)

**How:** the training set's **features come from the feature store** — `FeatureStore.get_historical_features()`
pulls `track_audio_features` for each track (a **point-in-time** join), and the `track_genre` label is joined
from silver. Train on that.

**Why you'd do this — the guarantees Feast adds:**
- **Point-in-time correctness** — features are retrieved *as of* each row's timestamp, so a training set can
  never leak a feature value from the future. Critical when features are time-varying.
- **Train/serve consistency** — the **exact same feature definition** (`track_audio_features`) that trains the
  model is the one `get_online_features` serves at inference. No skew between "how I computed it for training"
  and "how I compute it live."
- **Feature reuse + governance** — the feature is defined once, discoverable, shared across models.
- **This is Feast's consumer.** Feast was built as a capability; *this asset is what consumes it* — the model
  is the reason the feature store exists.

**When to reach for it:** the model will be **served online** and must not have train/serve skew; features are
**time-varying** and point-in-time matters; features are **shared** across models/teams.

---

## Use case 3 — SILVER-DIRECT (`mlflow_genre_from_silver`)

**How:** read the **lakehouse silver Parquet** (`spotify_tracks`) straight from lakeFS, take the audio-feature
columns + `track_genre`, train. No feature store in the path at all.

**Why you'd do this:**
- **Simplicity** — one hop (read Parquet → train). No registry, no materialization, no online store, no extra
  infrastructure on the path.
- **Full control** — you see and shape the raw columns directly; ad-hoc feature engineering is trivial.
- **Fits one-off / exploratory / batch-only** work where the model is *not* served online and train/serve
  consistency is a non-issue.

**When to reach for it:** exploratory modeling, batch scoring, a model that's **never served online**, or when
the feature-store machinery would be pure overhead. Most notebooks start here.

---

## The decision — Feast vs silver-direct

| Dimension | **Feast-sourced (UC2)** | **Silver-direct (UC3)** |
|---|---|---|
| Point-in-time correctness | ✅ built-in (as-of joins) | ❌ you must handle it yourself |
| Train/serve consistency | ✅ same definition both sides | ❌ serving path is separate code |
| Online serving of the same feature | ✅ `get_online_features` | ❌ none |
| Feature reuse / governance | ✅ defined once, registered | ❌ per-script |
| Setup / infra on the path | heavier (registry + online + materialize) | minimal (read Parquet) |
| Best for | **served / time-varying / shared** models | **exploratory / batch / one-off** models |

**The teaching point:** run both and the accuracy is ~identical (same features). So you *don't* pick Feast for a
better model — you pick it when you need **point-in-time correctness, train/serve consistency, or reuse**. If
none of those apply, silver-direct is the simpler, honest choice. Same destination, different guarantees.

---

## View it in MLflow

`mlflow.weyland.lab` → Experiments → **`genre-classifier`**: two runs (`genre-silver`, `genre-feast`) side by
side — compare `accuracy` / `f1_macro`, filter/group by the `feature_source` param. → Models →
**`genre_classifier`**: two registered versions (one per source). Load a version back with
`mlflow.sklearn.load_model("models:/genre_classifier/<version>")`.

## Reproduce

Materialize the assets (Dagster UI, group `datasets_music_ml`) or:
```
kubectl -n weyland exec deploy/dagster-user-code -- dagster asset materialize --select mlflow_genre_from_silver,mlflow_genre_from_feast -m weyland_pipeline.definitions
```
Re-run after the Spotify silver or the Feast `track_audio_features` view changes — each run is a new tracked
experiment + a new registered model version.
