# B6 — MinIO Object Storage (8TB USB → mother VM passthrough)

S3-compatible object storage for the lab (model artifacts, datasets, backups, LLM/data-mesh
artifacts). Backed by an **8TB USB drive physically attached to weyland** (the bare-metal
Proxmox host), with the MinIO partition **passed through to the mother VM** where k3s runs.

Commands run on **weyland** (Proxmox host) or **mother** (k3s VM) as noted.

---

## Storage path (how the bytes flow)

```
Seagate 8TB USB  ──┬─ sda1 (XFS, LABEL=minio)  ──[qm raw passthrough]──►  mother VM: /dev/sda
   on weyland      │                                                       └─ mount /mnt/minio
   (Proxmox host)  │                                                          └─ MinIO data dir (k3s local PV)
                   │
                   └─ sda2 (ext4, LABEL=data)  ──[stays on host]──►  weyland: /mnt/data
                                                                       └─ Music/ + linux-backup/
```

- `sda1` → MinIO (in the VM). `sda2` → Music + Linux backups (on the host).
- Only `sda1` crosses into the VM; `sda2` stays on weyland so it can later be re-exported
  (Samba/NFS) for rogueone backups.

---

## Key decision: raw partition passthrough, NOT Proxmox-managed storage

**Decision (2026-06-10):** the MinIO partition (`sda1`) is handed to the mother VM as a
**raw block device** via `qm set 101 -scsi0 /dev/disk/by-id/...-part1`. Proxmox only records
the device path — it does **not** wrap the disk in a managed storage (no Directory store, no
zvol, no disk image). The XFS filesystem we created on the host *is* the MinIO data store,
seen directly inside the guest.

### Options considered

| Option | What it is | Verdict |
|---|---|---|
| **Raw partition passthrough** (chosen) | `qm set … /dev/disk/by-id/…-part1`; guest gets the bare XFS partition | ✅ Chosen |
| Proxmox-managed storage | Make `sda1` a Directory/LVM/ZFS storage, allocate a VM disk image on it, attach that | ❌ Rejected for this workload |

### Why passthrough (rationale)

1. **Performance on a slow disk.** This drive sustains only ~24 MB/s on writes (measured
   during the Music restore). Wrapping it in a Proxmox storage layer (a raw/qcow2 image on a
   Directory store, or a zvol) stacks a second filesystem/image format on top — more overhead
   and write amplification on a disk that is already the bottleneck. Passthrough is the leanest
   path.
2. **The hypervisor's value-adds are moot or unwanted here.**
   - *Live migration:* impossible regardless — the disk is physically USB-attached to weyland,
     so the VM cannot migrate off weyland with it either way.
   - *Snapshots / vzdump backup:* we do **not** want Proxmox snapshotting or backing up a 4 TB
     object store. MinIO owns its own data; backups belong at the bucket/object layer, not the
     hypervisor. (The passthrough disk is tagged `backup=0` so `vzdump` skips it.)
   - *Thin provisioning:* an object store fills with real bytes — little to thin.
3. **Portability.** The XFS filesystem *is* the MinIO data — unplug the drive and read it on
   any Linux box. No nested image format to extract.

### Consequences accepted

- This disk is **not** visible/managed in the Proxmox storage UI, gets **no** Proxmox
  snapshots, and is **not** in `vzdump` backups. (Acceptable: MinIO data is reproducible
  artifact storage, backed up at the object layer if needed.)
- The mother VM is effectively **pinned to weyland** while this disk is attached (already true
  — the drive is USB-local to weyland).
- Storage management is manual (mount + fstab in the guest), documented below.

---

## Hard dependency: the UAS quirk (drive stalls without it)

The drive is a **Seagate Backup+ Hub** (USB `0bc2:ab38`, internal disk `ST8000DM004`,
WWN `0x5000c500c67e302c`). On the kernel `uas` (USB Attached SCSI) driver it **silently
stalls mid-transfer under sustained load** — the transfer freezes with no error in dmesg or
app logs, and the process dies. This cost hours of debugging during setup.

**Fix (persistent, applied on weyland):** `/etc/modprobe.d/usb-storage-quirks.conf`:
```
options usb-storage quirks=0bc2:ab38:u
```
The `u` (IGNORE_UAS) flag forces the stable bulk-only `usb-storage` transport. Confirm a
healthy bind in dmesg after plugging the drive in:
```bash
dmesg -T | grep -i 'uas\|usb-storage'   # want: "UAS is ignored for this device, using usb-storage instead"
```
Tradeoff: slower (writes ~24–70 MB/s) but does not stall. If a transfer on this drive ever
freezes silently, first check it is not on `uas`. Also watch for
`Cannot enable. Maybe the USB cable is bad?` (flaky-link warning — try a different port/cable).

---

## Disk layout (8TB repartitioned 2026-06-10, GPT)

