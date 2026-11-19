#!/usr/bin/env bats
# The rules every workflow in .woodpecker/ follows (B200, 2026-11-18; .woodpecker/README.md § Rules), checked so a new
# or edited workflow cannot quietly break them. Each rule was learned the hard way:
#   - no node label: a workflow could land on the other agent pool, away from the ci-cache-* volumes (CI #676 hung 3 h);
#   - a cache volume mounted by two workflows: two steps writing one RWO cache at once;
#   - a cache from another pool's node: a local-path volume mounts only on its node (step 3: `-tb` = timberback);
#   - deliver not waiting on everything: images ship from a red run;
#   - finish not waiting on everything: it reads a still-running workflow (#686);
#   - a workflow-level gate on a --var: Woodpecker never shows it the var, so the workflow is filtered out (#681);
#   - notify trusting $CI_PIPELINE_STATUS: it sees only its own workflow (#683);
#   - a workflow whose steps write JUnit but has no trunk-upload: its results never reach Trunk (step 2 lost the
#     golden-path uploads that way for #687-#691);
#   - golden-path shards that drift apart, or a shard missing or used twice (step 4: golden-path-1..N);
#   - a trunk-upload that runs when every JUnit writer in its workflow was gated off: no report, so it goes red (smoke
#     run #693: platform's ungated upload ran while test-python/-shell/-java skipped on SMOKE_ONLY).
# Every rule runs against the real pipeline AND against a copy broken on purpose, so no rule can pass by checking nothing.
# The checker is one inline python program; LAYOUT_DIR is the directory it reads.

