#!/usr/bin/env bash
# B165 — provision the throwaway Kindle-extraction VM on rogueone, fully unattended. "Log in once, script the
# rest": this builds + installs Windows + self-installs the toolchain with NO clicks; your ONLY manual step is
# signing into Kindle-for-PC once the desktop is up (then extraction auto-fires and uploads to MinIO).
#
#   bash nodes/rogueone/kindle/provision-kindle-vm.sh          # first time: build the VM
#   bash nodes/rogueone/kindle/provision-kindle-vm.sh --rerun  # later (new books): start the persisted VM,
#                                                              # which re-syncs (Kindle stays signed in) + re-extracts
#
# ONE-TIME prerequisites the first time (printed + checked below; not per-extraction work):
#   1. sudo apt install -y virtinst genisoimage libvirt-daemon-system   (VM tooling — rogueone has virsh/qemu/swtpm)
#   2. the Windows 11 Enterprise Evaluation ISO (Microsoft gates it behind a browser) saved to $ISO — get it at
#      https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise
#   3. MinIO S3 creds in scripts/.env (KINDLE_MINIO_ACCESS_KEY / KINDLE_MINIO_SECRET_KEY) so the VM can upload.
set -euo pipefail

# SESSION libvirt (qemu:///session) — QEMU runs as this user, so it can read the ISOs + disk under $HOME with no
# root and no perms grants (the system connection's `libvirt-qemu` user cannot traverse a 700 home dir). Every
# virt-install/virsh call in this script inherits it via the env var, matching the virt-viewer session connection.
export LIBVIRT_DEFAULT_URI="qemu:///session"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$REPO_ROOT/nodes/rogueone/kindle"
VM="${KINDLE_VM_NAME:-kindle-extract}"
WORK="${KINDLE_VM_WORK:-$HOME/kindle-vm}"
ISO="${KINDLE_WIN_ISO:-$WORK/Win11_Eval.iso}"
MINIO_ENDPOINT="${KINDLE_MINIO_ENDPOINT:-http://192.168.1.243:30990}"   # the LAN MinIO S3 NodePort (minio-s3-lan.yaml)
BUCKET="${KINDLE_MINIO_BUCKET:-kindle-corpus}"
mkdir -p "$WORK"

say() { printf '== %s\n' "$*"; }
die() { printf '!! %s\n' "$*" >&2; exit 1; }

CFG_ISO="$WORK/kindle-config.iso"

# (Re)build the config ISO from the CURRENT scripts here + the MinIO creds in scripts/.env. Used by the first-run
# create AND by --refresh-iso (so a fix to the in-guest scripts can be pushed without recreating the VM).
build_config_iso() {
  # shellcheck disable=SC1091
  [ -f "$REPO_ROOT/scripts/.env" ] && { set -a; . "$REPO_ROOT/scripts/.env"; set +a; }
  local ak="${KINDLE_MINIO_ACCESS_KEY:-${AWS_ACCESS_KEY_ID:-}}"
  local sk="${KINDLE_MINIO_SECRET_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"
  [ -n "$ak" ] || die "no MinIO S3 key - set AWS_ACCESS_KEY_ID (or KINDLE_MINIO_ACCESS_KEY) in scripts/.env"
  [ -n "$sk" ] || die "no MinIO S3 secret - set AWS_SECRET_ACCESS_KEY (or KINDLE_MINIO_SECRET_KEY) in scripts/.env"
  say "building the unattended config ISO"
  local stage; stage="$(mktemp -d)"
  cp "$HERE/autounattend.xml" "$HERE/kindle-bootstrap.cmd" \
     "$HERE/kindle-vm-setup.ps1" "$HERE/kindle-extract.ps1" "$HERE/kindle-autorun.ps1" "$stage/"
  cat > "$stage/kindle-minio.env" <<EOF
MINIO_ENDPOINT=$MINIO_ENDPOINT
MINIO_BUCKET=$BUCKET
MINIO_ACCESS_KEY=$ak
MINIO_SECRET_KEY=$sk
EOF
  genisoimage -quiet -J -r -V KINDLECFG -o "$CFG_ISO" "$stage"
  rm -rf "$stage"
  say "config ISO: $CFG_ISO"
}