| Partition | Size | FS | LABEL | UUID | Role |
|---|---|---|---|---|---|
| `sda1` | ~3.9 TiB (4000 GiB) | XFS | `minio` | `d25597f5-357f-4722-8dbf-c8f310b1d242` | MinIO object store (→ mother VM) |
| `sda2` | ~3.4 TiB | ext4 | `data` | `2d5f4cc1-3525-45ae-9b7d-5e51b81b109f` | Music + Linux backups (on weyland host) |

`sda2` ext4 made with `-m 1` (1% root reserve instead of 5%, reclaiming ~135 GB on a pure
data volume). `/mnt/data` holds `Music/` (~500 GB, static) and `linux-backup/` (Timeshift +
DejaDup + rogueone, ~205 GB, hardlink-based).

---

## Setup runbook

### 1. (weyland) UAS quirk — see "Hard dependency" above
Create the modprobe drop-in, then re-plug the drive (no reboot needed):
```bash
echo 'options usb-storage quirks=0bc2:ab38:u' > /etc/modprobe.d/usb-storage-quirks.conf
echo 0bc2:ab38:u > /sys/module/usb_storage/parameters/quirks   # apply to running kernel
# physically unplug + replug the drive, then verify it bound to usb-storage (not uas)
```

### 2. (weyland) Partition + format
```bash
sgdisk --zap-all /dev/sda
sgdisk -n 1:0:+4000G -t 1:8300 -c 1:minio -n 2:0:0 -t 2:8300 -c 2:data /dev/sda
blockdev --rereadpt /dev/sda            # partprobe is not installed on this host
wipefs -a /dev/sda1 /dev/sda2
mkfs.xfs  -f -L minio /dev/sda1
mkfs.ext4 -F -m 1 -L data /dev/sda2
```

### 3. (weyland) Mount the data partition + persist
```bash
mkdir -p /mnt/data
echo 'UUID=2d5f4cc1-3525-45ae-9b7d-5e51b81b109f /mnt/data ext4 defaults,nofail,x-systemd.device-timeout=30 0 2' >> /etc/fstab
systemctl daemon-reload
mount /mnt/data
```
`nofail` is essential for a USB fstab entry — without it a missing/slow drive drops the host
into emergency mode at boot.

### 4. (weyland) Pass sda1 through to the mother VM (vm 101)
```bash
qm set 101 -scsi0 /dev/disk/by-id/wwn-0x5000c500c67e302c-part1,backup=0
qm config 101 | grep scsi0   # confirm: scsi0: /dev/disk/by-id/wwn-...-part1,backup=0,size=4000G
```
- Uses the **WWN by-id** path (stable hardware id; avoids the `+`/`:` shell-escaping in the
  `usb-Seagate_Backup+_Hub…` name). All of `wwn-…-part1`, `ata-ST8000DM004…-part1`, and
  `usb-Seagate…-part1` point to the same `sda1`.
- `backup=0` keeps `vzdump` from trying to dump the 4 TB store.
- VM 101 is `virtio-scsi-single` with disk hotplug on → the disk appears **live** in the guest,
  no VM restart. Inside the guest it shows as a whole-device XFS (e.g. `/dev/sda`, no partition
  table beneath it) because we passed the host's *partition* through as a raw disk.

### 5. (mother) Mount the MinIO disk + persist
```bash
sudo mkdir -p /mnt/minio
sudo blkid -L minio                     # confirm the guest sees the XFS (e.g. /dev/sda)
echo 'UUID=d25597f5-357f-4722-8dbf-c8f310b1d242 /mnt/minio xfs defaults,nofail,x-systemd.device-timeout=30 0 2' | sudo tee -a /etc/fstab
sudo systemctl daemon-reload
sudo mount /mnt/minio
df -h /mnt/minio
```

### 6. (mother) Deploy MinIO on k3s
Manifests: `nodes/mother/lab/weyland-platform/k8s/minio/` (namespace, pv, pvc, deployment,
service, ingress). Single-drive MinIO, RWO local PV → `/mnt/minio`, `strategy: Recreate`.

**Image:** `alpine/minio:RELEASE.2025-10-15T17-29-55Z` — upstream `minio/minio` was archived
(Oct 2025); `alpine/minio` is the maintained community rebuild of the same last release.

**Secrets (NOT committed):**
```bash
kubectl apply -f ~/lab/weyland-platform/k8s/minio/namespace.yaml
kubectl create secret generic minio-creds -n minio \
  --from-literal=MINIO_ROOT_USER=admin --from-literal=MINIO_ROOT_PASSWORD=weyland_dev_password
kubectl create secret tls weyland-wildcard-tls -n minio \
  --cert=$HOME/certs/weyland-wildcard.pem --key=$HOME/certs/weyland-wildcard-key.pem
kubectl apply -f ~/lab/weyland-platform/k8s/minio/
```

