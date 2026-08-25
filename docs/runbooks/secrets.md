# Secrets management — SealedSecrets (B69)

As of **B69 Wave 2**, the cluster's imperative secrets are **GitOps-managed via Bitnami SealedSecrets**. The **56**
credentials we created by hand (`kubectl create secret …` — 53 in the B69 Wave 2 batch + the `kiali` signing-key (B89)
+ `ranger-admin-secret` (B92) + `datamesh-store-creds` (SEC-1) + `cron-freshness-woodpecker` (B135)
+ `port-pr-reconcile-creds` (B144)) are now **sealed
into the public repo** and restored by
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

**Sealed (55):** every credential we created imperatively — nothing else recreates them, so they must be in git.
The authoritative list is the `SECRETS=(…)` array in `scripts/seal-secrets.sh` — this count trails it, so when the
two disagree the array wins (it read 53 here against 54 in the array before B135 added the 55th).

**Deliberately NOT sealed** (do not add these):
- **Chart/operator-generated** secrets — their chart/operator recreates them on install, so they're already
  reproducible: `datahub-{gms,auth,encryption,secret}`, `superset-{config,env}`, `lightdash{,-secret}`,
  jupyterhub `hub`, `prerequisites-kafka-*`, all prometheus-operator `alertmanager-*`/`prometheus-*`,
  `monitoring-kube-prometheus-admission`, `gatekeeper-webhook-server-cert` (the last two are rotating webhook certs
  — pinning them would break rotation).
- **TLS/CA** (`weyland-wildcard-tls`, `weyland-mkcert-ca`) — mkcert-regenerable, replicated across namespaces, and
  they expire. Regenerate from the mkcert CA on a rebuild instead.

### Getting a credential OUT of a chart-generated secret (the `extraEnvRaw` pattern)

A chart-generated secret is reproducible precisely because the chart templates it **from your values file** — so the
plaintext lives in git even though the secret itself isn't sealed. You cannot fix that by editing the secret: it is
Helm-owned (`heritage=Helm`) and Argo reverts hand-added keys on the next sync.

Override it at the **container** level instead. An explicit `env:` entry always outranks the same name arriving via
`envFrom:` — a Kubernetes precedence rule, not an ordering coincidence — so the chart's key becomes inert:

1. Dump the live pod spec first and confirm where the value actually comes from, for **every** consumer (web pods,
   workers, and any init/migration Job — they frequently differ):
   `kubectl -n <ns> get deploy,job -o jsonpath='{range .items[*]}{.kind}/{.metadata.name}{"\n"}{range .spec.template.spec.containers[*]}  {.name} env={.env[*].name} envFrom={.envFrom[*].secretRef.name}{"\n"}{end}{end}'`
2. Seal the **live** value straight out of the existing secret — byte-identical, no rotation, no paste-mangling:
   `kubectl -n <ns> create secret generic <new> --from-literal=KEY="$(kubectl -n <ns> get secret <chart-secret> -o jsonpath='{.data.KEY}' | base64 -d)" --dry-run=client -o yaml | kubeseal --format yaml > <ns>__<new>.yaml`
3. Add the chart's raw-env hook (`extraEnvRaw`, or `envFromSecrets`/`extraSecretEnv` depending on chart) pointing at
   the sealed secret, and check the chart source that the hook renders in **all** relevant templates.
4. Replace the values field with an inert placeholder and comment *why* it's inert.

Live example: superset `connections.db_pass` → `superset-db-pass` SealedSecret (SEC-1/EMA-84). Immutable Jobs may need
a one-time delete, though Argo often recreates them itself. Verify against something that truly exercises the cred —
for superset that's the `superset-init-db` migration Job succeeding, **not** `/health`, which never touches Postgres.

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

> ⚠ **YOU CANNOT FIX A SEALED SECRET IN THE CLUSTER. Updating the live Secret does not stick.**
> `sealed-secrets-manifests` runs `selfHeal: true`, so Argo re-applies the sealed CR **from git** and the
> controller rewrites the Secret back to the sealed value within minutes. Observed end to end on
> 2026-08-25 (B147) — every intermediate step reported success:
>
> ```
> kubectl apply (real creds)        -> clientId len 32, HTTP 200   ✅
> kubeseal -> new CR -> apply       -> HTTP 200                    ✅
> rollout restart the consumer      -> ~90 s
> kubectl get secret                -> clientId len 7, "YOUR_ID"   ❌ reverted
> ```
>
> The revert arrives on Argo's sync interval, so a verify **immediately after** the change passes and the
> real state comes back a few minutes later. Same family as the `argocd app rollback` trap.

