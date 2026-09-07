#!/usr/bin/env bash
# Service onboarding scaffolder (B154 Phase 1b — the paved road that Phase 1a's guard checks).
#
# WHY THIS EXISTS: onboarding a service means adding it to the canonical registry (applications.yaml)
# AND placing it in the single LikeC4 model — two curated files a human edits by hand and forgets one of
# (the exact drift Phase 1a's check-onboarding-completeness.sh now fails CI on). This writes BOTH from one
# command, deterministically, then runs the guards to prove the new service lands onboarded-complete
# instead of being audited into compliance later.
#
# WHAT IT WRITES (idempotent-safe — refuses if the key already exists):
#   1. a registry entry appended to applications.yaml (flow style, matching the file), with
#      deployed: true and an explicit `likec4: <id>` so placement can never be ambiguous;
#   2. a LikeC4 element `<id> = <kind> "<Name>" "<desc>"` as the first element inside the chosen zone,
#      with the id = camelCase(key) so it also matches by name — belt and suspenders.
# It does NOT invent edges: a scaffolded element is placed but unwired, and the tool says so — wiring
# relationships is a human judgement the scaffold deliberately leaves as a follow-up.
#
#   usage: scripts/onboard-service.sh --key <k> --name "<Name>" --group <group> --zone <zone> \
#             [--kind component|gateway|store|node] [--datahub-app] [--port-component <id>] \
#             [--metrics] [--ingress] [--capabilities a,b] [--description "..."] [--dry-run]
#     --metrics  the service exposes /metrics (declares the ServiceMonitor+dashboard gate applies)
#     --ingress  the service has a user-facing host (declares the Kuma + endpoint gates apply)
#     --zone   the LikeC4 zone the element lands in: ai | mesh | gov | edge | obs | platform
#     --kind   the LikeC4 element kind (default: component)
#     --dry-run  print exactly what would be written to each file, change nothing
#
# EXIT CODES: 0 onboarded (or dry-run printed); 1 bad/duplicate input; 2 the guard could not verify.
set -euo pipefail

if [ -r "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh" ]; then
  # shellcheck source=scripts/lib/common.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
fi
PLATFORM_DIR="${PLATFORM_DIR:-}"
REPO_ROOT="${REPO_ROOT:-.}"
REGISTRY_FILE="${REGISTRY_FILE:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline/applications.yaml}"
LIKEC4_FILE="${LIKEC4_FILE:-$REPO_ROOT/docs/architecture/weyland.likec4}"
GUARD="$(dirname "${BASH_SOURCE[0]}")/check-onboarding-completeness.sh"

KEY="" NAME="" GROUP="" ZONE="" KIND="component" PORTC="" CAPS="" DESC="" DATAHUB="false" DRY="false"
METRICS="false" INGRESS="false"
while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --group) GROUP="$2"; shift 2 ;;
    --zone) ZONE="$2"; shift 2 ;;
    --kind) KIND="$2"; shift 2 ;;
    --port-component) PORTC="$2"; shift 2 ;;
    --capabilities) CAPS="$2"; shift 2 ;;
    --description) DESC="$2"; shift 2 ;;
    --datahub-app) DATAHUB="true"; shift ;;
    --metrics) METRICS="true"; shift ;;
    --ingress) INGRESS="true"; shift ;;
    --dry-run) DRY="true"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

VALID_GROUPS="core-producer ai-serving data-platform bi operational observability serving gateway ui platform"
VALID_KINDS="component gateway store node"
VALID_ZONES="ai mesh gov edge obs platform"

for pair in "key:$KEY" "name:$NAME" "group:$GROUP" "zone:$ZONE"; do
  [ -z "${pair#*:}" ] && { echo "missing required --${pair%%:*}" >&2; exit 1; }
done
case " $VALID_GROUPS " in *" $GROUP "*) ;; *) echo "invalid --group '$GROUP' (one of: $VALID_GROUPS)" >&2; exit 1 ;; esac
case " $VALID_KINDS " in *" $KIND "*) ;; *) echo "invalid --kind '$KIND' (one of: $VALID_KINDS)" >&2; exit 1 ;; esac
case " $VALID_ZONES " in *" $ZONE "*) ;; *) echo "invalid --zone '$ZONE' (one of: $VALID_ZONES)" >&2; exit 1 ;; esac

