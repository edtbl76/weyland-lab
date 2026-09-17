"""Planted-violation fixture resource submodule — reaches UP into the assets layer, breaking
resources-are-independent. In a SUBMODULE (not __init__) so the broken import proves package-level
source_modules covers descendants."""
from badleaf_pkg import asset  # noqa: F401 — forbidden: resources must not import the pipeline layers

_ = asset