**GOTCHA — non-root write permission:** `alpine/minio` runs as **UID 1000**, but `/mnt/minio`
is `root:root`, so MinIO CrashLoops with `file access denied` creating `/data/.minio.sys`.
Fix: `sudo chown 1000:1000 /mnt/minio` on mother (the deployment pins `runAsUser: 1000`;
`fsGroup` does NOT apply to local PVs, so the on-disk chown is required).

**Validate (functional S3 round-trip):**
```bash
kubectl run mc -it --rm --restart=Never --image=minio/mc -n minio --command -- sh
# inside: mc alias set lab http://minio.minio.svc.cluster.local:9000 admin weyland_dev_password
#         mc mb lab/smoke ; echo hi | mc pipe lab/smoke/o ; mc cat lab/smoke/o ; mc rb --force lab/smoke
```

### 7. Web UI — Filestash (the MinIO console is dead)
**The MinIO community web console was stripped/removed in 2025** — login fails with a
"network error" by design. Do NOT chase it; `minio.weyland.lab` (console ingress) is a no-op.
Manage MinIO via `mc`/S3 API, and browse via **Filestash** instead.

Manifest: `k8s/minio/filestash.yaml` (`machines/filestash:latest`), at `https://files.weyland.lab`.
Reuses the `weyland-wildcard-tls` secret in the `minio` namespace. Config persists in the
`filestash-data` PVC.

Post-deploy (one-time, in the Filestash admin UI):
1. Set a Filestash admin password.
2. **Storage** → S3 backend; **Authentication Middleware** → `passthrough` → in the attribute
   mapping enter: Access Key `admin`, Secret `weyland_dev_password`,
   **Endpoint** `http://minio.minio.svc.cluster.local:9000`, Region `us-east-1`.
   (No path-style checkbox — Filestash auto-uses path-style when a custom Endpoint is set.)

**GOTCHA — scheme-doubled redirect / phantom NXDOMAIN:** do NOT set `APPLICATION_URL` to a full
URL, and ensure the persisted config's `general.host` is a **bare host** (`files.weyland.lab`,
no `https://`). With a scheme included, Filestash builds `http://https//files.weyland.lab`,
and the browser then tries to resolve a host literally named `https` → `DNS_PROBE_FINISHED_NXDOMAIN`
(which looks like a DNS problem but is not). The value lives in
`/app/data/state/config/config.json` in the PVC (env seeds it once, then the file wins).

## Access (day-to-day)
- **CLI (`mc`) from rogueone:** `mc alias set weyland https://s3.weyland.lab admin weyland_dev_password`,
  then `mc ls/cp/mirror weyland/<bucket>`. (Binary: `dl.min.io/client/mc/release/linux-amd64/mc`.)
- **Web browser:** `https://files.weyland.lab` (Filestash).
- **In-cluster workloads** (Dagster, tool server, etc.): S3 SDK → `http://minio.minio.svc.cluster.local:9000`.
- **External S3 endpoint** (you, from rogueone): `https://s3.weyland.lab` (TLS, trusted mkcert cert).
  Both `s3.weyland.lab` and `files.weyland.lab` need a `192.168.1.243` line in rogueone's `/etc/hosts`.

---

## Operational notes / gotchas

- **After a weyland reboot or drive re-plug:** the UAS quirk persists (modprobe.d), and the
  host `/mnt/data` re-mounts via fstab. The passthrough (`scsi0` in vm 101's config) persists
  too, so the guest disk returns on the next VM start. If the guest doesn't see it after a live
  re-plug, rescan in the guest: `for h in /sys/class/scsi_host/host*/scan; do echo '- - -' | sudo tee $h; done`.
- **Do not pass the whole `/dev/sda`** to the VM — only `…-part1`. The host keeps `sda2`
  mounted at `/mnt/data`; handing the whole disk to the guest would collide with that.
- **No Proxmox-level backup/snapshot of MinIO data** (by design — see decision above). Back up
  at the bucket/object layer if/when needed.
- **Slow drive:** ~24 MB/s sustained writes. Keep MinIO throughput expectations modest; this is
  a homelab artifact/model store, not a high-IOPS tier. Revisit the drive choice if it bites.
- **To unwind the passthrough:** `qm set 101 --delete scsi0` (then the disk is host-only again).

---

## Provenance
Set up 2026-06-10/11. Original drive contents (Music + Linux backups) were staged to
`rpool/usb-stage` on weyland, the drive repartitioned, and the data restored to `sda2`
(file-count verified). Staging reclaimed 2026-06-11 (`zfs destroy rpool/usb-stage`) after
MinIO + Filestash were validated. Data on `sda2` is adequately protected: Music is also backed
up to **Google Cloud**, and the Linux backups are redundant (rogueone holds the originals).
