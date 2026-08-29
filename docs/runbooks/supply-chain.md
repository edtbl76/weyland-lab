# Runbook — Software supply chain (SBOM · signing · provenance · licences)

**B88 Phase 3.** SBOM generation, image signing, SLSA provenance and licence scanning for every image
this lab builds. Tooling: `scripts/supply-chain.sh`, invoked per pushed image by
`scripts/ci/build-images.sh`. Admission policy: `k8s/gatekeeper/image-signatures.yaml`.

**Why this exists:** before B88 every one of these concepts lived in this repo as *knowledge* and
nowhere as *implementation* — `syft`, `cosign`, `sigstore`, SBOM, CycloneDX, SPDX, SLSA, provenance,
attestation and Renovate appeared only under `knowledge-repos/`. The lab documented a supply chain
it did not have.

- **Registry:** `quality-tools.yaml` → `runner: supply-chain` (5 tools; `check-quality-tools.sh` fails on drift)
- **Tests:** `scripts/tests/supply-chain.bats` (14 cases) · `scripts/ci/check-rego-policies.sh` (Rego compile + behaviour)
- **Related:** [code-quality.md](code-quality.md) (the scan-suite) · [B88 in the backlog](../backlog.md)

---

## The three exit codes, and why they are not interchangeable

```
0  the step ran and reported clean
1  the step ran and FOUND something   (unsigned image, licence violation)
2  the step COULD NOT RUN             (missing tool, missing key, bad arguments)
```

`1` and `2` must never be collapsed. "We looked and it is unsigned" and "we never looked" are
different facts, and this repo has repeatedly shipped the second while reporting the first.

---

## ⚠ OPERATOR SETUP — required once, and nothing signs until it is done

Until these two steps are complete, **every image ships unsigned**. The build does not fail (an
unsigned image is a gap, not a broken build) but it logs loudly on every push.

### 0. Install cosign — it is on NEITHER mother NOR rogueone

Found the hard way 2026-08-28: `cosign: command not found` on both hosts. It is a single static
binary, so this needs no package manager and no `sudo` — fetch it to `~` and invoke it by path.

```
curl -sSfL -o ~/cosign https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 && chmod +x ~/cosign && ~/cosign version
```

