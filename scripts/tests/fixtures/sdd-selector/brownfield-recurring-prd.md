# PRD: alert rules as a maintained product

## Context
The lab's Prometheus alert rules (nodes/mother/lab/weyland-platform/k8s/monitoring/, an existing set of rule files
with promtool tests) are edited every few weeks as services come and go.

## Change
Add a severity-routing label to every existing rule and a guard that fails CI when a rule has none.

## Acceptance
- Every existing rule carries a severity label; promtool tests still pass.
- CI fails on a rule without the label.

We will keep changing these rules for the life of the lab: new services, new alerts, retuned thresholds, several
times a month. One person maintains them.
