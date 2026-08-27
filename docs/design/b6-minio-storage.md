# B6 — MinIO Object Storage: 8TB USB Repartition (Design + Live Execution State)

**Status**: IN PROGRESS — staging live data off the USB before repartition.
**Last updated**: 2026-06-10. This doc doubles as the crash-recovery checkpoint
(a laptop crash already cost us the in-flight context once — persist decisions here).

## Goal
Repartition the 8TB USB drive (`sda`) on the **weyland** Proxmox host to serve as the
storage substrate for MinIO (B6), while preserving the existing live data (Music + Linux
backups). MinIO must be reachable by the lab containers running in the mother VM (k3s).

## Topology constraint
- The 8TB USB (`sda`) is physically attached to **weyland** (the bare-metal Proxmox host).
- MinIO runs in **k3s inside the mother VM** (vm-101) on top of weyland.
- Therefore the MinIO-backing partition must be **passed through** weyland → mother VM,
  then mounted in the VM and exposed as a local PV for MinIO.

## Pre-state (before repartition) — captured 2026-06-09/10
`sda` = 7.3T USB, two partitions with LIVE DATA (repartition destroys both):
- `sda1` — 3.6T ext4, label "Linux Backup", `/mnt/usb1`, ~204G used:
  `DejaDupBackup/`, `timeshift/` (**hardlink-based**), `rogueone/`, `lost+found`, `.Trash-1000`
- `sda2` — 3.6T vfat ("Shared File"), `/mnt/usb2`, ~501G used: `Music/` (**static — never changes**)

## Data preservation — decision: PRESERVE BOTH (option A)
Stage both datasets to weyland local ZFS, then restore after repartition.
- Staging target: `rpool/usb-stage` → `/rpool/usb-stage` (dataset already existed pre-crash; rpool has ~1.53T avail).
- `usb1` (backups): `rsync -aH` (`-H` mandatory — Timeshift hardlinks, else copy balloons).
- `usb2` (Music): simpler flags (vfat source: no perms/owners/hardlinks).

## Approved partition layout (locked 2026-06-10)
| Part | Size | FS | Purpose | Lives on |
|---|---|---|---|---|
| `sda1` | ~4.0 TB | **XFS** | MinIO object storage (models, datasets, artifacts) | Passthrough → mother VM → MinIO local PV |
| `sda2` | ~3.3 TB | **ext4** | Music + Linux backups (restored from staging) | Stays mounted on weyland host |

Rationale: XFS = MinIO's recommended FS. Backups are hardlink/incremental *filesystem*
backups → cannot be S3 objects → stay on a real FS (`sda2`), not in MinIO. Only `sda1`
is passed to the VM; `sda2` stays on the host so it can later be re-exported (Samba/NFS)
for rogueone backups. Music is static → can be mounted read-only after restore.

## Diagnosis 2026-06-10 — staging rsync froze (UAS instability)
First staging rsync (started ~00:09, froze ~00:38 Jun 10) stopped at 47% / ~175G of ~204G
staged in `rpool/usb-stage` (resumable). Root cause: **USB/UAS link instability**, NOT:
weyland reboot (uptime 9d, booted May 31), OOM, disk-full, ext4/SCSI errors (dmesg clean),
or rsync bug (no error in log). Drive = **Seagate Backup+ Hub `0bc2:ab38`** on the `uas`
driver — a well-known stall-under-load combo; dmesg also showed `Cannot enable. Maybe the
USB cable is bad?`. **Decision (Plan A): disable UAS** via `usb-storage.quirks=0bc2:ab38:u`
(modprobe.d drop-in + runtime sysfs + re-plug, NO reboot so lab VMs stay up), then resume.
**Strategic flag:** a flaky USB link is a weak foundation for MinIO storage — stabilize the
link before committing the destructive repartition; possibly reconsider this drive for MinIO.

### Plan A recovery steps (no reboot)
1. Unmount `/mnt/usb1` + `/mnt/usb2` (clean, before unplug)
2. Write `/etc/modprobe.d/usb-storage-quirks.conf` → `options usb-storage quirks=0bc2:ab38:u`
3. Apply at runtime: `echo 0bc2:ab38:u > /sys/module/usb_storage/parameters/quirks`
4. Physically unplug → wait → replug
5. Verify dmesg shows usb-storage binding (no `scsi host: uas`); partitions reappear
6. Remount both; resume rsync (continues from ~175G)

