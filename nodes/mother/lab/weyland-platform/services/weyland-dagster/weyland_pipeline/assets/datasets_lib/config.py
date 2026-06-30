"""DomainConfig — the explicit, per-domain knobs the shared broker needs. Allowlists are written out as
literal sets (NOT derived from the storage grid): the grid is a guideline with free-text cells, and we
want the code to be the grep-able source of truth for what actually runs. Keyed by raw/ folder name."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainConfig:
    domain: str                          # "music" / "health" — drives asset names datasets_<domain>_<fmt>
    repo: str                            # lakeFS repo / bucket
    namespace: str                       # iceberg namespace, e.g. "datasets_music"
    group_name: str                      # dagster asset group
    land_deps: tuple = ()                # land asset names this transform depends on (asset-graph ordering)
    # per-format allowlists (raw/ folder names). A table absent from a format's set is skipped for that
    # format BEFORE the read. parquet/arrow/avro/iceberg are usually "all"; lance is selective.
    parquet_allow: frozenset = field(default_factory=frozenset)
    arrow_allow: frozenset = field(default_factory=frozenset)
    avro_allow: frozenset = field(default_factory=frozenset)
    lance_allow: frozenset = field(default_factory=frozenset)
    iceberg_allow: frozenset = field(default_factory=frozenset)

    @property
    def producer(self) -> str:
        return f"datasets_{self.domain}"
