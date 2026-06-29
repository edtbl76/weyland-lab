"""LP-MusicCaps — music captioning and audio tagging datasets from HuggingFace.
Two public configs:
  MC  (5.5k rows)  — music captioning, structured metadata
  MTT (22k audio / 88k captions) — audio tagging, multi-label
"""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land LP-MusicCaps-MC (5.5k captions) → music/raw/lp_musiccaps_mc/.")
def datasets_music_lp_musiccaps_mc_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("LP-MusicCaps-MC: loading seungheondoh/LP-MusicCaps-MC")
    results = {}
    for split in ["train", "test"]:
        try:
            ds = load_dataset("seungheondoh/LP-MusicCaps-MC", split=split)
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            music_put(client, f"lp_musiccaps_mc/{split}.csv", data, "text/csv")
            results[split] = len(ds)
            context.log.info(f"lp_musiccaps_mc/{split}.csv: {len(ds):,} rows → {len(data):,} bytes")
        except Exception as e:
            results[split] = f"ERROR: {e}"
            context.log.warning(f"LP-MusicCaps-MC {split}: {e}")
    total = sum(v for v in results.values() if isinstance(v, int))
    return Output(results, metadata={"total_rows": MetadataValue.int(total)})


@asset(group_name="datasets_music", description="Land LP-MusicCaps-MTT (22k audio/88k captions) → music/raw/lp_musiccaps_mtt/.")
def datasets_music_lp_musiccaps_mtt_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("LP-MusicCaps-MTT: loading seungheondoh/LP-MusicCaps-MTT")
    results = {}
    for split in ["train", "valid", "test"]:
        try:
            ds = load_dataset("seungheondoh/LP-MusicCaps-MTT", split=split)
            buf = io.StringIO()
            cols = [c for c in ds.column_names if c != "audio"]
            writer = csvmod.DictWriter(buf, fieldnames=cols)
            writer.writeheader()
            for row in ds:
                writer.writerow({k: v for k, v in row.items() if k in cols})
            data = buf.getvalue().encode("utf-8")
            music_put(client, f"lp_musiccaps_mtt/{split}.csv", data, "text/csv")
            results[split] = len(ds)
            context.log.info(f"lp_musiccaps_mtt/{split}.csv: {len(ds):,} rows → {len(data):,} bytes")
        except Exception as e:
            results[split] = f"ERROR: {e}"
            context.log.warning(f"LP-MusicCaps-MTT {split}: {e}")
    total = sum(v for v in results.values() if isinstance(v, int))
    return Output(results, metadata={"total_rows": MetadataValue.int(total)})
