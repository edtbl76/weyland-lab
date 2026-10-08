#!/usr/bin/env bats
# The SQLite app-store backups (open-webui-backup 2026-10-04, woodpecker-backup 2026-10-05). Each CronJob runs the copy
# of scripts/sqlite_backup.py embedded in its ConfigMap, not the repo file — copies drift silently, and a backup that
# drifted from its tested logic is untested. scripts/embed-sqlite-backup.sh regenerates them; this asserts each is
# identical and that each job is wired to the right PVC, database file and required tables.
# The behaviour itself is tested by scripts/tests/test_sqlite_backup.py (pytest).

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  K="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s"
}

check() {
  python3 - "$REPO_ROOT/scripts/sqlite_backup.py" "$@" <<'PY'
import sys, yaml
script, manifest, data_claim, db, *required = sys.argv[1:]
docs = [d for d in yaml.safe_load_all(open(manifest)) if d]
cm = next(d for d in docs if d["kind"] == "ConfigMap")["data"]
assert cm.get("sqlite_backup.py") == open(script).read(), "DRIFT — run scripts/embed-sqlite-backup.sh"
cj = next(d for d in docs if d["kind"] == "CronJob")
assert cj["spec"]["timeZone"] == "America/New_York", cj["spec"].get("timeZone")
spec = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]
cmd = spec["containers"][0]["command"]
claims = {v["name"]: v.get("persistentVolumeClaim", {}).get("claimName") for v in spec["volumes"]}
assert cmd[:2] == ["python3", "/opt/backup/sqlite_backup.py"], cmd
assert cmd[cmd.index("--db") + 1] == db, cmd
assert [cmd[i + 1] for i, a in enumerate(cmd) if a == "--require"] == required, cmd
assert claims["data"] == data_claim, claims
print("ok")
PY
}

@test "open-webui-backup runs the identical embedded script against webui.db, requiring users" {
  run check "$K/open-webui/backup.yaml" open-webui-data webui.db user
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "woodpecker-backup runs the identical embedded script against woodpecker.sqlite, requiring users + pipelines" {
  run check "$K/woodpecker/woodpecker-backup.yaml" data-woodpecker-server-0 woodpecker.sqlite users pipelines
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "bifrost-backup runs the identical embedded script against config.db, requiring providers + VKs + prompts + skills" {
  run check "$K/bifrost/bifrost-backup.yaml" bifrost-data config.db config_providers governance_virtual_keys prompts skills
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
