# Secrets management — SealedSecrets (B69)

As of **B69 Wave 2**, the cluster's imperative secrets are **GitOps-managed via Bitnami SealedSecrets**. The 53
credentials we created by hand (`kubectl create secret …`) are now **sealed into the public repo** and restored by
Argo — closing the "reproducible-from-git / secrets-restorable" gap. Encrypted `SealedSecret` CRs are safe in a
public repo: **only this cluster's controller private key can decrypt them.**

For *what each secret holds* and how to regenerate individual values, see [data-mesh-secrets.md](data-mesh-secrets.md)
(the shapes/regeneration table). This page is the **mechanism**: how sealing, restore, rotation, and escrow work.

## How it works

```
kubectl get secret <name> -o yaml ──kubeseal──▶ SealedSecret CR (encrypted) ──git push──▶ Argo (sealed-secrets-manifests)
                                                                                                    │ apply
                                                                    controller (kube-system) ◀──────┘
                                                                                    │ decrypt with private key
                                                                                    ▼
                                                                    real Secret (adopted, ownerRef=SealedSecret)
```

- **Controller**: `kube-system/sealed-secrets-controller` (chart `sealed-secrets` 2.19.1 / controller v0.37.0),
  installed by the `sealed-secrets` Argo app (`k8s/argocd/applications/b69-onboarding.yaml`). Watches all namespaces.
- **Sealed CRs**: `k8s/sealed-secrets/sealed/<ns>__<name>.yaml`, applied by the `sealed-secrets-manifests` Argo app
  (`prune:false` — it never auto-deletes a live Secret). Argo shows this app `Progressing` (no health check exists
  for the CRD) — that's normal; the `ownerReferences[0].kind: SealedSecret` on each live Secret is the real proof.
- **Sealer**: `scripts/seal-secrets.sh` holds the **explicit allow-list** — the single source of truth for what is
  sealed. Adoption of a pre-existing secret works because the script annotates it `sealedsecrets.bitnami.com/managed: "true"`
  before sealing, so the controller takes it over in place (identical value → no disruption).

## What is and isn't sealed

**Sealed (53):** every credential we created imperatively — nothing else recreates them, so they must be in git.
The authoritative list is the `SECRETS=(…)` array in `scripts/seal-secrets.sh`.

**Deliberately NOT sealed** (do not add these):
- **Chart/operator-generated** secrets — their chart/operator recreates them on install, so they're already
  reproducible: `datahub-{gms,auth,encryption,secret}`, `superset-{config,env}`, `lightdash{,-secret}`,
  jupyterhub `hub`, `prerequisites-kafka-*`, all prometheus-operator `alertmanager-*`/`prometheus-*`,
  `monitoring-kube-prometheus-admission`, `gatekeeper-webhook-server-cert` (the last two are rotating webhook certs
  — pinning them would break rotation).
- **TLS/CA** (`weyland-wildcard-tls`, `weyland-mkcert-ca`) — mkcert-regenerable, replicated across namespaces, and
  they expire. Regenerate from the mkcert CA on a rebuild instead.

## ⚠️ The controller key is a bricking key — ESCROW IT

The controller auto-generated a private key on first start (Secret labelled
`sealedsecrets.bitnami.com/sealed-secrets-key` in kube-system). **Every committed SealedSecret can only be decrypted
by this key.** If it's lost and a fresh controller generates a new one, all 53 committed CRs become undecryptable and
the sealed values are gone. It was escrowed at install:

```
kubectl -n kube-system get secret -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > sealed-secrets-key.backup.yaml
```

Keep `sealed-secrets-key.backup.yaml` **off-cluster** (password manager / offline store). Re-export it if the key
is ever rotated.

### Also raw-escrow the 3 truly-bricking values

Three sealed secrets brick their app *and* can't be regenerated if both the live secret and the controller key are
ever lost at once. Keep their decoded values off-cluster too, as defense-in-depth:

- `weyland/glitchtip-secret` → Django `SECRET_KEY` (invalidates all sessions/tokens if changed)
- `data-mesh/lakefs-secret` → `encrypt-key` (`LAKEFS_AUTH_ENCRYPT_SECRET_KEY`) — decrypts lakeFS's stored creds in Postgres
- `n8n/n8n-secret` → `N8N_ENCRYPTION_KEY` — decrypts stored n8n workflow credentials

## Restore on a fresh cluster

1. Install the controller (Argo syncs the `sealed-secrets` app), then **restore the escrowed key** and restart so it
   adopts it instead of generating a new one:
   ```
   kubectl -n kube-system apply -f sealed-secrets-key.backup.yaml
   kubectl -n kube-system rollout restart deploy/sealed-secrets-controller
   ```
2. Argo applies `sealed-secrets-manifests` → the controller decrypts all 53 CRs → live Secrets reappear.
3. Regenerate the *unsealed* classes: TLS/CA from mkcert; chart-generated secrets come back with their charts.

## Rotate / re-seal a secret

Update the live secret, then re-seal (the script overwrites the CR in place):
```
kubectl -n <ns> create secret generic <name> --from-literal=<k>=<newval> --dry-run=client -o yaml | kubectl -n <ns> apply -f -
~/seal-secrets.sh --seal   # on mother; rsync ~/sealed-out/ -> repo k8s/sealed-secrets/sealed/ ; commit + push
```

## Add a NEW secret to the sealed set

Create it imperatively, add its `ns/name` to the `SECRETS=(…)` allow-list in `scripts/seal-secrets.sh`, then
`--seal` → rsync → push. It'll be adopted on the next Argo sync.
