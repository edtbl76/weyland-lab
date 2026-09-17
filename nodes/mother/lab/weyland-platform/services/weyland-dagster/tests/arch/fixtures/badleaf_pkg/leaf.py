"""Planted-violation fixture leaf — a datasets_lib pure leaf that WENT BAD. It imports dagster (breaks
leaves-are-dagster-free) AND a resource client (breaks leaves-are-resource-free). grimp reads this by AST;
nothing is executed, so the unresolvable `dagster` import is fine under include_external_packages."""
import dagster  # noqa: F401 — forbidden: a pure leaf must not import dagster
from badleaf_pkg.resource import thing  # noqa: F401 — forbidden: a pure leaf must not import resources

_ = (dagster, thing)
