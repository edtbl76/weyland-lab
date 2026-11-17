# Keep MLflow on mother

## Status

accepted

Date: 2026-11-17

## Context and Problem Statement

B134 moved the largest stateless pods from mother to timberback, the second k3s node. MLflow, with a 3.5 GB memory
request, was on that list. It was held back because of how its LAN port is locked down.

MLflow has no login: a caller that reaches it can delete experiments, runs and models. Its LAN NodePort,
`mlflow-lan` (`:30500`), admits rogueone (`192.168.1.230`) alone, enforced by an `ipBlock` in the NetworkPolicy
`mlflow-front-door-only`. That rule needs the caller's real source IP, which only `externalTrafficPolicy: Local`
keeps. A Local NodePort answers only on the node that runs the pod, and every caller dials `192.168.1.243:30500`.

## Decision Drivers

* Keep the B211 lockdown: only rogueone reaches the unauthenticated MLflow from the LAN.
* Move a workload only for a real gain. After B134, mother sits at 74% of its memory requested (84% before).

## Considered Options

* Keep MLflow on mother, pinned with a node selector
* Move it to timberback and repoint callers to `192.168.1.233:30500`
* Switch `mlflow-lan` to `externalTrafficPolicy: Cluster`

## Decision Outcome

Chosen option: Keep MLflow on mother (owner, 2026-11-17), because neither alternative is worth its cost.

* **Repointing** touches 19 files that hard-code `192.168.1.243:30500` (Ray, the genre trainer, the gateway
  scripts, `scripts/.env` and the docs), plus a repointed Ray worker, all to free 3.5 GB that mother no longer
  needs.
* **The Cluster policy** SNATs every caller to a node IP. The rogueone-only rule then cannot match, and the
  unauthenticated MLflow would be open to the whole LAN. That undoes B211. Do not re-propose it.

### Consequences

* Good, because the LAN lockdown and every caller's URL stay as they are.
* Neutral: MLflow's 3.5 GB request stays on mother.
* Bad, because a mother outage still takes MLflow down. That was true before, and its state (Postgres and MinIO)
  lives on mother anyway.

## More Information

* Pin: `nodeSelector: kubernetes.io/hostname: mother` in `k8s/mlflow/mlflow.yaml`; `placement.yaml` row
  `k8s:weyland/Deployment/mlflow`.
* Lockdown: `k8s/mlflow/netpol.yaml` (B211).
* The pre-lift placement check: [docs/runbooks/timberback.md § The onboarding taint](../runbooks/timberback.md).
* Backlog B134 (Linear EMA-195); the target hardware: [ADR-0012](./0012-timberback-bare-metal-ubuntu-on-btrfs.md).
