# Run timberback as a bare-metal Ubuntu k3s worker on btrfs, not under Proxmox

## Status

accepted

Date: 2026-11-14

## Context and Problem Statement

timberback is the lab's new machine: AMD Ryzen 9 9950X (16C/32T), 96 GB RAM, an NVIDIA GeForce RTX 5070 Ti 16 GB plus
the CPU's AMD iGPU, a 4 TB NVMe (verified over SSH, 2026-11-14). It joins the k3s cluster as a second node and runs
GPU AI workloads. NVIDIA driver and CUDA experimentation is expected. How should it be installed?

(The Strix Halo box that B134 described as bought was never purchased; timberback is the real hardware.)

## Decision Drivers

* Everything planned for it runs as Kubernetes pods.
* NVIDIA driver changes are expected and need a rollback; CUDA versions vary per container image.
* The cluster is short of RAM and CPU (B134); the node should give it as much as possible.
* Simplicity: fewer layers to patch and debug.
* The lab's own history (below).

## Considered Options

* Bare-metal Ubuntu 24.04 on btrfs (snapshots via snapper), a k3s worker, the GPU through NVIDIA's device plugin
* Proxmox VE with the RTX 5070 Ti passed through to a k3s worker VM (a standalone host, or clustered with weyland plus a QDevice)
* Bare-metal Ubuntu on ext4 as first installed (driver rollback by reinstalling packages)

## Decision Outcome

Chosen option: "Bare-metal Ubuntu 24.04 on btrfs", because it gives driver-change rollback with one layer instead of
two, hands all 96 GB and 32 threads to Kubernetes, and avoids the VM-layer pain the lab has already paid for.

### Consequences

* Good, because a snapshot before every driver change makes a bad driver a reboot into the old snapshot, not a manual
  recovery.
* Good, because there is no VM sizing to guess and re-guess (mother's RAM was regrown 16 → 78 GB and still hit walls),
  no CPU-type default to trip on (`qemu64` without AVX caused SIGILLs), and no GPU passthrough or reset quirks.
* Bad, because a rollback rewinds the whole node and needs a reboot; the node leaves the cluster briefly.
* Bad, because there is no separate "driver lab" VM next to the worker; drivers are tested on the node, behind a snapshot.
* Bad, because a hard hang takes the whole node and timberback has no remote power control: someone must be at the box.
* Required from day one:
  * `/var/lib/rancher` (k3s) and the container image store in their own btrfs subvolumes, outside the root snapshots,
    so a rollback rewinds the OS and driver but not the node's cluster state or images;
  * the NVIDIA driver packages held, with a drift check (the rogueone lesson);
  * a needrestart override so automatic upgrades never restart k3s (the mother lesson);
  * stateful stores stay pinned to mother (btrfs copy-on-write suits database files poorly).

## More Information

Lab history that weighed in (shared agent memory): `proxmox-vm-cpu-host-avx`, `mother-ram-ceiling-hydrate-reliability`,
`istiod-request-node-wall`, `weyland-usb-uas-quirk`, `unattended-upgrades-nvidia-driver-drift`,
`needrestart-restarts-k3s`, `rogueone-gpu-freeze-vram`, `strix-halo-never-purchased`.

Revisit if a real need for a separate VM appears (another OS, an isolated driver lab running next to the worker); moving
to Proxmox is a reinstall of a replaceable worker node. Mother's own disk is ext4 on a ZFS volume on weyland, so Proxmox
snapshots it; timberback gets the same capability in one layer through btrfs.
