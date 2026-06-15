from prometheus_client import Counter, Histogram
from .verdict import Verdict, Hook, Mode

_VERDICTS = Counter(
    "guardrail_verdicts_total", "Guardrail verdicts",
    ["validator", "hook", "decision", "mode"],
)
_LATENCY = Histogram(
    "guardrail_validator_latency_ms", "Validator latency (ms)", ["validator", "hook"],
)


def observe(hook: Hook, mode: Mode, verdict: Verdict) -> None:
    _VERDICTS.labels(verdict.validator, hook.value, verdict.decision.value, mode.value).inc()
    if verdict.latency_ms is not None:
        _LATENCY.labels(verdict.validator, hook.value).observe(verdict.latency_ms)