(CI does not depend on this: the `build` step fetches its own copy per run, because `moby/buildkit`
is upstream's image and not ours to rebuild.)

### 1. Generate the signing key pair and seal it

Run **on mother**. `COSIGN_PASSWORD=""` is deliberate: CI has no TTY to enter a passphrase, and the
key's protection is the SealedSecret plus cluster RBAC, not a password sitting in a CI variable.

```
cd ~ && COSIGN_PASSWORD="" ~/cosign generate-key-pair && kubectl -n weyland create secret generic cosign-signing-key --from-file=cosign.key=./cosign.key --from-file=cosign.pub=./cosign.pub
```

Then seal it into git (`cosign-signing-key` is already on the allow-list in `seal-secrets.sh`).

**⚠ mother has NO repo checkout** — the established convention is a mirrored subtree at
`~/lab/weyland-platform/...` (see `docs/validation/test-commands.md`), so the script must be rsync'd
from the repo on rogueone BEFORE running. Skipping that is how it drifts: on 2026-08-28 a loose
`~/seal-secrets.sh` was found on mother, predating the `cosign-signing-key` allow-list entry — it
would have sealed every other secret, reported success, and silently omitted this one.

**On rogueone (push the current script):**
```
rsync -a /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/seal-secrets.sh emangini@mother:~/lab/weyland-platform/scripts/seal-secrets.sh
```

**On mother (seal):**
```
cd ~/lab/weyland-platform/scripts && ./seal-secrets.sh --seal
```

**⚠ ESCROW THE PRIVATE KEY OFF-CLUSTER**, alongside `glitchtip-secret`. Losing it means every image
already signed can no longer be verified against the public key shipped in the Gatekeeper policy —
the same bricking class as the sealed-secrets controller key.

### 2. Provision the Woodpecker CI secrets

The `build` step declares `secrets: [cosign_key, cosign_password]`. Add them in the Woodpecker UI
(Repo → Settings → Secrets), since Woodpecker secrets are UI-only state:

- `cosign_key` — the contents of `cosign.key`
- `cosign_password` — empty

---

## Operate

Everything runs automatically per pushed image via `build-images.sh`. To run a step by hand:

```
bash scripts/supply-chain.sh all registry.weyland.lab/weyland-agent:git-abc1234
```

Individual subcommands — `sbom` · `sign` · `attest` · `verify` · `licenses`.

**SBOM output** lands in `$WEYLAND_SBOM_DIR` (default `/tmp/weyland-sbom`), two files per image:

```
<image>.cyclonedx.json   CycloneDX 1.7 — feeds vulnerability tooling
<image>.spdx.json        SPDX-2.3     — feeds licence / compliance
```

Both formats are emitted deliberately: they answer to different consumers, and shipping one while
calling it "an SBOM" is half an artifact.

**Verify an image by hand:**

```
COSIGN_PUBKEY=/path/to/cosign.pub bash scripts/supply-chain.sh verify registry.weyland.lab/weyland-agent:git-abc1234
```

---

## Admission control — and its honest limitation

`k8s/gatekeeper/image-signatures.yaml` ships in **`enforcementAction: dryrun`**. Every image running
today is unsigned; `deny` would reject all of them on the next pod creation and the cluster would not
recover until the policy was deleted.

**Gatekeeper cannot verify signatures.** Its Rego runs in the admission path with no network egress,
so it cannot call cosign or reach the registry. The constraint therefore asserts the checkable
thing — images must come from `registry.weyland.lab/` — while real cryptographic verification runs
in CI via `cosign verify` before anything is deployed.

That is a real limitation, stated rather than hidden. Full in-cluster verification needs a controller
that can reach the registry (Kyverno + cosign, or sigstore-policy-controller). Separate decision.

**⛔ DO NOT `kubectl apply` THIS — the path is Argo-managed with `selfHeal: true`.**

`k8s/gatekeeper/` is owned by the **`gatekeeper-constraints`** Argo Application, so a hand-apply is
reverted to git main HEAD within minutes. Worse, it fails *quietly*: `kubectl apply` prints
`configured` for both resources and the live object simply does not change. Measured 2026-08-28 —
live Rego 1083 bytes, repo 1978, after two applies that both reported success.

**The deploy is the push.** Commit the policy, let Argo sync it, then read the audit. This is the
same selfHeal mechanism recorded in the `argocd-gitops-gotchas` memory, which is also why
`argocd app rollback` and `kubectl rollout undo` are traps here.

A hand-apply is legitimate only for the **first** creation of the ConstraintTemplate on a cluster
that has never seen it — and even then it is two phases, not one:

**The two-phase gotcha (first creation only)**

The ConstraintTemplate *generates* the `K8sImageSignature` CRD, so the constraint that uses that kind
cannot be applied in the same pass — the first apply creates the template and then fails with
`no matches for kind "K8sImageSignature" ... ensure CRDs are installed first`. That is expected, not
a broken manifest; `constraints.yaml` carries the same warning. Wait for the CRD to be established,
then apply again:

```
kubectl apply -f /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/gatekeeper/image-signatures.yaml ; kubectl wait --for condition=established --timeout=60s crd/k8simagesignature.constraints.gatekeeper.sh && kubectl apply -f /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/gatekeeper/image-signatures.yaml
```

(Runs from **rogueone** — kubectl reaches the cluster from either host, and the file lives in the repo
there, so no rsync is needed. After this first creation, every subsequent change goes through git.)

**Read the audit:**

```
kubectl get k8simagesignature require-signed-images -o jsonpath='{.status.totalViolations}{"\n"}'
```

### Promoting to `deny` — do not skip a step

1. Sign everything. The ship loop signs images as they are rebuilt, but images that are **not**
   rebuilt stay unsigned indefinitely. Enumerate what is actually running:
   ```
   kubectl get pods -A -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' | sort -u
   ```
2. Watch `totalViolations` until it reads zero. Gatekeeper audits on an interval, so a fresh zero
   means "zero at the last audit", not "zero now" — confirm it holds across at least two cycles.
3. Only then flip `enforcementAction: dryrun` → `deny`, and keep `exemptImages` honest.

---

## Gotchas

- **The OPA image is distroless** — no shell, no python. `check-rego-policies.sh` therefore runs in
  `python:3.12-slim` with the OPA binary fetched, not in `openpolicyagent/opa`.
- **Rego v0, not v1.** Gatekeeper uses v0 and every ConstraintTemplate here is written in it; OPA's
  own default is now v1, which rejects both. `opa check --v0-compatible` is mandatory — checking with
  the wrong dialect reports false errors on correct policy.
- **`kubeconform` skips Gatekeeper CRDs** (no schema), which is why the Rego needs its own CI step.
  Before B88 nothing validated it at all: an inverted policy would have shipped and silently admitted
  everything.
- **Keyless signing is not usable here.** It needs Fulcio/OIDC over the internet; this lab is
  LAN-only, hence the key pair.
- **A signature is not provenance.** `cosign sign` vouches for a blob; `cosign attest` records *which
  commit, which pipeline, which builder*. Only the second answers "rebuilt from what?".