setup() {
  REPO="$BATS_TEST_DIRNAME/../.."
  CHECK="$BATS_TEST_TMPDIR/check.py"
  cat > "$CHECK" <<'PY'
import glob, os, re, sys, yaml
d = sys.argv[1]
flows = {os.path.basename(f)[:-4]: yaml.safe_load(open(f)) for f in sorted(glob.glob(f"{d}/*.yml"))}
bad = []
if not flows:
    bad.append(f"no workflow in {d}")
VARS = r"\b(SMOKE_ONLY|RUN_FIXTURES|FIXTURE_LANES|GOLDEN_PATH_ONLY|SHIP_RUN)\b"
caches = {}
for name, doc in flows.items():
    labels = doc.get("labels") or {}
    if labels.get("backend") != "kubernetes" or not labels.get("node"):
        bad.append(f"{name}: labels must name backend: kubernetes and a node (the agent pool)")
    if re.search(VARS, str(doc.get("when", ""))):
        bad.append(f"{name}: a workflow-level `when` gates on a --var, which it never sees (gate the steps)")
    for s in doc.get("steps") or []:
        for v in s.get("volumes") or []:
            vol = str(v).split(":")[0]
            if vol.startswith("ci-cache-"):
                caches.setdefault(vol, set()).add(name)
                home = "timberback" if vol.endswith("-tb") else "mother"
                if labels.get("node") != home:
                    bad.append(f"{name}/{s.get('name')}: mounts {vol}, which lives on {home}, but the workflow runs on node {labels.get('node')}")
for vol, users in sorted(caches.items()):
    if len(users) > 1:
        bad.append(f"{vol} is mounted by {sorted(users)}: one workflow per cache (RWO, one writer at a time)")
work = sorted(n for n in flows if n not in ("deliver", "finish"))
if "deliver" in flows and sorted(flows["deliver"].get("depends_on") or []) != work:
    bad.append(f"deliver must depend on exactly {work}, has {sorted(flows['deliver'].get('depends_on') or [])}")
if "finish" in flows:
    f = flows["finish"]
    want = sorted(n for n in flows if n != "finish")
    if sorted(f.get("depends_on") or []) != want:
        bad.append(f"finish must depend on every other workflow {want}, has {sorted(f.get('depends_on') or [])}")
    if "failure" not in str(f.get("when", "")):
        bad.append("finish must run on failure too (when: status: [success, failure])")
    for s in f.get("steps") or []:
        text = "\n".join(map(str, s.get("commands") or []))
        if "CI_PIPELINE_STATUS" in text or "pipeline-status.sh" not in text:
            bad.append(f"finish/{s.get('name')}: must read the status from scripts/ci/pipeline-status.sh, never $CI_PIPELINE_STATUS")
for name, doc in flows.items():
    writes = any(isinstance(s.get("environment"), dict) and ({"LANG_JUNIT_DIR", "GOLDEN_PATH_JUNIT"} & set(s["environment"]))
                 for s in doc.get("steps") or [])
    if writes and not any(s.get("name") == "trunk-upload" for s in doc.get("steps") or []):
        bad.append(f"{name}: its steps write JUnit but it has no trunk-upload, so those results never reach Trunk")
    def conjuncts(step):
        ev = " ".join(str(w.get("evaluate", "")) for w in (step.get("when") or []) if isinstance(w, dict))
        return {c.strip() for c in ev.split("&&") if c.strip() and not c.strip().startswith("(")}
    writers = [s for s in doc.get("steps") or [] if isinstance(s.get("environment"), dict)
               and ({"LANG_JUNIT_DIR", "GOLDEN_PATH_JUNIT"} & set(s["environment"]))]
    uploads = [s for s in doc.get("steps") or [] if s.get("name") == "trunk-upload"]
    if writers and uploads:
        shared = set.intersection(*(conjuncts(w) for w in writers))
        missing = sorted(shared - conjuncts(uploads[0]))
        if missing:
            bad.append(f"{name}: trunk-upload runs when every JUnit writer is gated off; its gate lacks {missing}")
shards = sorted(n for n in flows if re.match(r"^golden-path-\d+$", n))
if shards:
    texts = {}
    for n in shards:
        raw = open(f"{d}/{n}.yml").read().split("\n")
        m = re.search(r"GOLDEN_PATH_SHARD: (\d+)/(\d+)", "\n".join(raw))
        if not m:
            bad.append(f"{n}: sets no GOLDEN_PATH_SHARD k/n"); continue
        texts[n] = ("\n".join(raw[1:]).replace(m.group(0), "GOLDEN_PATH_SHARD: K/N"), (int(m.group(1)), int(m.group(2))))
    if len({t for t, _ in texts.values()}) > 1:
        bad.append(f"golden-path shards differ beyond their header and shard number: {shards}")
    got = sorted(k for _, (k, _) in texts.values())
    if got != list(range(1, len(shards) + 1)) or any(n_ != len(shards) for _, (_, n_) in texts.values()):
        bad.append(f"golden-path shards must be 1/{len(shards)}..{len(shards)}/{len(shards)}, each once: got {sorted(v for _, v in texts.values())}")
print("\n".join(bad) if bad else f"OK - {len(flows)} workflow(s) follow the layout rules")
sys.exit(1 if bad else 0)
PY
  COPY="$BATS_TEST_TMPDIR/wf"
  mkdir -p "$COPY" && cp "$REPO"/.woodpecker/*.yml "$COPY/"
}

check() { run python3 "$CHECK" "$1"; }

@test "the real pipeline follows every layout rule" {
  check "$REPO/.woodpecker"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"10 workflow(s)"* ]] || { echo "$output"; return 1; }
}

@test "a workflow with no node label is refused" {
  sed -i '/^  node: /d' "$COPY/fixtures-a.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"fixtures-a: labels must name"* ]] || { echo "$output"; return 1; }
}

@test "a cache volume mounted by a second workflow is refused" {
  python3 - "$COPY/fixtures-c.yml" <<'PY'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
d["steps"][0]["volumes"] = ["ci-cache-npm-tb:/cache/npm"]     # fixtures-c is on timberback too: only sharing is wrong
yaml.safe_dump(d, open(p, "w"))
PY
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"ci-cache-npm-tb is mounted by"* ]] || { echo "$output"; return 1; }
}

@test "a cache from the other pool's node is refused (a local-path volume mounts only on its node; CI #676)" {
  sed -i 's/ci-cache-npm-tb:/ci-cache-npm:/' "$COPY/fixtures-b.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"mounts ci-cache-npm, which lives on mother, but the workflow runs on node timberback"* ]] || { echo "$output"; return 1; }
}

@test "deliver that does not wait for every work workflow is refused" {
  sed -i 's/^depends_on: \[platform, /depends_on: [/' "$COPY/deliver.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"deliver must depend on exactly"* ]] || { echo "$output"; return 1; }
}

@test "finish that does not wait for deliver is refused (#686: it read a running workflow)" {
  sed -i 's/, deliver\]$/]/' "$COPY/finish.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"finish must depend on every other workflow"* ]] || { echo "$output"; return 1; }
}

@test "a workflow-level gate on a --var is refused (#681: it never sees the var)" {
  printf 'labels: {backend: kubernetes, node: mother}\nwhen:\n  - event: manual\n    evaluate: '"'"'RUN_FIXTURES != "0"'"'"'\nsteps:\n  - name: x\n    image: alpine:3.20\n    commands: [echo x]\n' > "$COPY/extra.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"extra: a workflow-level"* ]] || { echo "$output"; return 1; }
}

@test "a finish step that trusts \$CI_PIPELINE_STATUS is refused (#683: it sees only its own workflow)" {
  python3 - "$COPY/finish.yml" <<'PY'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
d["steps"][0]["commands"] = ["echo $CI_PIPELINE_STATUS"]
yaml.safe_dump(d, open(p, "w"))
PY
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"finish/notify-port: must read the status"* ]] || { echo "$output"; return 1; }
}

@test "an empty pipeline directory is refused, never a pass" {
  check "$BATS_TEST_TMPDIR/nothing-here"
  [ "$status" -eq 1 ] && [[ "$output" == *"no workflow"* ]] || { echo "$output"; return 1; }
}

@test "a workflow that writes JUnit without a trunk-upload is refused (step 2 lost the golden-path uploads that way)" {
  python3 - "$COPY/golden-path-2.yml" <<'PY'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
d["steps"] = [s for s in d["steps"] if s["name"] != "trunk-upload"]
yaml.safe_dump(d, open(p, "w"))
PY
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"golden-path-2: its steps write JUnit but it has no trunk-upload"* ]] || { echo "$output"; return 1; }
}

@test "golden-path shards that drift apart are refused" {
  sed -i 's/memory: 1Gi/memory: 2Gi/' "$COPY/golden-path-3.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"golden-path shards differ"* ]] || { echo "$output"; return 1; }
}

@test "a golden-path shard used twice (and one missing) is refused" {
  sed -i 's|GOLDEN_PATH_SHARD: 3/3|GOLDEN_PATH_SHARD: 2/3|' "$COPY/golden-path-3.yml"
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"golden-path shards must be 1/3..3/3, each once"* ]] || { echo "$output"; return 1; }
}

@test "a trunk-upload broader than its JUnit writers is refused (#693: platform's upload ran in smoke mode with no report)" {
  python3 - "$COPY/platform.yml" <<'PY'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
for s in d["steps"]:
    if s["name"] == "trunk-upload":
        s["when"] = [{"status": ["success", "failure"]}]
yaml.safe_dump(d, open(p, "w"))
PY
  check "$COPY"
  [ "$status" -eq 1 ] && [[ "$output" == *"platform: trunk-upload runs when every JUnit writer is gated off"* ]] || { echo "$output"; return 1; }
}
