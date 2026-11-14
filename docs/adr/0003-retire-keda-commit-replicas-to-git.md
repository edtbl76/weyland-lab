# Retire KEDA; scale data-mesh stores by committing replicas to git

## Status

accepted

Date: 2026-08-22

## Context and Problem Statement

KEDA was installed as a platform capability for waking and sleeping workloads. Every Argo Application runs `selfHeal: true`, so any external actor that changes `/spec/replicas` fights Argo.

## Decision Drivers

* Argo CD (git) is the only writer of desired state.
* No installed component that nothing uses.

## Considered Options

* Retire KEDA; change replicas by a commit
* Keep KEDA and add an Argo `ignoreDifferences` carve-out on `/spec/replicas`
* A store-scaler service writing replicas directly

## Decision Outcome

Chosen option: Retire KEDA, because in 62 days it produced exactly one ScaledObject (its own interceptor) and both scaling options need the same rejected carve-out. Waking or sleeping a store is a commit of `replicas` to git.

### Consequences

* Good, because git stays the single source of desired state; Argo never fights a second writer.
* Bad, because a store cannot be woken by a button; memory pressure is owned by B134 (held for hardware).

## More Information

Runbooks: [keda.md](../runbooks/keda.md) (retired; kept for the gotchas), [port-agent-easy-button.md](../runbooks/port-agent-easy-button.md). Do not re-propose KEDA or the carve-out.
