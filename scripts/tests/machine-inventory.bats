#!/usr/bin/env bats
# Tests for the machine-inventory decision-logic (B129 merge + B169 verify). The collector and `emit` are
# env-dependent (real package managers / SSH / the live Port API), so these exercise the parts that MAKE
# DECISIONS: `merge` (the host-mismatch guard — fail-closed regression for the 2026-09-14 mother/weyland
# mixup — the empty-stdin refusal, the baseline-vs-discretionary default status, and decision preservation)
# and `verify`'s read-back pass/fail gate. `verify` normally queries Port; its count comparison is tested
# offline via the MACHINE_INV_VERIFY_ACTUAL seam (same idiom as MACHINE_INV_SOT), so the fail-closed logic is
# covered without network. SoT path is overridden via MACHINE_INV_SOT so no fixture touches the real catalog.
# Needs python3 + pyyaml (CI shell-tests installs both).

setup() {
  TOOL="${BATS_TEST_DIRNAME}/../machine_inventory.py"
  TMP="$(mktemp -d)"
  export MACHINE_INV_SOT="$TMP/sot.yaml"
}
teardown() { rm -rf "$TMP"; }

status_of() {  # status_of <host> <kind> <name>  -> prints the package's status from the SoT
  python3 -c "
import yaml,sys
d=yaml.safe_load(open('$MACHINE_INV_SOT'))
for p in d['hosts']['$1']['packages']:
    if p['kind']=='$2' and p['name']=='$3': print(p['status']); break
"
}

@test "host-mismatch FAILS CLOSED — collect A piped to merge B is refused (exit 1)" {
  run bash -c "printf 'host:mother\napt\tvim\t2.0\n' | python3 '$TOOL' merge weyland"
  [ "$status" -eq 1 ]
  [[ "$output" == *"collected host 'mother' != target 'weyland'"* ]]
  [ ! -f "$MACHINE_INV_SOT" ]   # nothing written
}

@test "empty inventory is refused, never blanks the host" {
  run bash -c "printf 'host:rogueone\n' | python3 '$TOOL' merge rogueone"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no records on stdin"* ]]
}

@test "baseline vs discretionary defaults: apt/pip/image=system, snap/flatpak/npm=unreviewed" {
  printf 'host:h\nsnap\ta\t1\napt\tb\t2\npip\tc\t3\nimage\td\t4\nnpm\te\t\nflatpak\tf\t1\n' \
    | python3 "$TOOL" merge h
  [ "$(status_of h snap a)" = "unreviewed" ]
  [ "$(status_of h flatpak f)" = "unreviewed" ]
  [ "$(status_of h npm e)" = "unreviewed" ]
  [ "$(status_of h apt b)" = "system" ]
  [ "$(status_of h pip c)" = "system" ]
  [ "$(status_of h image d)" = "system" ]
}

@test "a curated decision is PRESERVED across a re-merge (add-only)" {
  printf 'host:h\nsnap\tsteam\t1\n' | python3 "$TOOL" merge h
  # curate: mark it keep
  python3 -c "
import yaml
d=yaml.safe_load(open('$MACHINE_INV_SOT'))
for p in d['hosts']['h']['packages']:
    if p['name']=='steam': p['status']='keep'; p['rationale']='gaming'
yaml.safe_dump(d,open('$MACHINE_INV_SOT','w'),sort_keys=False)
"
  # re-collect the same thing → decision must survive
  printf 'host:h\nsnap\tsteam\t1\n' | python3 "$TOOL" merge h
  [ "$(status_of h snap steam)" = "keep" ]
}

@test "intra-run duplicate (kind,name) records are deduped (multi-tag image / apt multiarch)" {
  # crictl lists a repo once per tag; apt multiarch prints the arch-less name per arch. Those arrive as
  # identical (kind,name) records in ONE collector run and must collapse to ONE cataloged row.
  printf 'host:h\nimage\treg/app\ttag1\nimage\treg/app\ttag2\nimage\treg/app\ttag3\napt\tlibx\tamd64\napt\tlibx\ti386\n' \
    | python3 "$TOOL" merge h
  run python3 -c "import yaml;print(len(yaml.safe_load(open('$MACHINE_INV_SOT'))['hosts']['h']['packages']))"
  [ "$output" = "2" ]   # image:reg/app + apt:libx — two distinct (kind,name), not five rows
}

@test "a matching host merges cleanly (the happy path)" {
  run bash -c "printf 'host:h\nsnap\ta\t1\n' | python3 '$TOOL' merge h"
  [ "$status" -eq 0 ]
  [[ "$output" == *"+1 new"* ]]
}

@test "missing host: tag WARNS but proceeds (back-compat, not a false pass)" {
  run bash -c "printf 'snap\ta\t1\n' | python3 '$TOOL' merge h"
  [ "$status" -eq 0 ]
  [[ "$output" == *"carried no host: tag"* ]]
}

# --- B169: the verify read-back gate (fail CLOSED if the SoT did not actually land in Port) ---

@test "verify FAILS when the Port count != the SoT count (read-back gate, not assumed)" {
  printf 'host:h\nsnap\ta\t1\nsnap\tb\t1\n' | python3 "$TOOL" merge h   # SoT: 2 packages for h
  run env MACHINE_INV_VERIFY_ACTUAL=1 python3 "$TOOL" verify h          # Port claims only 1
  [ "$status" -ne 0 ]
  [[ "$output" == *"Port has 1 installed_package entities, SoT has 2"* ]]
}

@test "verify PASSES when the Port count matches the SoT count" {
  printf 'host:h\nsnap\ta\t1\nsnap\tb\t1\n' | python3 "$TOOL" merge h
  run env MACHINE_INV_VERIFY_ACTUAL=2 python3 "$TOOL" verify h
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "verify refuses a host absent from the SoT (never a false green)" {
  printf 'host:h\nsnap\ta\t1\n' | python3 "$TOOL" merge h
  run python3 "$TOOL" verify ghost
  [ "$status" -ne 0 ]
  [[ "$output" == *"not in the SoT"* ]]
}