**The sequence that works.** Order matters: `secretKeyRef` injects env vars at pod start, so the restart
must come AFTER the sync, not before.

```
# 1. update the live Secret (so kubeseal has something to read)
kubectl -n <ns> create secret generic <name> --from-literal=<k>=<newval> --dry-run=client -o yaml | kubectl -n <ns> apply -f -

# 2-3. annotate + seal ONE secret into the repo (the two commands seal-secrets.sh runs per entry)
kubectl -n <ns> annotate secret <name> sealedsecrets.bitnami.com/managed=true --overwrite
kubectl -n <ns> get secret <name> -o yaml | kubeseal --format yaml > nodes/mother/lab/weyland-platform/k8s/sealed-secrets/sealed/<ns>__<name>.yaml

# 4. COMMIT + PUSH — without this the next Argo sync undoes everything above
# 5. wait for the app to report Synced on the new revision, THEN restart the consumer
kubectl -n <ns> rollout restart deploy/<consumer>
```

**Seal only the ONE secret you changed**, not `--seal` across the whole allow-list: each seal produces
fresh ciphertext, so a full run rewrites all 56 CRs and buries the real change in the diff.

**Verify by decoding the STORED value and authenticating with it** — never by `DATA n`. See the guard below.

## The placeholder guard (B147)

```
bash scripts/check-secret-placeholders.sh          # assert
bash scripts/check-secret-placeholders.sh --list   # per-key verdicts + accepted exceptions
```

**Why it exists.** `weyland/port-creds` held the literal strings `YOUR_ID` / `YOUR_SECRET` for **63 days**.
Sealed ✅, committed ✅, Argo-applied ✅, `DATA 2` ✅, mounted by a running pod ✅ — and it authenticated to
nothing, so the B62 AI-Dev Usage pipeline never wrote a single entity. Pillar 6 asks whether secrets are
**restorable**, and the honest answer was yes: a full restore faithfully reproduced a 401. A placeholder
and a real credential are byte-indistinguishable from outside; only decoding and looking finds it.

It reads the allow-list **out of** `seal-secrets.sh` rather than duplicating it, decodes every value, and
fails on placeholder vocabulary or an empty value. It fails closed on an unparseable allow-list, an
unreadable Secret, or a secret that is allow-listed but absent from the cluster.

**Not in CI, deliberately.** It must read Secrets, and step pods run as `woodpecker:default` which cannot
(`kubectl auth can-i get secrets -n weyland` → no). Wiring it in means granting CI cluster-wide secret read
to run a lint — a permanent broad privilege for a periodic check. Run it at DoD time and after any secret
change. The durable form is a CronJob with a scoped SA alongside the `pr-lifecycle` watchdogs.

**The false-positive problem is the hard half.** A guard that cries wolf on a legitimate secret gets muted,
and a muted guard is worth nothing. The discriminator: a credential is a **short, single-line** token;
config is long or multi-line. `data-mesh/clickhouse-users` holds an XML document beginning `<clickhouse>`
and was flagged by the first version's `<[a-z-]+>` pattern. Accepted exceptions live in the `ACCEPTED`
array with the condition that justifies each one — same posture as `check-pip-audit-ignores.sh`.

**It found a second problem on its first live run.** An empty `password` in `data-mesh/trino-metrics-auth`
is legitimate (Trino's metrics endpoint ignores it, `k8s/data-mesh/trino.yaml:154`) — but verifying that
claim revealed Trino exports **no metrics to Prometheus at all**, with a 59-day-old ServiceMonitor. Filed
as **B148**.

## Add a NEW secret to the sealed set

Create it imperatively, add its `ns/name` to the `SECRETS=(…)` allow-list in `scripts/seal-secrets.sh`, then
`--seal` → rsync → push. It'll be adopted on the next Argo sync.
