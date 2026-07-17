#!/usr/bin/env bash
# B69 Wave 2 — seal the imperative cluster secrets into git-safe SealedSecret CRs.
# Run on MOTHER (needs kubectl cluster access + kubeseal + the sealed-secrets controller in kube-system + jq).
#
#   ./seal-secrets.sh            # DRY RUN — prints every secret it WOULD seal (review this first)
#   ./seal-secrets.sh --seal     # actually annotate-managed + seal each → writes CRs to $OUT
#
# Then: rsync "$OUT"/  ->  repo k8s/sealed-secrets/sealed/ , commit + push -> Argo applies them.
# The controller adopts the EXISTING secret (via the `sealedsecrets.bitnami.com/managed` annotation we add) and
# reconciles it to the sealed value — which is identical to the live value, so nothing is disrupted.
#
# What it seals: type Opaque + kubernetes.io/tls, in the app namespaces below, that aren't already sealed-managed.
# (SA-token and helm-release secrets are a different type → auto-excluded. kube-system / istio SA tokens skipped.)
set -euo pipefail
OUT="${OUT:-$HOME/sealed-out}"
NAMESPACES="${NAMESPACES:-weyland data-mesh monitoring minio n8n jupyterhub gatekeeper-system}"
SEAL=0; [ "${1:-}" = "--seal" ] && SEAL=1

command -v kubeseal >/dev/null || { echo "kubeseal not found"; exit 1; }
command -v jq       >/dev/null || { echo "jq not found (apt install jq)"; exit 1; }

[ "$SEAL" = 1 ] && { mkdir -p "$OUT"; echo "sealing -> $OUT"; } || echo "DRY RUN — nothing sealed. Add --seal to write CRs."

count=0
for ns in $NAMESPACES; do
  kubectl -n "$ns" get secrets -o json 2>/dev/null | jq -r '.items[]
    | select(.type=="Opaque" or .type=="kubernetes.io/tls")
    | select(.metadata.annotations["sealedsecrets.bitnami.com/managed"] != "true")
    | .metadata.name' | while read -r name; do
      if [ "$SEAL" = 1 ]; then
        kubectl -n "$ns" annotate secret "$name" sealedsecrets.bitnami.com/managed=true --overwrite >/dev/null
        kubectl -n "$ns" get secret "$name" -o yaml | kubeseal --format yaml > "$OUT/${ns}__${name}.yaml"
        echo "  sealed      $ns/$name"
      else
        echo "  would seal  $ns/$name"
      fi
  done
done
echo "---"
[ "$SEAL" = 1 ] && echo "Done. rsync '$OUT/' -> repo k8s/sealed-secrets/sealed/ , then commit + push (Argo applies)." \
                || echo "Review the list above. Re-run with --seal when it looks right."
