# Node memory resilience — swap-off + the memory-pressure survival test

**mother is a SINGLE k3s node.** Node-RAM exhaustion is a **total outage**, not a reschedule. B99 (2026-07-22)
root-caused the 2026-07-21 outage — via a live A/B test — to **swap**, and this runbook codifies the fix and the
test that proves it holds.

## The rule: swap MUST be off on mother

Kubernetes assumes swap is disabled. On this **memory-overcommitted** node (pod limits sum to ~300% of 64Gi), a
pressure spike with swap **on** makes the kernel *thrash* — it swaps out idle apiserver / `systemd-networkd` /
`systemd-resolved` pages instead of cleanly killing the offender. Those daemons then stall on swap-in, the control
plane + network stack go unresponsive, and mother drops off the LAN (`no route to host`). With swap **off**, the same
pressure produces a fast, clean **kernel OOM-kill** of the biggest offender (BestEffort / high `oom_score` first —
never a critical pod) and the node stays `Ready`.

### Current configuration (the fix)

| layer | what | where |
|---|---|---|
| **swap off (THE fix)** | `/swap.img` commented out of `/etc/fstab` (runtime `swapoff -a` + reboot-safe) | mother host |
| **kubelet backstop** | `system-reserved=2Gi` + `kube-reserved=1Gi` + `eviction-hard=memory.available<1.5Gi` | `nodes/mother/host/rancher/k3s/config.yaml` → `/etc/rancher/k3s/config.yaml` |
| **alarm** | leading node-memory-pressure alert + `KubePodOOMKilled` (B98) | `k8s/monitoring/node-memory-alerts.yaml` |

Note: the A/B test showed the kubelet `eviction-hard` did **not** win the race against a fast runaway — the **kernel
OOM-killer** caught it first. That is the correct last line of defense on a single node; the reserves are retained as
defense-in-depth and to shrink the overcommit.

### Verify swap is off + reserves are live (on mother)

```
grep -i swap /etc/fstab
```
```
free -m
```
```
kubectl get --raw "/api/v1/nodes/mother/proxy/configz" | grep -o '"evictionHard":{[^}]*}'
```
Expect: fstab line commented (`#/swap.img …`), `Swap: 0 0 0`, and `"evictionHard":{"memory.available":"1.5Gi"}`.

## The survival test (re-run after any node/kubelet/swap change)

Drives node memory to the wall with a disposable BestEffort hog and confirms the node **stays reachable** while the
offender is killed. The hog is the only possible victim (BestEffort = #1 eviction target; negative priority puts it
below every real pod; gradual allocation gives the kernel/kubelet time to act).

### 1. Apply the hog (on mother)

Write `~/eviction-test.yaml` with:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: eviction-test-low
value: -10
globalDefault: false
description: "node-memory test — most-evictable; hog is shed first"
---
apiVersion: v1
kind: Namespace
metadata:
  name: eviction-test
---
apiVersion: v1
kind: Pod
metadata:
  name: memhog
  namespace: eviction-test
spec:
  priorityClassName: eviction-test-low
  restartPolicy: Never
  terminationGracePeriodSeconds: 5
  automountServiceAccountToken: false
  containers:
    - name: memhog
      image: python:3.12-slim         # BestEffort on purpose: NO resources block
      imagePullPolicy: IfNotPresent
      command: ["python", "-u", "-c"]
      args:
        - |
          import time
          blocks = []
          gi = 0.0
          while True:
              blocks.append(bytearray(512 * 1024 * 1024))
              gi += 0.5
              print(f"allocated ~{gi:.1f}Gi", flush=True)
              time.sleep(8)
```
```
kubectl apply -f ~/eviction-test.yaml
```

### 2. Watch (on mother, two panes)

```
kubectl get pod memhog -n eviction-test -w
```
```
watch -n2 free -m
```

### 3. PASS criteria

- `available` falls in a controlled line (no swap: `Swap: 0 0 0` throughout).
- `memhog` reaches a terminal state — `OOMKilled` (exit 137, kernel won the race) **or** `Evicted` (kubelet won).
  Confirm: `kubectl get pod memhog -n eviction-test -o jsonpath='{.status.reason}{"  "}{.status.containerStatuses[0].state.terminated.reason}{"  "}{.status.containerStatuses[0].state.terminated.exitCode}{"\n"}'`
- **`kubectl never hangs and `kubectl get node mother` stays `Ready` the entire time.** ← the actual proof.
- No *other* pod shows `Failed`: `kubectl get pods -A --field-selector=status.phase=Failed` (ignore pods days-old — pre-existing).

**FAIL** looks like: `kubectl` returns `TLS handshake timeout` on `127.0.0.1:6443` and the node flips `NotReady`
(the swap-on signature). If that happens, swap is back on or the config regressed — recover immediately.

### 4. Recover / teardown (on mother)

If it thrashes (FAIL), kill the hog directly — bypasses a stalled API:
```
sudo pkill -9 -f blocks.append
```
Normal teardown:
```
kubectl delete ns eviction-test
```
```
kubectl delete priorityclass eviction-test-low
```

## Reference

- Incident + A/B result: B99 (`docs/backlog.md`), EMA-90.
- Alarming: B98 (`docs/runbooks/observability.md`, `k8s/monitoring/node-memory-alerts.yaml`).
- Forensics (which pod stormed): the `node-oom-forensics` note.
