"""Fixture resource package. Package-shaped on purpose: the planted `resources-are-independent` contract
uses this package as its `source_modules`, so a violation in the SUBMODULE (thing.py) proves the real
contract's package-level source (`weyland_pipeline.resources`) covers its submodules, not just __init__."""