## Execution sequence (checklist = crash-recovery state)
- [x] 1. Stage `usb1` backups → `/rpool/usb-stage/usb1-linux-backup/` — COMPLETE 2026-06-10 after UAS-disable (Plan A). Verified: zfs logicalused=202G (≈ source), used=175G @ 1.17x compression, rsync resume xfr#0 (nothing left). USB now on stable `usb-storage`; both partitions remounted `ro`.
- [x] 2. Stage `usb2` Music → `/rpool/usb-stage/usb2-shared/` — COMPLETE 2026-06-10. 76815 src == 76815 dst files (exact). ~500 GiB. Ran 71 min @ 119MB/s on usb-storage, no stall.
- [x] 3. Verify both staged copies — DONE. rpool/usb-stage: used=671G, logicalused=706G (~202 backups + ~504 Music), 1.05x. File counts matched. **Both copies safe; USB original still intact (not yet wiped).**
- [x] 4. Unmounted; repartitioned `sda` (GPT, sgdisk) 2026-06-10: sda1=3.9TiB PARTLABEL minio, sda2=3.4TiB PARTLABEL data. (partprobe absent → used `blockdev --rereadpt`.)
- [x] 5. Formatted: `sda1` XFS (LABEL minio), `sda2` ext4 (LABEL data, `-m 1` = 1% reserve). Confirmed via blkid.
- [x] 6. Restore COMPLETE 2026-06-10. sda2 mounted `/mnt/data` (3.3T free).
    - [x] 6a. Backups → `/mnt/data/linux-backup/` (rsync -aH). Verified 2533711 src == 2533711 dst files. NOTE: `-H` dataset shows ~47% in progress2 at completion (hardlinks move no bytes); `to-chk=0` = done. Run as a single rsync (the `sh -c '...&&...'` compound broke on paste — keep commands short).
    - [x] 6b. Music → `/mnt/data/Music/` (rsync -rt). Verified 76815 src == 76815 dst files. Slow restore: ~24MB/s avg / ~6h (drive's sustained write is modest — note for MinIO perf expectations).
    - Staged copies in `rpool/usb-stage` (671G) RETAINED for now — safe to delete only after the passthrough/MinIO phase is validated and you're confident.

## COMPLETE 2026-06-11 — durable runbook: docs/b6-minio-storage.md
- [x] sda2 `/mnt/data` in weyland `/etc/fstab` (UUID, nofail). Survives reboot.
- [x] 7. Passthrough `sda1` → mother VM (vm-101) `scsi0` via `wwn-...-part1,backup=0`. Appears as guest /dev/sda (whole-device XFS); mounted `/mnt/minio` (chown 1000:1000), fstab UUID.
- [x] 8. MinIO deployed: ns `minio`, `alpine/minio:RELEASE.2025-10-15...` (upstream archived), static local PV → /mnt/minio, RWO+Recreate, Traefik TLS s3.weyland.lab / minio.weyland.lab. Manifests k8s/minio/.
- [x] 9. Validated: S3 put/get/delete round-trip via `mc` (in-cluster + external https). 
- [x] UI: MinIO console is dead (community-stripped) → **Filestash** at files.weyland.lab (k8s/minio/filestash.yaml). `mc` on rogueone for CLI.
- [x] Cleanup: `zfs destroy rpool/usb-stage` DONE 2026-06-11 (reclaimed 671G; rpool back to 229G used / 1.53T free). /mnt/data verified intact before destroy. **sda2 is now the sole copy of Music** (backups are redundant via rogueone originals).
- [ ] Open items (non-destructive, future): re-export `/mnt/data` (Samba/NFS) for rogueone backups; optional read-only Music MinIO bucket.
- [ ] 7. Passthrough sda1 → mother VM (vm-101); mount in VM
- [ ] 8. Deploy MinIO on k3s (RWO + strategy: Recreate) backed by sda1 local PV
- [ ] 9. Validate: MinIO reachable from containers; data integrity on sda2

## Open items (later, non-destructive)
- Re-export `sda2` (Samba/NFS) so rogueone can resume backups to it.
- Optionally expose static Music as a read-only MinIO bucket (no FS disturbance).
- Passthrough method: pass `sda1` partition by stable `/dev/disk/by-id/...` path to vm-101.
