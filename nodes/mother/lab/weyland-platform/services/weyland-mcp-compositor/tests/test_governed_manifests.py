"""B256 (2026-11-23): governed writes trust the X-Forwarded-User / -Consumer headers, which is safe only where the gateway
is the sole caller. Both compositor deployments run the same image (scripts/ci/images.tsv ships them in lockstep), so
the manifests are what keeps writes off the fleet compositor, which Bifrost can also reach. These tests read the real
manifests and fail if that ever changes."""
import pathlib

import yaml

K8S = pathlib.Path(__file__).resolve().parents[3] / "k8s" / "mcp-servers"


def _docs(name):
    return [d for d in yaml.safe_load_all((K8S / name).read_text()) if d]


def _env(name):
    dep = next(d for d in _docs(name) if d["kind"] == "Deployment")
    return {e["name"]: e.get("value") for c in dep["spec"]["template"]["spec"]["containers"] for e in c.get("env", [])}


def test_governed_writes_are_on_in_the_memory_compositor_only():
    assert _env("compositor-memory.yaml").get("GOVERNED_WRITE") == "1"
    assert "GOVERNED_WRITE" not in _env("compositor.yaml")


def test_only_the_gateway_reaches_the_memory_compositor():
    pol = next(d for d in _docs("netpol-compositors.yaml")
               if d["kind"] == "NetworkPolicy" and d["spec"]["podSelector"]["matchLabels"] == {"app": "weyland-mcp-compositor-memory"})
    sources = [f for rule in pol["spec"]["ingress"] for f in rule["from"]]
    assert sources == [{"podSelector": {"matchLabels": {"app": "weyland-mcp-gateway"}}}]
