"""GTZAN Genre Collection — 1k songs, 10 genres, canonical genre-classification benchmark.
Source: confit/gtzan-parquet (parquet audio, no trust_remote_code / RCE — marsyas/gtzan needs a load script).
We DECODE the audio and EXTRACT librosa features (the canonical GTZAN feature set — chroma/rms/spectral/zcr/
tempo/mfcc mean+var), so the silver is a real feature matrix for similarity (Qdrant/Weaviate), not just the
genre label. (The old land skipped the audio column → only (label, genre) landed → no vector possible.)"""
import csv as csvmod
import io
import numpy as np
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put, is_fresh_local


def _to_mono(y):
    y = np.asarray(y, dtype=float)
    return y.mean(axis=1) if y.ndim > 1 else y


def _decode(a):
    """HF Audio feature → {'array','sampling_rate'}; fall back to decoding raw {'bytes'} via soundfile."""
    if isinstance(a, dict) and a.get("array") is not None:
        return _to_mono(a["array"]), int(a["sampling_rate"])
    import soundfile as sf
    y, sr = sf.read(io.BytesIO(a["bytes"]))
    return _to_mono(y), int(sr)


def _gtzan_features(y, sr):
    import librosa
    f = {}

    def ms(name, arr):
        f[f"{name}_mean"] = float(np.mean(arr))
        f[f"{name}_var"] = float(np.var(arr))

    ms("chroma_stft", librosa.feature.chroma_stft(y=y, sr=sr))
    ms("rms", librosa.feature.rms(y=y))
    ms("spectral_centroid", librosa.feature.spectral_centroid(y=y, sr=sr))
    ms("spectral_bandwidth", librosa.feature.spectral_bandwidth(y=y, sr=sr))
    ms("rolloff", librosa.feature.spectral_rolloff(y=y, sr=sr))
    ms("zero_crossing_rate", librosa.feature.zero_crossing_rate(y))
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    f["tempo"] = float(np.atleast_1d(tempo)[0])
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    for i in range(20):
        f[f"mfcc{i + 1}_mean"] = float(np.mean(mfcc[i]))
        f[f"mfcc{i + 1}_var"] = float(np.var(mfcc[i]))
    return f


@asset(group_name="datasets_music", description="Land GTZAN + extract librosa audio features → music/raw/gtzan/.")
def datasets_music_gtzan_land(context) -> Output[dict]:
    if is_fresh_local(context, max_age_days=30):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    from datasets import load_dataset
    client = music_minio()
    context.log.info("GTZAN: loading confit/gtzan-parquet + extracting librosa features (~1k clips)")
    ds = load_dataset("confit/gtzan-parquet", split="train")
    label_cols = [c for c in ds.column_names if c not in {"audio", "video", "file"}]
    rows, ok = [], 0
    for i, row in enumerate(ds):
        try:
            y, sr = _decode(row["audio"])
            rec = {c: str(row[c]) for c in label_cols}
            rec.update(_gtzan_features(y, sr))
            rows.append(rec)
            ok += 1
        except Exception as e:  # noqa: BLE001 — one bad clip must not sink the land
            context.log.warning(f"gtzan clip {i}: feature extraction failed ({type(e).__name__}: {e})")
    if not rows:
        raise RuntimeError("GTZAN: no clips yielded features")
    fields = list(rows[0].keys())
    buf = io.StringIO()
    w = csvmod.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    data = buf.getvalue().encode("utf-8")
    music_put(client, "gtzan/gtzan.csv", data, "text/csv")
    context.log.info(f"gtzan/gtzan.csv: {ok:,} clips × {len(fields)} cols → {len(data):,} bytes")
    return Output({"rows": ok, "features": len(fields)}, metadata={"rows": MetadataValue.int(ok)})
