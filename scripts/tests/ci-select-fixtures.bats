#!/usr/bin/env bats
# B177 — select-fixtures.sh: decide RUN_FIXTURES (1 = full fixture matrix, 0 = skip fixtures).
#
# The load-bearing invariant is FAIL-CLOSED: "0" (skip) is emitted ONLY on a git diff that succeeded and
# matched none of the manifest's fixture_trigger_paths. A missing/unparseable manifest, or any change
# under a trigger path, must print "1" — an absent/errored result must never read as "nothing changed"
# (project.md c14). The SELECT_CHANGED_FILES seam feeds a fixed changed-file list so the DECISION is
# tested without a git repo.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/ci/select-fixtures.sh"
  # Real manifest by default; individual tests override CI_LANGS_FILE for the fail-closed cases.
  MANIFEST="$REPO_ROOT/ci-langs.yaml"
}

teardown() { teardown_stubs; }

@test "the selector exists and is executable-as-bash" {
  [ -f "$GUARD" ]
}

@test "a change under golden-paths/ runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'golden-paths/go/gin/main.go' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [ "$output" = "1" ]
}

@test "a change under tests/lang/ runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'tests/lang/shell/foo.bats' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to the lane runner runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'scripts/run-lang-tests.sh' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to .woodpecker.yml with no base version to compare runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/absent.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

# --- 2026-10-16: .woodpecker.yml counts only where it touches a fixture lane --------------------------------------------
# Pipeline #382 ran the whole fixture matrix (hours) because one line was added to repo-guards — a step that runs in
# every lean run anyway. The file stays a trigger, but only its fixture-gated steps and its top-level keys (labels,
# when, the shared anchors) decide; a change confined to an ungated step selects lean.

wp() {  # wp <file> <repo-guards command> <test-go image> [top-level label]
  cat > "$1" <<EOF
labels:
  backend: ${4:-kubernetes}
steps:
  - name: repo-guards
    image: alpine
    commands:
      - $2
  - name: test-go
    when: &fixture [{event: [manual, cron], evaluate: 'SMOKE_ONLY != "smoke" && RUN_FIXTURES != "0"'}]
    image: $3
    commands:
      - bash scripts/run-lang-tests.sh go
  - name: test-rust
    when: *fixture
    image: rust:1
EOF
}

