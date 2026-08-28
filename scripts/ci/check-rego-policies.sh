#!/usr/bin/env sh
# Verify every Gatekeeper ConstraintTemplate's Rego — COMPILES and BEHAVES (B88 Phase 3).
#
# WHY THIS IS ITS OWN STEP. `kubeconform` SKIPS Gatekeeper CRDs (it has no schema for them), so
# before this script NOTHING validated the Rego at all: a policy with a syntax error or inverted
# logic would ship, be applied, and silently admit everything. "The file exists" was the only check.
#
# It cannot live in the bats suite: exercising Rego needs the OPA binary, that suite runs inside
# bats/bats, and shelling to docker from there is docker-in-docker with an unmappable temp path —
# the tests only "passed" by skipping. So this runs in the OPA image directly.
#
# REGO v0 IS DELIBERATE. Gatekeeper uses v0 and the shipped constraints.yaml is written in it; OPA's
# own default is now v1, which rejects both files. Checking with the wrong dialect would report
# false errors on correct policy.
set -eu

POLICY_DIR="nodes/mother/lab/weyland-platform/k8s/gatekeeper"
WORK="$(mktemp -d)"
rc=0

for f in "$POLICY_DIR"/*.yaml; do
  [ -f "$f" ] || continue
  grep -q "kind: ConstraintTemplate" "$f" || continue
  python3 - "$f" "$WORK" <<'PY'
import sys, yaml, os, pathlib
src, work = sys.argv[1], sys.argv[2]
for i, d in enumerate(x for x in yaml.safe_load_all(open(src)) if x):
    if d.get("kind") != "ConstraintTemplate":
        continue
    for j, tgt in enumerate(d["spec"]["targets"]):
        name = f"{pathlib.Path(src).stem}.{i}.{j}.rego"
        pathlib.Path(work, name).write_text(tgt["rego"])
        print(f"extracted {name} from {os.path.basename(src)}")
PY
done

for r in "$WORK"/*.rego; do
  [ -f "$r" ] || continue
  if opa check --v0-compatible "$r" >/dev/null 2>&1; then
    echo "  OK   $(basename "$r") compiles"
  else
    echo "  FAIL $(basename "$r") does not compile:" >&2
    opa check --v0-compatible "$r" >&2 || true
    rc=1
  fi
done

# ── behaviour, not just syntax ──────────────────────────────────────────────────────────────────
# A policy that compiles can still be inverted. The signature constraint gets exercised against
# three real admission payloads: an allowed image, a foreign one, and an exempted one. If the
# "foreign" case ever returns zero violations the constraint is decoration, and that must fail.
SIG="$WORK/image-signatures.0.0.rego"
if [ -f "$SIG" ]; then
  P='{"allowedRegistries":["registry.weyland.lab/"],"exemptImages":["docker.io/library/"]}'
  check() { # check <label> <image> <expected-count>
    printf '{"parameters":%s,"review":{"object":{"spec":{"containers":[{"name":"c","image":"%s"}]}}}}' \
      "$P" "$2" > "$WORK/in.json"
    got="$(opa eval --v0-compatible -d "$SIG" -i "$WORK/in.json" \
      'data.k8simagesignature.violation' 2>/dev/null \
      | python3 -c 'import sys,json;r=json.load(sys.stdin);print(len(r.get("result",[{}])[0].get("expressions",[{}])[0].get("value",[])))')"
    if [ "$got" = "$3" ]; then
      echo "  OK   $1 -> $got violation(s)"
    else
      echo "  FAIL $1 -> $got violation(s), expected $3" >&2
      rc=1
    fi
  }
  check "signed-registry image admitted" "registry.weyland.lab/weyland-agent:git-abc" 0
  check "foreign-registry image flagged" "evil.example.com/backdoor:latest"           1
  check "exempted third-party admitted"  "docker.io/library/postgres:17"              0
fi

rm -rf "$WORK"
[ "$rc" -eq 0 ] && echo "OK — every Gatekeeper Rego compiles and the signature policy behaves correctly."
exit "$rc"
