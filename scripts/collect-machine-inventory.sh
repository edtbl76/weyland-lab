#!/usr/bin/env bash
# collect-machine-inventory.sh — the canonical machine-inventory collector (B129).
#
# Gathers the installed-software inventory of one lab machine and prints it NORMALIZED to stdout, one
# record per line:  <kind>\t<name>\t<version>   (kind = snap|flatpak|apt|pip|npm|image|appimage|uv-tool).
#
# It is OUTPUT-ONLY: it reads nothing but the machine's own package managers and writes nothing on the
# host. The curated decisions (keep/remove/rationale) live in `machine-inventory.yaml`; `machine_inventory.py
# merge` folds this raw output into that SoT (new items land status: unreviewed; the system apt baseline is
# bulk-tagged status: system). See docs/runbooks/machine-inventory.md.
#
#   usage: scripts/collect-machine-inventory.sh <host>      # rogueone | mother | weyland | <hostname>
#          scripts/collect-machine-inventory.sh <host> | scripts/machine_inventory.py merge <host>
#
# The host is collected LOCALLY when it is this box, else over SSH as emangini@<host> (hostname, not IP —
# see feedback-ssh-conventions). Each collector is tolerant: a package manager that is not installed is
# skipped (a note to stderr), never a silent empty success — the header line reports which sources ran.
set -euo pipefail

host="${1:?usage: collect-machine-inventory.sh <host>   (rogueone | mother | weyland | <hostname>)}"

# The gather snippet runs identically local or remote. It emits <kind>\t<name>\t<version> and, to stderr,
# a "sources:" note naming every collector that actually ran — so an absent tool is visible, not a silent gap.
read -r -d '' GATHER <<'SNIPPET' || true
ran=""
if command -v snap >/dev/null 2>&1; then
  snap list 2>/dev/null | awk 'NR>1 && NF{printf "snap\t%s\t%s\n",$1,$2}'; ran="$ran snap"
fi
if command -v flatpak >/dev/null 2>&1; then
  flatpak list --app --columns=application,version 2>/dev/null | awk -F'\t' 'NF{printf "flatpak\t%s\t%s\n",$1,$2}'; ran="$ran flatpak"
fi
if command -v apt-mark >/dev/null 2>&1; then
  apt-mark showmanual 2>/dev/null | xargs -r dpkg-query -W -f='apt\t${Package}\t${Version}\n' 2>/dev/null; ran="$ran apt"
fi
if command -v pip3 >/dev/null 2>&1; then
  pip3 list --format=freeze 2>/dev/null | awk -F'==' 'NF==2{printf "pip\t%s\t%s\n",$1,$2}'; ran="$ran pip"
fi
if command -v npm >/dev/null 2>&1; then
  npm ls -g --depth=0 --parseable 2>/dev/null | while IFS= read -r d; do
    b="${d##*/}"; [ "$b" = "node_modules" ] || [ "$b" = "lib" ] || [ -z "$b" ] && continue
    printf 'npm\t%s\t\n' "$b"
  done; ran="$ran npm"
fi
if command -v docker >/dev/null 2>&1; then
  docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -v '<none>' | while IFS= read -r i; do
    printf 'image\t%s\t%s\n' "${i%:*}" "${i##*:}"; done; ran="$ran image(docker)"
elif command -v crictl >/dev/null 2>&1; then
  crictl images 2>/dev/null | awk 'NR>1 && NF{printf "image\t%s\t%s\n",$1,$2}'; ran="$ran image(crictl)"
elif command -v ctr >/dev/null 2>&1; then
  ctr -n k8s.io images ls -q 2>/dev/null | while IFS= read -r i; do
    printf 'image\t%s\t%s\n' "${i%:*}" "${i##*:}"; done; ran="$ran image(ctr)"
fi
# User-space installs no package manager lists (2026-10-12: Emdash, Cursor, LM Studio and the basic-memory uv tool
# had never been cataloged). AppImages: ~/Applications/*.AppImage (a *.part download is not an install). The name and
# version come from the file name: AppImageLauncher's _<32-hex> suffix and a trailing arch are dropped, and the
# version is the first -<digit>... segment ("emdash-1.2.7-x86_64" → emdash 1.2.7; "bruno_<hex>" → bruno, no version).
if [ -d "$HOME/Applications" ]; then
  for f in "$HOME"/Applications/*.AppImage; do
    [ -e "$f" ] || continue
    b="${f##*/}"; b="${b%.AppImage}"
    b="$(printf '%s' "$b" | sed -E 's/_[0-9a-f]{32}$//; s/[._-](x86_64|x64|amd64)$//')"
    name="$(printf '%s' "$b" | sed -E 's/-[0-9].*$//')"
    ver="${b#"$name"}"; ver="${ver#-}"
    printf 'appimage\t%s\t%s\n' "$name" "$ver"
  done; ran="$ran appimage"
fi
# uv tools (`uv tool install`): `uv tool list` prints "<name> v<version>" then "- <entry point>" lines, and bolds the
# name with ANSI escapes EVEN WHEN PIPED (observed 2026-10-12: the first run cataloged "\e[1mbasic-memory"), so strip them.
if command -v uv >/dev/null 2>&1; then
  uv tool list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk '!/^-/ && NF>=2 {v=$2; sub(/^v/,"",v); printf "uv-tool\t%s\t%s\n",$1,v}'; ran="$ran uv-tool"
fi
printf 'sources:%s\n' "${ran:- NONE}" >&2
SNIPPET

# SSH user per host: weyland (the Proxmox host) has no `emangini` account → root; every other box → emangini
# (feedback-ssh-conventions). Override for a new client with MACHINE_INV_SSH_USER.
case "$host" in
  weyland) sshuser="root" ;;
  *)       sshuser="emangini" ;;
esac
sshuser="${MACHINE_INV_SSH_USER:-$sshuser}"

# Tag the stream with the host being collected — the merge/emit step verifies this matches its own target
# and fails closed on a mismatch, so `collect <A> | merge <B>` can never silently mislabel A's inventory as B.
printf 'host:%s\n' "$host"

# Local when the target names this box (hostname or the rogueone dev workstation); else SSH.
this="$(hostname -s 2>/dev/null || hostname)"
if [ "$host" = "$this" ] || { [ "$host" = "rogueone" ] && [ "$this" = "rogueone" ]; }; then
  printf 'collecting %s locally...\n' "$host" >&2
  bash -c "$GATHER"
else
  printf 'collecting %s over ssh (%s@%s)...\n' "$host" "$sshuser" "$host" >&2
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$sshuser@$host" "$GATHER"
fi
