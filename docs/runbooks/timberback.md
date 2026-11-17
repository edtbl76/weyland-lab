# timberback — runbook

timberback is the lab's k3s **GPU worker**: bare-metal Ubuntu 24.04.5 on **btrfs**, joined to mother's cluster
(decision: [ADR-0012](../adr/0012-timberback-bare-metal-ubuntu-on-btrfs.md)). Host inventory row: [hosts.md](../hosts.md).
Host config files live in `nodes/timberback/host/` and are tracked in `placement.yaml` (`host_config`).

| | |
|---|---|
| Hardware | AMD Ryzen 9 9950X (16C/32T), 96 GB, NVIDIA RTX 5070 Ti 16 GB + AMD iGPU, 4 TB WD SN820 NVMe |
| Address | `192.168.1.233`, static, netplan on `eno1` (`/etc/netplan/50-cloud-init.yaml`) |
| Access | `ssh emangini@timberback` (rogueone's key) |
| Kernel | HWE **7.0** (`linux-generic-hwe-24.04`). **Never install the 6.8 GA kernel (`linux-generic`)**: the board's Realtek RTL8126 5GbE ports need kernel 6.9 or newer, so a 6.8 boot has no network |
| GPU stack | NVIDIA **595.99.02** open, signed prebuilt modules (`linux-modules-nvidia-595-open-generic-hwe-24.04`; Secure Boot is on); container toolkit **1.20.1** |
| k3s | agent v1.35.5+k3s1 (matches mother), service `k3s-agent`; config `/etc/rancher/k3s/config.yaml` |

## The filesystem layout

One btrfs filesystem on `nvme0n1p2`, with root in its own subvolume so it can be snapshotted and swapped:

| Subvolume | Mounted at | In root snapshots? | Why |
|---|---|---|---|
| `@` | `/` | yes | the OS, the NVIDIA driver, every package |
| `@home` | `/home` | no | user files survive a rollback |
| `@var_log` | `/var/log` | no | logs survive a rollback, so you can read what went wrong |
| `@rancher` | `/var/lib/rancher` | no | k3s state and container images: a rollback must not rewind the node's cluster state or re-pull images |
| `@swap` | `/swap` | no | btrfs cannot snapshot a subvolume holding an active swap file (8 GB `/swap/swapfile`) |
| `.snapshots` (inside `@`) | `/.snapshots` | — | snapper's snapshots of `/` |

`/etc/fstab` and GRUB both name the root as **`subvol=@`**. That is why rollback swaps `@` (below) instead of using
`snapper rollback`, which assumes root is the default subvolume (the openSUSE layout) and would be ignored at boot here. The swap method is drilled (see Roll back).

## Snapshots

snapper takes a snapshot **before and after every apt change** automatically (the `80snapper` apt hook). No hourly
snapshots; cleanup keeps 20, plus 10 marked important. Quotas are off. Snapshot **1** is the clean baseline and
**12** is the first known-good kernel + driver point.

List them:

[timberback]
```
sudo snapper -c root list
```

Take one by hand before anything risky (mark it important so cleanup keeps it longer):

[timberback]
```
sudo snapper -c root create --cleanup-algorithm number --userdata important=yes --description "before <what you are about to change>"
```

See what changed between two snapshots:

[timberback]
```
sudo snapper -c root status <older>..<newer>
```

## Roll back

> **Drilled 2026-11-14, passed** — using exactly the commands below. Snapshot 15 was taken, then marker files were
> written to `/etc` (inside `@`) and `/var/log` (in `@var_log`). After the swap to snapshot 15 and a reboot (about
> 40 s): the `/etc` marker was gone, the `/var/log` marker was kept (outside the snapshots, as designed), root was the
> new `@` (subvolume 277, made from snapshot 15), snapper still listed every snapshot, the GPU answered
> (`nvidia-smi`), `k3s-agent` came back, and the node advertised `nvidia.com/gpu: 1` after uncordon. The rolled-back
> copy was then deleted with step 5. Re-drill after any change to the layout, `fstab` or GRUB.

The idea: rename the broken `@` aside, make a new `@` from the snapshot you want, move `.snapshots` into it, reboot.
GRUB and `fstab` load whatever is called `@`, so nothing else changes. The k3s state (`@rancher`), logs and home are
untouched.

**1. Drain the node** so its pods reschedule cleanly (from rogueone):

[rogueone]
```
kubectl drain timberback --ignore-daemonsets --delete-emptydir-data
```

**2. Pick the snapshot** to return to (`sudo snapper -c root list`) and swap it in. Replace `N`:

[timberback]
```
N=12; T=/mnt/top; D=$(date +%Y%m%d-%H%M); sudo mkdir -p $T && sudo mount -o subvolid=5 /dev/nvme0n1p2 $T && sudo mv $T/@ $T/@.rolledback-$D && sudo btrfs subvolume snapshot $T/@.rolledback-$D/.snapshots/$N/snapshot $T/@ && sudo rmdir $T/@/.snapshots && sudo mv $T/@.rolledback-$D/.snapshots $T/@/.snapshots && sudo btrfs subvolume set-default $(sudo btrfs subvolume show $T/@ | awk '/Subvolume ID/{print $3}') $T && sudo umount $T && echo "SWAPPED to snapshot $N — reboot now"
```

**3. Reboot and check:**

[timberback]
```
sudo reboot
```

[timberback]
```
uname -r; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader; findmnt -n -o SOURCE /
```

**4. Uncordon** (from rogueone):

[rogueone]
```
kubectl uncordon timberback
```

**5. Later, once you are sure,** delete the rolled-back copy (`@.rolledback-<date>`) from the top level:

[timberback]
```
sudo mount -o subvolid=5 /dev/nvme0n1p2 /mnt/top && sudo ls /mnt/top && sudo btrfs subvolume delete /mnt/top/@.rolledback-<date> && sudo umount /mnt/top
```

**If timberback will not boot at all:** boot the Ubuntu 24.04.5 server USB stick, choose **Help → Enter shell**, and
run step 2's commands there (the disk is the same `nvme0n1p2`). `grub-btrfs` (boot-menu snapshots) is not packaged
for 24.04 and is not installed.

## Change the NVIDIA driver or the kernel

The kernel metapackages and the NVIDIA packages are **held together** (`apt-mark showhold`), because the NVIDIA
module is built per kernel: moving one without the other leaves the GPU missing after a reboot. Change them together,
on purpose:

**1.** Drain the node (as in Roll back, step 1), then take an important snapshot:

[timberback]
```
sudo snapper -c root create --cleanup-algorithm number --userdata important=yes --description "before driver/kernel change to <version>"
```

**2. Release the holds:**

[timberback]
```
sudo apt-mark unhold $(apt-mark showhold)
```

**3a. A newer kernel** (same driver branch) — upgrade the kernel and its matching NVIDIA module together:

[timberback]
```
sudo apt-get install --only-upgrade linux-generic-hwe-24.04 linux-image-generic-hwe-24.04 linux-headers-generic-hwe-24.04 linux-modules-nvidia-595-open-generic-hwe-24.04
```

**3b. A different driver branch** (for example 580 or 615; list them with `ubuntu-drivers list`) — replace `NEW`:

[timberback]
```
NEW=615; sudo apt-get install nvidia-headless-$NEW-open nvidia-utils-$NEW linux-modules-nvidia-$NEW-open-generic-hwe-24.04
```

Always the **`-open`** variant (Blackwell needs NVIDIA's open kernel modules) and the **prebuilt `linux-modules-nvidia-*`**
package (signed for Secure Boot; never the DKMS build).

**4. Rebuild the boot image, reboot, check:**

[timberback]
```
sudo update-initramfs -u -k all && sudo reboot
```

[timberback]
```
uname -r; lspci -nnk -s 01:00.0 | grep "driver in use"; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
```

`Kernel driver in use: nvidia` and the new version mean success. If it says `nouveau`, the blacklist is missing from
the boot image: rerun `sudo update-initramfs -u -k all` and reboot.

**5. Hold the new set again** and uncordon:

[timberback]
```
sudo apt-mark hold $(dpkg-query -W -f '${Package}\n' 'linux-generic-hwe-24.04' 'linux-image-generic-hwe-24.04' 'linux-headers-generic-hwe-24.04' 'linux-modules-nvidia-*-open-generic-hwe-24.04' 'nvidia-*' 'libnvidia-*' 2>/dev/null)
```

If the GPU is broken after the change, roll back to the snapshot from step 1 (see Roll back).

**No driver-drift check (decided 2026-11-14, owner: "Agreed").** rogueone needs one because unattended upgrades moved
its NVIDIA userspace without a reboot. Here the holds remove that cause: unattended upgrades respect `apt-mark hold`,
and this procedure re-holds at the end. When a workload first depends on the GPU, add one alert on what matters
instead — timberback's allocatable `nvidia.com/gpu` dropping to 0, or the device plugin not running — which catches
drift and every other way of losing the GPU.

**CUDA versions do not need any of this:** CUDA lives in the container image. A newer driver runs older CUDA, so try
CUDA versions per pod freely.

## Run a GPU workload

A pod gets the GPU with the GPU limit and the `nvidia` runtime. The toleration below was needed while the onboarding
taint was on (until 2026-11-17); it is harmless now and the existing manifests keep it:

```yaml
spec:
  runtimeClassName: nvidia
  tolerations:
    - {key: weyland.lab/onboarding, operator: Exists, effect: NoSchedule}
  containers:
    - name: app
      image: docker.io/nvidia/cuda:12.8.1-base-ubuntu24.04   # CUDA 12.8 is the first with Blackwell support
      resources:
        limits: {nvidia.com/gpu: 1}
```

The device plugin
([k8s/nvidia-device-plugin/values.yaml](../../nodes/mother/lab/weyland-platform/k8s/nvidia-device-plugin/values.yaml),
Argo app `nvidia-device-plugin`) advertises the card **time-sliced into 4** (2026-11-14), so `nvidia.com/gpu: 1` is one
slice and the node offers 4. A request for 2 or more slices is rejected (`failRequestsGreaterThanOne`).

Check what the node offers (expect `4`):

[rogueone]
```
kubectl get node timberback -o jsonpath='{.status.allocatable.nvidia\.com/gpu}{"\n"}'
```

## GPU sharing and the VRAM budget

Time-slicing shares the GPU's compute, **not its memory**: every pod sees all 16 GB of VRAM, and nothing stops two
pods from asking for more than exists between them. The one that allocates last fails with a CUDA out-of-memory error.
So every GPU workload has a VRAM budget here, and a new one is checked against the total before it lands:

| Workload | Slice | VRAM budget | Source |
|---|---|---|---|
| whisper (ggml-large-v3, `k8s/whisper/`) | 1 | 4.0 GB (measured 2026-11-14: 4,024 MiB) | B134 plan step 2 |
| llama-guard (Llama-Guard-3-1B Q8_0, `k8s/llama-guard/`) | 1 | 1.7 GB (measured 2026-11-17 on rogueone with the same image: 1,720 MiB; re-measure here) | B134 follow-up |
| (free) | 2 | ~10.2 GB of 15.9 GB | |

Measure the real figure once a workload is running and update its row (check `nvidia-smi` on timberback, which lists
each process's memory):

[timberback]
```
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

## GPU benchmark (B134, 2026-11-17)

What this card actually does, measured with llama.cpp's `llama-bench` (build b12033, native `sm_120a` code) on one GPU
time-slice beside whisper (4 GB of VRAM in use). One-off Job `nodes/timberback/checks/gpu-bench.yaml` (applied by hand,
deleted after; it downloads both models, checks their SHA-256, and runs the benchmark), 18 minutes end to end.

| Model | Placement | Prompt (512 tokens) | Generation |
|---|---|---|---|
| Qwen3-8B Q4_K_M (4.7 GiB) | fully on the GPU | 7,506 tokens/s | **149 tokens/s** |
| Llama-3.3-70B-Instruct Q4_K_M (39.6 GiB) | CPU only (`-ngl 0`, 16 threads) | 194 tokens/s | **1.4 tokens/s** |
| Llama-3.3-70B-Instruct Q4_K_M | 18 layers on the GPU | 235 tokens/s | **1.8 tokens/s** |

A model that fits in VRAM is fast; a 70B does not fit in 16 GB and is memory-bandwidth bound (nearly all of it is in
system RAM, read once per generated token), so it runs but is impractical for chat. The useful range for this card is
models up to roughly the low teens of billions of parameters at 4-bit, within the VRAM budget above.

Re-run after a driver, CUDA or llama.cpp change (the Job's image is pinned by digest; bump it deliberately):

[rogueone]
```
kubectl apply -f /home/edwardmangini/IdeaProjects/weyland/nodes/timberback/checks/gpu-bench.yaml
```

[rogueone]
```
kubectl -n weyland logs -f job/timberback-gpu-bench -c bench
```

[rogueone]
```
kubectl -n weyland delete job timberback-gpu-bench
```

## The onboarding taint

timberback joined with `weyland.lab/onboarding=true:NoSchedule`. **Lifted 2026-11-17.** Every workload not pinned to
mother may now schedule here. Removing the taint moves nothing at once; a pod moves only when it is next scheduled
(a rollout, a restart, a CronJob run), and the scheduler favours the emptier node, so unpinned pods drift here
over time.

**The pre-lift check (re-run 2026-11-17 against the live cluster):** 167 workloads. 15 are pinned by a node
selector, and 44 are held on mother by local-path volumes bound to it. Of the 108 free to move, every image comes from
a registry timberback pulls from. No free workload uses a host path, host networking or a host port. Two broke the
rules, and both are now pinned to mother:

| Workload | Why it must stay on mother |
| -- | -- |
| `data-mesh/valkey` | `valkey-lan` is a Local-policy NodePort, so it answers only on its pod's node; clients dial `192.168.1.243:30379` |
| `weyland/mlflow` | `mlflow-lan` (`:30500`) is the same; the Ray worker dials mother. Moving mlflow is a separate owner decision |

Off the cluster, pods on timberback arrive from `192.168.1.233`. rogueone's firewall
(`nodes/rogueone/ufw/rogueone-ufw.sh`) now admits it on 11434 (Ollama) and on 8765 (Basic Memory). Apply that on
rogueone before lifting the taint.

**Found on the lift:** DaemonSets that did not tolerate the taint scheduled a pod on timberback at once. For Alloy that
was wrong: it tails every pod through the Kubernetes API, so a second Alloy pod ships every log line twice. Alloy is
pinned to mother (`k8s/loki/alloy-values.yaml`), and that one pod still collects both nodes' logs.

**Caveats that stay:**

- A new Local-policy NodePort, host path, host network or host port needs a node selector for mother. The same goes
  for an off-cluster allowlist that admits only `192.168.1.243`.
- The default `local-path` storage class (`WaitForFirstConsumer`) creates a NEW volume on whichever node its pod
  lands on. A new stateful workload needs a deliberate placement: a node selector for mother, or a decision that its
  data lives on timberback.

To lift the taint (done 2026-11-17):

[rogueone]
```
kubectl taint node timberback weyland.lab/onboarding=true:NoSchedule-
```

The `node-taint` entry is gone from `nodes/timberback/host/rancher/k3s/config.yaml`. Install that file with the
command in § k3s agent, so the live config matches git and no restart can put the taint back. Then confirm the node
has no taints (prints `[]` or nothing):

[rogueone]
```
kubectl get node timberback -o jsonpath='{.spec.taints}'
```

## Cross-node canary

Proves a pod on timberback can reach services on mother through flannel, the Istio sidecar and NetworkPolicy. Run it
before pinning anything to timberback, and again after a k3s, flannel or Istio change. **Passed 2026-11-14.**

The manifest is `nodes/timberback/checks/timberback-canary.yaml` (a sidecar-injected pod in `data-mesh`, pinned to
timberback, tolerating the onboarding taint, deleted after; Argo does not manage it).

[rogueone]
```
kubectl apply -f /home/edwardmangini/IdeaProjects/weyland/nodes/timberback/checks/timberback-canary.yaml && kubectl -n data-mesh wait --for=condition=Ready pod/timberback-canary --timeout=240s
```

[rogueone]
```
kubectl -n data-mesh exec timberback-canary -c canary -- sh -c 'curl -s -o /dev/null -w "gms %{http_code}\n" http://datahub-datahub-gms.data-mesh:8080/health; curl -s -o /dev/null -w "bifrost %{http_code}\n" http://bifrost.weyland:8080/health; curl -sk -o /dev/null -w "trino-8443 %{http_code}\n" https://trino.data-mesh:8443/v1/info; curl -s -o /dev/null -m 6 -w "trino-8080 %{http_code}\n" http://trino.data-mesh:8080/v1/info'
```

[rogueone]
```
kubectl -n data-mesh delete pod timberback-canary
```

Pass: `gms 200`, `bifrost 200`, `trino-8443 200`, and `trino-8080` NOT 200 (503: the policy admits only Traefik on
8080, so a 200 there means NetworkPolicy is not enforced). Then confirm the mesh call was mutual TLS in Prometheus:
`istio_requests_total{source_workload="timberback-canary", destination_workload="datahub-datahub-gms", reporter="destination"}`
carries `connection_security_policy="mutual_tls"`.

## k3s agent

Apply a changed config from the repo:

[rogueone]
```
rsync -a /home/edwardmangini/IdeaProjects/weyland/nodes/timberback/host/rancher/k3s/config.yaml emangini@timberback:/tmp/ && ssh -t emangini@timberback 'sudo install -m 0644 /tmp/config.yaml /etc/rancher/k3s/config.yaml && sudo systemctl restart k3s-agent && systemctl is-active k3s-agent'
```

Logs:

[timberback]
```
sudo journalctl -u k3s-agent --no-pager -n 100
```

needrestart never restarts `k3s-agent` (`/etc/needrestart/conf.d/weyland-k3s.conf`, from
`nodes/timberback/host/needrestart/`). Verify it:

[timberback]
```
sudo needrestart -r l -u NeedRestart::UI::stdio 2>&1 | grep -iE "Services to be restarted|restarts being deferred|k3s"
```

`registry.weyland.lab` resolves through `/etc/hosts` (`192.168.1.243`); the router does not serve `*.weyland.lab`.

LAN name: `timberback.weyland.lab` -> `192.168.1.233` has its own zone in the LAN DNS on mother
(`nodes/mother/lab/weyland-platform/k8s/coredns-lan.yaml`), which overrides the `*.weyland.lab` -> mother wildcard. Check:
`dig +short @mother timberback.weyland.lab` prints `192.168.1.233`.

## Rebuild from scratch

timberback is a replaceable worker; its state lives on mother. To rebuild it:

1. Boot the Ubuntu **24.04.5 server** USB. Its installer kernel (6.8) shows **no network interface** (the RTL8126):
   choose **Skip networking**.
2. Storage: custom layout, NVMe as boot device (creates `/boot/efi`), the rest **btrfs** at `/`. Name `timberback`,
   user `emangini`, install OpenSSH.
3. First boot: install the HWE 7.0 kernel **from the stick** (mount it at `/mnt`), then reboot:
   `sudo apt install /mnt/pool/main/l/linux-*hwe-7.0/linux-{image,modules}-7.0.0-*-generic_*.deb`
4. Static IP in `/etc/netplan/50-cloud-init.yaml` (`eno1`, `192.168.1.233/24`, gateway and DNS `192.168.1.1`), and
   disable cloud-init's network config (`/etc/cloud/cloud.cfg.d/99-disable-network-config.cfg`).
5. Convert btrfs to the subvolume layout above (snapshot `/` into `@`, create the others, move `/home` and
   `/var/log` in, write `fstab` with `subvol=` entries, reinstall GRUB from a chroot into `@`, set `@` as default),
   then reboot and delete the leftovers at the top level.
6. snapper (`TIMELINE_CREATE=no`, `NUMBER_LIMIT=20`), `apt full-upgrade`, `linux-generic-hwe-24.04`, purge the 6.8
   kernels, the NVIDIA packages above, `update-initramfs -u -k all`, reboot, hold the kernel + NVIDIA set.
7. The needrestart override and the k3s config files from `nodes/timberback/host/`; the `/etc/hosts` registry line.
8. Join: the agent token streamed from mother (never printed), then the `get.k3s.io` installer pinned to mother's
   version with `INSTALL_K3S_EXEC=agent`, `K3S_URL=https://192.168.1.243:6443`, `K3S_TOKEN_FILE`.
9. NVIDIA container toolkit (NVIDIA's apt repository), pinned and held; restart `k3s-agent`.
