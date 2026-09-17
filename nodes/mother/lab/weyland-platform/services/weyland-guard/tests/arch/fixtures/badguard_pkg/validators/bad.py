"""Planted-violation fixture — a guardrail validator that imports the web framework. grimp reads this by AST;
fastapi need not be installed (include_external_packages tracks it as external)."""
import fastapi  # noqa: F401 — forbidden: guardrails must stay framework-free

_ = fastapi
