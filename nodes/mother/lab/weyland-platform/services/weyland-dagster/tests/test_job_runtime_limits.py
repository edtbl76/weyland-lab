"""Job max-runtime caps must leave headroom over the job's measured runtime (B239 finding 15).

`datahub_catalog_emit_job` ran 23-31.5 minutes every night from 2026-10-02 to 2026-11-08 (Dagster run history) against
a 30-minute `dagster/max_runtime` tag. It failed whenever it ran a little long (10-04, 10-09..11, 10-13, 10-22..23),
then every night from 10-31, and the DataHub catalog went stale for 9+ days. The job is sequential on purpose
(`in_process_executor`: parallel ops each re-imported ~1.1 GB of definitions and ran the pod out of memory), so it
cannot simply be made parallel; the cap has to fit it. Reads the source with `ast`, so it runs in the light lane.
"""
import ast
import pathlib

DEFS = pathlib.Path(__file__).resolve().parents[1] / "weyland_pipeline" / "definitions.py"

# job -> the longest run observed when the cap was last set, in seconds. The cap must be at least twice that.
MEASURED_MAX = {"datahub_catalog_emit_job": 1890}  # 31.5 min, run 6a6f3d61 (2026-11-08), stopped at the old cap


def _max_runtime(job_name):
    tree = ast.parse(DEFS.read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == job_name:
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    for kw in dec.keywords:
                        if kw.arg == "tags" and isinstance(kw.value, ast.Dict):
                            for k, v in zip(kw.value.keys, kw.value.values):
                                if isinstance(k, ast.Constant) and k.value == "dagster/max_runtime":
                                    return int(v.value)
    raise AssertionError(f"{job_name} has no dagster/max_runtime tag in {DEFS.name}")


def test_catalog_emit_cap_leaves_twice_the_measured_runtime():
    for job, measured in MEASURED_MAX.items():
        cap = _max_runtime(job)
        assert cap >= 2 * measured, f"{job}: cap {cap}s is under 2x its measured {measured}s runtime"


def test_catalog_emit_cap_stays_under_the_instance_limit():
    # The instance-wide run_monitoring limit is 4 h (k8s/dagster/configmap.yaml); a job cap above it means nothing.
    assert _max_runtime("datahub_catalog_emit_job") < 4 * 3600
