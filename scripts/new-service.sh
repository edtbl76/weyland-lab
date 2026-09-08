#!/usr/bin/env bash
#
# new-service.sh — scaffold a REAL service FROM a golden path (B153).
#
#   scripts/new-service.sh <golden-path> <service-name> [dest-dir]
#
#   <golden-path>   language/framework under golden-paths/, e.g. python/fastapi, node/express,
#                   frontend/nextjs, go/gin, rust/axum, java/quarkus
#   <service-name>  kebab-case name for the new service (also its image + SERVICE_NAME)
#   [dest-dir]      where to write it (default: ./<service-name>)
#
# It copies the golden path (minus build output and the lane's selfcheck probe), rewrites the
# golden-<lang>-<framework> token to <service-name> everywhere (SERVICE_NAME, the image ref, the
# manifest name), drops a minimal service README, and prints the onboarding-declaration snippets the
# B154/B155 gates want — so the scaffolded service starts in a DoD-passing shape.
#
# Fails closed: a missing golden path, a non-kebab name, or an existing dest all stop with a reason.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GP_DIR="$REPO_ROOT/golden-paths"

die() { printf 'new-service: %s\n' "$*" >&2; exit 2; }

usage() {
  cat >&2 <<EOF
usage: new-service.sh <golden-path> <service-name> [dest-dir]
  <golden-path>   e.g. python/fastapi, node/express, frontend/nextjs, go/gin, rust/axum, java/quarkus
  <service-name>  kebab-case (^[a-z][a-z0-9-]*\$)
  [dest-dir]      default ./<service-name>
available golden paths:
$(cd "$GP_DIR" 2>/dev/null && find . -name Dockerfile -exec dirname {} \; | sed 's|^\./|  |' | sort)
EOF
  exit 2
}

[ $# -ge 2 ] || usage
gp="$1"; name="$2"; dest="${3:-$PWD/$name}"

# ── validate ────────────────────────────────────────────────────────────────
[ -d "$GP_DIR/$gp" ] || die "no golden path at golden-paths/$gp (run with no args to list)"
[ -f "$GP_DIR/$gp/Dockerfile" ] || die "golden-paths/$gp has no Dockerfile — not a scaffoldable golden path"
case "$name" in
  [a-z]*) : ;;
  *) die "service name must start with a lowercase letter" ;;
esac
case "$name" in
  *[!a-z0-9-]*) die "service name must be kebab-case (lowercase letters, digits, hyphens only): '$name'" ;;
esac
[ -e "$dest" ] && die "destination already exists: $dest (refusing to overwrite)"

token="golden-$(printf '%s' "$gp" | tr '/' '-')"   # python/fastapi -> golden-python-fastapi

# ── copy (excluding build output + the lane selfcheck probe) ──────────────────
mkdir -p "$dest" || die "could not create $dest"
( cd "$GP_DIR/$gp" && tar \
    --exclude=node_modules --exclude=dist --exclude=build --exclude=.next --exclude=.astro \
    --exclude=coverage --exclude=target --exclude=__pycache__ --exclude=.venv --exclude=.pytest_cache \
    --exclude=selfcheck -cf - . ) | ( cd "$dest" && tar -xf - ) \
  || die "copy failed"

# ── rewrite the golden token -> the service name (SERVICE_NAME, image ref, manifest name) ─────────
# grep -I skips binary files; the token has no sed-special characters, and `|` is the delimiter.
while IFS= read -r f; do
  [ -n "$f" ] || continue
  sed -i "s|$token|$name|g" "$f"
done < <(grep -rIl -- "$token" "$dest" 2>/dev/null)

# ── minimal service README (the golden-path README is about the path, not this service) ───────────
cat > "$dest/README.md" <<EOF
# $name

Scaffolded from the \`$gp\` golden path (\`scripts/new-service.sh $gp $name\`). Conforms to the
golden-path contract: \`GET /health\` \`/ready\` \`/metrics\` \`/hello\`. Build → \`registry.weyland.lab/$name\`.

Run the tests the same way the golden path did (see the golden path at \`golden-paths/$gp\` for the
exact lane commands). Then wire it into the estate with the onboarding declaration below.
EOF

# ── onboarding declaration (what check-onboarding-completeness.sh + check-api-lifecycle.sh want) ──
camel="$(printf '%s' "$name" | awk -F- '{out=$1; for(i=2;i<=NF;i++){out=out toupper(substr($i,1,1)) substr($i,2)} print out}')"
cat <<EOF

Scaffolded $name from golden-paths/$gp  ->  $dest

Next steps (fill the <...> and the onboarding + API-lifecycle gates pass by construction):

# --- applications.yaml (append under \`applications:\`) ---
- {key: $name, deployed: true, metrics: true, ingress: <true|false>, name: <$name>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: $camel, port_component: $name,
   description: "<one line>"}

# --- apis.yaml (append under \`apis:\`) ---
- {id: $name, owner: $name, kind: openapi, status: published, version: "1.0",
   base: "http://$name.weyland.svc:8080",
   spec: docs/api/specs/$name.openapi.json, consumers: []}

# --- weyland.likec4 (add to the right zone) ---
$camel = component "<$name>" "<one line>"

Then: capture the OpenAPI/spec snapshot, run scripts/gen-api-contract-lock.sh, and the gates go green.
EOF