# The file surgery + validation runs in python (precise insertion; the bash above owns arg contracts).
KEY="$KEY" NAME="$NAME" GROUP="$GROUP" ZONE="$ZONE" KIND="$KIND" PORTC="$PORTC" CAPS="$CAPS" \
DESC="$DESC" DATAHUB="$DATAHUB" METRICS="$METRICS" INGRESS="$INGRESS" DRY="$DRY" \
REGISTRY_FILE="$REGISTRY_FILE" LIKEC4_FILE="$LIKEC4_FILE" \
python3 <<'PY' || exit $?
import os, re, sys
key=os.environ["KEY"]; name=os.environ["NAME"]; group=os.environ["GROUP"]; zone=os.environ["ZONE"]
kind=os.environ["KIND"]; portc=os.environ["PORTC"] or key; caps=os.environ["CAPS"]
desc=os.environ["DESC"] or f"{name} (scaffolded — wire edges + refine placement)."
datahub=os.environ["DATAHUB"]=="true"; dry=os.environ["DRY"]=="true"
metrics=os.environ["METRICS"]=="true"; ingress=os.environ["INGRESS"]=="true"
reg_f=os.environ["REGISTRY_FILE"]; lk_f=os.environ["LIKEC4_FILE"]

if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', key):
    print(f"invalid --key '{key}' (kebab-case: lowercase, digits, single dashes)", file=sys.stderr); sys.exit(1)
# camelCase id from the kebab key
parts=key.split("-"); cid=parts[0]+"".join(p.capitalize() for p in parts[1:])

reg=open(reg_f).read()
if re.search(r'\bkey:\s*'+re.escape(key)+r'\b', reg):
    print(f"'{key}' is already in the registry — refusing to duplicate", file=sys.stderr); sys.exit(1)
lk=open(lk_f).read()
if re.search(r'^\s*'+re.escape(cid)+r'\s*=\s*', lk, re.M):
    print(f"LikeC4 element id '{cid}' already exists — pick a different --key", file=sys.stderr); sys.exit(1)

caps_yaml="[" + ", ".join(f'"{c.strip()}"' for c in caps.split(",") if c.strip()) + "]"
entry=('  - {key: %s, deployed: true, metrics: %s, ingress: %s, name: %s, group: %s, '
       'datahub_application: %s, owns: [], capabilities: %s, likec4: %s, port_component: %s, '
       'description: "%s"}'
       % (key, str(metrics).lower(), str(ingress).lower(), name, group, str(datahub).lower(),
          caps_yaml, cid, portc, desc.replace('"',"'")))

# LikeC4 element line, indented to the chosen zone's body (zone indent + 2).
zm=re.search(r'^(\s*)'+re.escape(zone)+r'\s*=\s*zone\b[^\n]*\{\s*$', lk, re.M)
if not zm:
    print(f"could not find the '{zone}' zone in {lk_f}", file=sys.stderr); sys.exit(2)
indent=" "*(len(zm.group(1))+2)
element=f'{indent}{cid} = {kind} "{name}" "{desc}"'

if dry:
    print("DRY RUN — would add to the registry (before the CODE-REVIEW / excluded section):")
    print(entry)
    print(f"\nDRY RUN — would add to LikeC4 (first element in zone '{zone}'):")
    print(element)
    print(f"\nThen: check-app-registry + check-onboarding-completeness would verify (likec4: {cid}).")
    sys.exit(0)

# Insert the registry entry before the CODE-REVIEW section comment, else before `excluded:`, else end of list.
anchor=re.search(r'^\s*# =+ CODE-REVIEW', reg, re.M) or re.search(r'^excluded:', reg, re.M)
if anchor:
    reg=reg[:anchor.start()]+entry+"\n"+reg[anchor.start():]
else:
    reg=reg.rstrip()+"\n"+entry+"\n"
open(reg_f,"w").write(reg)

# Insert the element as the first line inside the zone body.
lk=lk[:zm.end()]+"\n"+element+lk[zm.end():]
open(lk_f,"w").write(lk)

print(f"onboarded '{key}': registry entry + LikeC4 element '{cid}' ({kind}) in zone '{zone}'.")
print("NOTE: the element is placed but UNWIRED — add its relationships in weyland.likec4 by hand.")
PY

# --dry-run stops here (python already exited 0 without writing).
[ "$DRY" = "true" ] && exit 0

echo "--- verifying onboarding completeness ---"
REGISTRY_FILE="$REGISTRY_FILE" LIKEC4_FILE="$LIKEC4_FILE" bash "$GUARD" >/dev/null 2>&1 \
  && echo "✓ check-onboarding-completeness green — '$KEY' is placed." \
  || { echo "check-onboarding-completeness did NOT pass after scaffolding '$KEY' — inspect the two files" >&2; exit 2; }
