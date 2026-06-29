"""AudioSet (balanced) — Google's large-scale audio event dataset.
35k clips, 527 audio event labels including music. CC-BY-4.0.
Source: agkphysics/AudioSet on HuggingFace (balanced config)."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land AudioSet balanced (35k clips, 527 labels) → music/raw/audioset/.")
def datasets_music_audioset_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("AudioSet: loading agkphysics/AudioSet (balanced)")
    results = {}
    for split in ["train", "test"]:
        try:
            ds = load_dataset("agkphysics/AudioSet", name="balanced", split=split)
            skip_cols = {"audio", "video", "file"}
            cols = [c for c in ds.column_names if c not in skip_cols]
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=cols)
            writer.writeheader()
            for row in ds.select_columns(cols):
                writer.writerow({k: str(v) for k, v in row.items()})
            data = buf.getvalue().encode("utf-8")
            music_put(client, f"audioset/{split}.csv", data, "text/csv")
            results[split] = len(ds)
            context.log.info(f"audioset/{split}.csv: {len(ds):,} rows → {len(data):,} bytes")
        except Exception as e:
            import traceback
            results[split] = f"ERROR: {e}"
            context.log.error(f"AudioSet {split} FAILED: {e}\n{traceback.format_exc()}")
    total = sum(v for v in results.values() if isinstance(v, int))
    return Output(results, metadata={"total_rows": MetadataValue.int(total)})