# --refresh-iso: rebuild the config disc from the CURRENT (edited) scripts and HOT-SWAP it into the running VM,
# so a fix to the in-guest scripts reaches the VM without recreating it. Then re-run the bootstrap in the guest.
if [ "${1:-}" = "--refresh-iso" ]; then
  virsh dominfo "$VM" >/dev/null 2>&1 || die "VM '$VM' does not exist - run without a flag first."
  build_config_iso
  if virsh change-media "$VM" sdc "$CFG_ISO" --update; then
    say "swapped the fresh config disc into '$VM' (drive sdc)"
  else
    die "change-media failed - the config CD may not be sdc (check: virsh domblklist $VM)"
  fi
  say "now RE-RUN the bootstrap in the VM: File Explorer -> KINDLECFG drive -> right-click kindle-bootstrap.cmd -> Run as administrator"
  exit 0
fi

# --rerun: the VM already exists (Kindle still signed in) → just start it; the in-guest autorun re-extracts.
if [ "${1:-}" = "--rerun" ]; then
  virsh dominfo "$VM" >/dev/null 2>&1 || die "VM '$VM' does not exist yet — run without --rerun first."
  say "starting persisted VM '$VM' — it re-syncs the library and auto-extracts new books to MinIO $BUCKET"
  virsh start "$VM" 2>/dev/null || say "VM already running"
  say "watch the desktop (virt-viewer --connect qemu:///session $VM); nothing else to do — extraction is automatic."
  exit 0
fi

# 1) tooling prereqs (one-time; a sudo apt, not extraction work)
for t in virt-install genisoimage; do
  command -v "$t" >/dev/null 2>&1 || die "missing '$t' — one-time: sudo apt install -y virtinst genisoimage libvirt-daemon-system, then re-run."
done
[ -e /dev/kvm ] || die "no /dev/kvm — enable virtualization."

# 2) the Windows ISO (Microsoft gates the download behind a browser — can't be curled)
[ -f "$ISO" ] || die "Windows 11 Eval ISO not found at $ISO
     One-time: download it (https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise) and save it there
     (or point KINDLE_WIN_ISO at it), then re-run."

# 3) Build the CONFIG ISO (autounattend + scripts + MinIO creds from scripts/.env) — creds resolved inside.
build_config_iso

# Create + install the VM: unattended Windows (the config ISO's autounattend drives it), vTPM for Win11, both ISOs.
say "creating VM '$VM' (6GB / 4 vCPU / 64GB disk, vTPM) — unattended Windows install begins now"
virt-install \
  --name "$VM" \
  --osinfo win11 \
  --ram 6144 --vcpus 4 \
  --disk path="$WORK/$VM.qcow2",size=64,format=qcow2,bus=sata \
  --cdrom "$ISO" \
  --disk path="$CFG_ISO",device=cdrom \
  --tpm backend.type=emulator,backend.version=2.0,model=tpm-crb \
  --boot uefi \
  --network user,model=e1000e \
  --graphics spice \
  --noautoconsole

cat <<EOF

== VM '$VM' is installing Windows unattended (several minutes; no clicks).
   Watch it:   virt-viewer --connect qemu:///session $VM     (or virt-manager)
   The setup log inside the guest is C:\\kindle\\setup.log.

   YOUR ONE STEP: when the Windows desktop is up and Kindle-for-PC opens, sign into Amazon (2FA).
   Everything else is automatic: the toolchain self-installs, the library syncs, and kindle-autorun.ps1
   extracts + uploads to MinIO $BUCKET on its own.

   Later, for new books:  bash $0 --rerun   (starts the VM; Kindle stays signed in; re-extracts, zero-touch).
EOF
