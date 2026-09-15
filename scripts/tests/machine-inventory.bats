#!/usr/bin/env bats
# Tests for the machine-inventory merge decision-logic (B129). The collector is env-dependent (real package
# managers / SSH), so these exercise `machine_inventory.py merge` — the part that MAKES DECISIONS: the
# host-mismatch guard (fail-closed regression for the 2026-09-14 mother/weyland mixup), the empty-stdin
# refusal, the baseline-vs-discretionary default status, and decision preservation. SoT path is overridden
# via MACHINE_INV_SOT so no fixture touches the real catalog. Needs python3 + pyyaml (CI shell-tests installs both).

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
