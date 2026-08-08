"""B49 thread (b) Phase 2 — OpenTelemetry for the Dagster user-code process. App-level spans → Tempo OTLP.

OPT-IN via OTEL_EXPORTER_OTLP_ENDPOINT (set in the k8s env → http://tempo.monitoring.svc.cluster.local:4318);
unset → every `traced(...)` is a no-op, so local runs / tests need no collector.

Two deliberate choices:
  • SimpleSpanProcessor, NOT Batch — Dagster's multiprocess executor runs each op in a SUBPROCESS that exits when the
    op ends; Batch would drop spans that hadn't flushed. Simple exports each span synchronously on end, which is fine
    at our COARSE volume.
  • COARSE spans only (per store-load / per dataset), NOT per-DB-query — auto-instrumenting cassandra/psycopg2 at the
    query level would explode into millions of spans on a 17M-row hydrate. The mesh already gives service-level spans
    (dagster-user-code.weyland); these add the app-internal "which dataset/store step is slow" detail.

HTTP OTLP (:4318), matching the tool-server — avoids the gRPC/Envoy http2-framing snag on the meshed→unmeshed hop.
"""
import os
from contextlib import contextmanager

_ENABLED = False


def init_otel():
    """Set up the tracer provider + OTLP exporter once per process. Safe to call repeatedly and in forked op
    subprocesses (each re-imports the code location, so this runs fresh there)."""
    global _ENABLED
    if _ENABLED or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    provider = TracerProvider(resource=Resource.create(
        {"service.name": os.environ.get("OTEL_SERVICE_NAME", "weyland-dagster")}))
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))  # reads OTEL_EXPORTER_OTLP_ENDPOINT (+ /v1/traces)
    trace.set_tracer_provider(provider)
    _ENABLED = True


@contextmanager
def traced(name, **attrs):
    """Coarse span around a unit of work (a store-load, a dataset load). No-op when OTel is disabled. The yielded
    span (or None) lets the caller set result attributes (e.g. row counts) after the work finishes."""
    if not _ENABLED:
        yield None
        return
    from opentelemetry import trace
    with trace.get_tracer("weyland_pipeline").start_as_current_span(name) as span:
        for k, v in attrs.items():
            if v is not None:
                span.set_attribute(k, v)
        yield span


def traced_load(fn):
    """Decorator for the per-dataset `_load_dataset_to_<store>` loaders — one coarse span per call, named
    `<store>_load:<dataset>` (so a hydrate trace shows which dataset in which store is slow, e.g. cassandra:lastfm).
    No-op when OTel is disabled. Pulls `dataset` from the bound args regardless of its position in the signature."""
    import functools
    import inspect
    sig = inspect.signature(fn)
    store = fn.__name__.replace("_load_dataset_to_", "")

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not _ENABLED:
            return fn(*args, **kwargs)
        try:
            ds = sig.bind_partial(*args, **kwargs).arguments.get("dataset")
        except Exception:
            ds = None
        with traced(f"{store}_load:{ds}", store=store, dataset=ds):
            return fn(*args, **kwargs)

    return wrapper