@test ".woodpecker.yml changed only in an ungated step selects lean (0)" {
  wp "$STUB_DIR/base.yml" "bash scripts/a.sh" golang:1.26
  wp "$STUB_DIR/head.yml" "bash scripts/b.sh" golang:1.26
  SELECT_CHANGED_FILES=$'.woodpecker.yml\ndocs/backlog.md' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test ".woodpecker.yml changed in a fixture-gated step runs the full matrix (1)" {
  wp "$STUB_DIR/base.yml" "bash scripts/a.sh" golang:1.26
  wp "$STUB_DIR/head.yml" "bash scripts/a.sh" golang:1.27
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test ".woodpecker.yml changed at the top level runs the full matrix (1)" {
  wp "$STUB_DIR/base.yml" "bash scripts/a.sh" golang:1.26 kubernetes
  wp "$STUB_DIR/head.yml" "bash scripts/a.sh" golang:1.26 local
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a step that LOSES its fixture gate runs the full matrix (1)" {
  wp "$STUB_DIR/base.yml" "bash scripts/a.sh" golang:1.26
  wp "$STUB_DIR/head.yml" "bash scripts/a.sh" golang:1.26
  sed -i 's/^    when: \*fixture$//' "$STUB_DIR/head.yml"
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "an unparseable .woodpecker.yml base runs the full matrix (1)" {
  printf 'steps: [unclosed\n' > "$STUB_DIR/base.yml"
  wp "$STUB_DIR/head.yml" "bash scripts/a.sh" golang:1.26
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a base with NO fixture-gated steps runs the full matrix (1), never 'nothing gated changed'" {
  printf 'steps:\n  - name: a\n    image: alpine\n' > "$STUB_DIR/base.yml"
  printf 'steps:\n  - name: a\n    image: alpine:3\n' > "$STUB_DIR/head.yml"
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "the real push that tripped #382 (f9ac9ae1..d7ae173b, repo-guards only) selects lean (0)" {
  { git -C "$REPO_ROOT" cat-file -e d7ae173b && git -C "$REPO_ROOT" cat-file -e f9ac9ae1; } 2>/dev/null || skip "commits not in this clone"
  git -C "$REPO_ROOT" show f9ac9ae1:.woodpecker.yml > "$STUB_DIR/base.yml"
  git -C "$REPO_ROOT" show d7ae173b:.woodpecker.yml > "$STUB_DIR/head.yml"
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" \
    SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "0" ]
}

@test "a change to the manifest itself runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'ci-langs.yaml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "changes ONLY to production/other code skip fixtures (0)" {
  SELECT_CHANGED_FILES=$'nodes/mother/lab/weyland-platform/services/weyland-dagster/foo.py\nscripts/check-linear-sync.sh\ndocs/backlog.md' \
    CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test "an EMPTY diff fails closed to the full matrix (1) — ambiguous, not 'nothing changed'" {
  # Run after a push, HEAD == origin/main, so the diff is empty even if the push touched golden paths.
  # "0" (skip) must require POSITIVE evidence of a non-fixture-only change; empty is not that.
  SELECT_CHANGED_FILES=$'' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a mixed change (fixture + non-fixture) runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'docs/backlog.md\ngolden-paths/rust/axum/Cargo.toml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "an unreadable manifest fails closed to the full matrix (1)" {
  SELECT_CHANGED_FILES=$'docs/backlog.md' CI_LANGS_FILE="$STUB_DIR/nope.yaml" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a manifest with no fixture_trigger_paths fails closed to the full matrix (1)" {
  printf 'production_lanes:\n  - test-python\n' > "$STUB_DIR/m.yaml"
  SELECT_CHANGED_FILES=$'docs/backlog.md' CI_LANGS_FILE="$STUB_DIR/m.yaml" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a fixture path only counts as a real PREFIX (not a substring elsewhere)" {
  # 'x/golden-paths/go' must NOT match the 'golden-paths/' prefix — startswith, not contains.
  SELECT_CHANGED_FILES=$'vendor/x/golden-paths/go/main.go\ndocs/notes.md' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "0" ]
}

# --- 2026-10-03: the golden-path smoke machinery is a trigger too --------------------------------------------------------
# A change to scripts/run-golden-path-jobs.sh (the run-scoped Job names, pipeline #242) selected LEAN (0), which skips
# golden-path-smoke — the one step that exercises that script. Its RBAC and the lib it sources have the same blind spot.

@test "a change to the golden-path smoke runner runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'scripts/run-golden-path-jobs.sh' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to the golden-paths k8s RBAC runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'nodes/mother/lab/weyland-platform/k8s/golden-paths/golden-paths-rbac.yaml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to scripts/lib/common.sh (sourced by the lane runners) runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'scripts/lib/common.sh' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

# The audit that keeps the gap closed: every script a fixture-gated step runs — and every file that script sources —
# must be a trigger path, or a change to it gets a lean run that never exercises it.
@test "every script a lean-gated step runs (and what it sources) is in fixture_trigger_paths" {
  run python3 - "$REPO_ROOT" <<'PY'
import os, re, sys, yaml
root = sys.argv[1]
wp = yaml.safe_load(open(f"{root}/.woodpecker.yml"))
trig = yaml.safe_load(open(f"{root}/ci-langs.yaml"))["fixture_trigger_paths"]
gated = [s for s in wp["steps"] if 'RUN_FIXTURES != "0"' in str(s.get("when", ""))]
if not gated:
    sys.exit("no lean-gated steps found — the guard is checking nothing")
scripts = set()
for s in gated:
    for c in s.get("commands") or []:
        scripts.update(re.findall(r"(scripts/[\w./-]+\.sh)", str(c)))
seen, todo = set(), list(scripts)
while todo:                                   # follow `. "$(dirname "$0")/lib/x.sh"` style sources
    f = todo.pop()
    if f in seen or not os.path.exists(f"{root}/{f}"):
        continue
    seen.add(f)
    for m in re.findall(r'^\s*(?:\.|source)\s+"?\$\(dirname "\$(?:0|\{BASH_SOURCE\[0\]\})"\)/([\w./-]+)"?', open(f"{root}/{f}").read(), re.M):
        todo.append(os.path.normpath(os.path.join(os.path.dirname(f), m)))
missing = sorted(f for f in seen if not any(f.startswith(t) for t in trig))
print(f"{len(gated)} lean-gated steps, {len(seen)} scripts checked")
if missing:
    print("NOT a trigger path (a change here would skip the step that runs it):", missing); sys.exit(1)
PY
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"scripts checked"* ]] || { echo "$output"; return 1; }
}

# --- 2026-10-18: --plan narrows a golden-path-only change to the lanes that test it --------------------------------------
# select-fixtures printed only 0/1, so ONE golden path's change (swift-nio in golden-paths/swift/vapor-app, CI #413) ran
# all ~46 fixture lanes. --plan prints RUN_FIXTURES + FIXTURE_LANES (the lane keys: test-<key>/scan-<key>) +
# GOLDEN_PATH_ONLY (the changed golden paths that have a Dockerfile, for golden-path-smoke). It narrows ONLY when every
# fixture-path change is inside golden-paths/<a>/<b>/ and maps to lanes through the lanes' OWN discovery
# (run-lang-tests.sh --list-roots); anything shared, unmapped or unreadable stays the full matrix (FIXTURE_LANES="").
plan_wp() {  # a .woodpecker.yml with two lane keys (swift, node) + the smoke step
  cat > "$1" <<'YML'
steps:
  - name: test-swift
    when: [{event: [manual, cron], evaluate: 'RUN_FIXTURES != "0"'}]
    commands: [bash scripts/run-lang-tests.sh swift]
  - name: scan-swift
    when: [{event: [manual, cron], evaluate: 'RUN_FIXTURES != "0"'}]
    commands: [bash scripts/run-lang-scan.sh swift]
  - name: test-node
    when: [{event: [manual, cron], evaluate: 'RUN_FIXTURES != "0"'}]
    commands: [bash scripts/run-lang-tests.sh javascript, bash scripts/run-lang-tests.sh react]
  - name: golden-path-smoke
    when: [{event: [manual, cron], evaluate: 'RUN_FIXTURES != "0"'}]
    commands: [bash scripts/run-golden-path-jobs.sh $GOLDEN_PATH_ONLY]
YML
}
ROOTS=$'swift golden-paths/swift/vapor-app\nswift golden-paths/mobile/swift-ios\njavascript golden-paths/node/express\nreact golden-paths/frontend/vite-react'

plan() {  # plan <changed files>
  plan_wp "$STUB_DIR/wp.yml"
  SELECT_CHANGED_FILES="$1" SELECT_WOODPECKER_HEAD="$STUB_DIR/wp.yml" SELECT_LANG_ROOTS="$ROOTS" \
    CI_LANGS_FILE="$MANIFEST" run bash "$GUARD" --plan
}

@test "--plan: one golden path narrows to its own lanes and smoke-tests only that path" {
  plan $'golden-paths/swift/vapor-app/Package.resolved'
  [ "$status" -eq 0 ]
  [[ "$output" == *"RUN_FIXTURES=1"* ]]
  [[ "$output" == *"FIXTURE_LANES='swift'"* ]]
  [[ "$output" == *"GOLDEN_PATH_ONLY='swift/vapor-app'"* ]]
}

@test "--plan: a path the lane DISCOVERS (not its fixture) selects that lane; no Dockerfile means no smoke target" {
  plan $'golden-paths/mobile/swift-ios/Sources/App.swift'
  [[ "$output" == *"FIXTURE_LANES='swift'"* ]]
  [[ "$output" == *"GOLDEN_PATH_ONLY=''"* ]]
}

@test "--plan: two languages select both lanes" {
  plan $'golden-paths/swift/vapor-app/Package.swift\ngolden-paths/frontend/vite-react/src/App.tsx'
  [[ "$output" == *"FIXTURE_LANES='node swift'"* ]]
  [[ "$output" == *"GOLDEN_PATH_ONLY='frontend/vite-react swift/vapor-app'"* ]]
}

@test "--plan: a golden path no fixture lane tests runs no lane (none), only its smoke" {
  plan $'golden-paths/python/flask/app.py'
  [[ "$output" == *"FIXTURE_LANES='none'"* ]]
  [[ "$output" == *"GOLDEN_PATH_ONLY='python/flask'"* ]]
}

@test "--plan: a shared fixture trigger alongside stays the FULL matrix (empty FIXTURE_LANES = all)" {
  plan $'golden-paths/swift/vapor-app/Package.swift\nscripts/run-lang-tests.sh'
  [[ "$output" == *"RUN_FIXTURES=1"* ]]
  [[ "$output" == *"FIXTURE_LANES=''"* ]]
  [[ "$output" == *"GOLDEN_PATH_ONLY=''"* ]]
}

@test "--plan: production-only changes skip fixtures (RUN_FIXTURES=0)" {
  plan $'nodes/mother/lab/weyland-platform/services/weyland-dagster/x.py'
  [[ "$output" == *"RUN_FIXTURES=0"* ]]
}

@test "--plan: lane discovery that fails stays the full matrix, never a narrowed guess" {
  plan_wp "$STUB_DIR/wp.yml"
  stub failing-roots 3 ''
  SELECT_CHANGED_FILES=$'golden-paths/swift/vapor-app/Package.swift' SELECT_WOODPECKER_HEAD="$STUB_DIR/wp.yml" \
    SELECT_LIST_ROOTS_CMD="$STUB_DIR/failing-roots" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD" --plan
  [[ "$output" == *"RUN_FIXTURES=1"* ]]
  [[ "$output" == *"FIXTURE_LANES=''"* ]]
}

@test "--plan output is eval-safe shell assignments, three lines" {
  plan $'golden-paths/swift/vapor-app/Package.resolved'
  [ "${#lines[@]}" -eq 3 ]
  eval "$output"
  [ "$FIXTURE_LANES" = "swift" ]
}

@test "the REAL .woodpecker.yml: every fixture lane gates on its OWN lane key, and the smoke step on its scope" {
  python3 - "$REPO_ROOT/.woodpecker.yml" <<'PY'
import re, sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
bad = []
for s in d["steps"]:
    w = str(s.get("when", ""))
    if "RUN_FIXTURES" not in w:
        continue
    name = s["name"]
    if name == "golden-path-smoke":
        if "GOLDEN_PATH_ONLY" not in w or "FIXTURE_LANES" not in w:
            bad.append(f"{name}: must gate on FIXTURE_LANES + GOLDEN_PATH_ONLY")
        continue
    key = re.sub(r"^(test|scan)-", "", name)
    if f'" {key} "' not in w or "FIXTURE_LANES" not in w:
        bad.append(f"{name}: evaluate must test FIXTURE_LANES for \" {key} \"")
print("\n".join(bad)); sys.exit(1 if bad else 0)
PY
}

@test "--plan: a .woodpecker.yml change confined to ONE lane's steps narrows to that lane (the swift 6.4.1 bump)" {
  plan_wp "$STUB_DIR/base.yml"
  sed 's|run-lang-tests.sh swift]|run-lang-tests.sh swift, echo swift-6.4.1]|' "$STUB_DIR/base.yml" > "$STUB_DIR/head.yml"
  SELECT_CHANGED_FILES=$'.woodpecker.yml\ngolden-paths/swift/vapor-app/Package.resolved' \
    SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" \
    SELECT_LANG_ROOTS="$ROOTS" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD" --plan
  [[ "$output" == *"FIXTURE_LANES='swift'"* ]]
  [[ "$output" == *"GOLDEN_PATH_ONLY='swift/vapor-app'"* ]]
}

@test "--plan: a change to the golden-path-smoke step itself stays the full matrix" {
  plan_wp "$STUB_DIR/base.yml"
  sed 's|run-golden-path-jobs.sh $GOLDEN_PATH_ONLY|run-golden-path-jobs.sh --verbose $GOLDEN_PATH_ONLY|' "$STUB_DIR/base.yml" > "$STUB_DIR/head.yml"
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" \
    SELECT_LANG_ROOTS="$ROOTS" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD" --plan
  [[ "$output" == *"FIXTURE_LANES=''"* ]]
}

@test "--plan: a top-level .woodpecker.yml change stays the full matrix even if a lane step also changed" {
  plan_wp "$STUB_DIR/base.yml"
  { echo "labels: {backend: docker}"; sed 's|run-lang-tests.sh swift]|run-lang-tests.sh swift, echo x]|' "$STUB_DIR/base.yml"; } > "$STUB_DIR/head.yml"
  SELECT_CHANGED_FILES=$'.woodpecker.yml' SELECT_WOODPECKER_BASE="$STUB_DIR/base.yml" SELECT_WOODPECKER_HEAD="$STUB_DIR/head.yml" \
    SELECT_LANG_ROOTS="$ROOTS" CI_LANGS_FILE="$MANIFEST" run bash "$GUARD" --plan
  [[ "$output" == *"FIXTURE_LANES=''"* ]]
}
