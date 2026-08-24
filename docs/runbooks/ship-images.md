# Ship Images — verified build→deploy loop + open-PR lifecycle (B135 / B131)

`scripts/ship-images.sh` takes a pushed change from source to a **verified** rollout in one command,
and `k8s/pr-lifecycle/` alerts when a pull request is left open past its age budget.

---

## The problem this solves

The path from a source change to a running pod is seven steps. It is complete on both ends and was
broken in the middle — three of those steps could be skipped without anything going red:

| # | Step | How it failed silently |
|---|---|---|
| 1 | push to `main` | — |
| 2 | trigger the Woodpecker pipeline | triggered *before* the push landed → built the wrong sha |
| 3 | pipeline builds + pushes `registry.weyland.lab/<img>:git-<sha>` | — |
| 4 | `deploy-handoff` opens a tag-bump PR | **`curl -sf … \|\| exit 0`** — a 500 and a duplicate 422 were indistinguishable, and both left the step green (constraint **C9**) |
| 5 | you merge the PR | no reminder attached; PRs sat for days |
| 6 | Argo CD reconciles (~3 min poll) | nothing told you when |
| 7 | the pod restarts on the new tag | never checked — a merged PR is not evidence of a running pod |

Five runs on 2026-08-20 stumbled four times, every stumble a skipped step rather than a fault. The
cost is not lost minutes, it is **false confidence**.

**The design rule:** a gate that cannot verify itself is worse than no gate, because it produces a
green signal. Every gate below asserts against an authoritative source and the command refuses to
advance past any gate it cannot positively verify.

> The human merge step is **not** a review control. In a solo lab "reviewer", "approver" and
> "on-call" are the same person — so automating it costs no governance. What replaces it is the
> two-condition check in FR2.1 below.

---

## Prerequisites

Run on **rogueone** (the dev machine). `kubectl` is already pointed at mother's k3s.

### 1. `argocd` CLI — NOT installed by default

This is the one genuinely new dependency. It exists so the loop can trigger reconciliation instead
of waiting out Argo's ~3-minute poll. `docs/runbooks/argocd.md` **forbids**
`kubectl annotate app … argocd.argoproj.io/refresh=hard` and `kubectl patch` on the Application CRD;
the CLI is the runbook's own documented mechanism.

Installs to `~/.local/bin`, matching where `woodpecker-cli` already lives — no `sudo`:

```
curl -sSL -o /tmp/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
```

```
install -m 555 /tmp/argocd ~/.local/bin/argocd && rm -f /tmp/argocd
```

```
argocd login mother:30880 --username admin --password "$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)" --plaintext --grpc-web
```

> **`--plaintext`, not `--insecure`** (corrected 2026-08-24). `--insecure` means "TLS with a certificate I
> won't verify"; port 30880 serves **plain HTTP**, which is a different thing. With `--insecure` the CLI stops
> to ask `server is not configured with TLS. Proceed (y/n)?` — fine by hand, but it reads EOF and dies with
> `{"level":"fatal","msg":"EOF"}` in any non-interactive context. `--plaintext` states the intent and skips
> the prompt.

**The session token expires, and the failure is quiet.** When it does, `ship-images.sh` prints
`⚠ sync of <app> did not return cleanly` for every app and falls through to the live check — correct behaviour,
but with no forced reconcile `FR1.5` then races Argo's ~3-minute poll and can fail on a rollout that was merely
slow. Seen 2026-08-24. Verify the session rather than the login message:

```
argocd app list --grpc-web -o name
```

`invalid session: token has invalid claims: token is expired` means re-run the login above.

**Log in against the LAN NodePort, NOT `argocd.weyland.lab`.** The public host is behind Keycloak
forward-auth (`k8s/argocd/argocd-ingress.yaml`), and a CLI cannot complete a browser SSO round-trip —
`argocd login argocd.weyland.lab` fails at `POST /session.SessionService/Create` with **HTTP 400**,
which is the auth gate answering, not Argo. [argocd.md](argocd.md) still documents the public-host
form; it predates the 2026-06-25 sweep that put every UI behind forward-auth.

`k8s/argocd/argocd-lan.yaml` (added 2026-08-22) exposes `argocd-server` on `mother:30880`, exactly
the pattern `woodpecker-http-lan.yaml` uses for `woodpecker-cli`. It is **hand-applied** — Argo CD
does not manage itself, so `k8s/argocd/` is not GitOps-synced:

```
kubectl apply -f /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/argocd/argocd-lan.yaml
```

Both login flags are required: the server runs plain HTTP internally
(`configs.params.server.insecure: true`), so the native gRPC transport does not survive the hop
(`--grpc-web`) and there is no TLS on 30880 for the client to verify (`--insecure`).

### 2. `woodpecker-cli` — installed but **not configured**

Same forward-auth problem as Argo CD, already solved: point it at the LAN NodePort `mother:30980`
(`k8s/woodpecker/woodpecker-http-lan.yaml`), **not** `woodpecker.weyland.lab`, which 302s Bearer
calls to the Keycloak login page.

Credentials go in the gitignored `scripts/.env`, per the lab convention — never on a command line:

```
WOODPECKER_SERVER=http://mother:30980
WOODPECKER_TOKEN=<your PAT from the Woodpecker UI → user settings>
```

Load and verify:

```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && woodpecker-cli repo ls
```

> **`--output json` DOES NOT WORK.** The flag is accepted and silently ignored — you get the human
> table anyway, with no error. `ship-images.sh` therefore uses
> `--output 'go-template={{range .}}{{.Number}} {{.Status}}{{"\n"}}{{end}}'`. The `range` is
> required: the payload is a slice even for one pipeline, so a bare `{{.Number}}` fails with
> `can't evaluate field Number in type []*woodpecker.Pipeline`.

> **`pipeline last <repo>` returns 404** even on a repo with history. Harmless here — the loop uses
> `pipeline create` and `pipeline show <repo> <number>`, which take explicit arguments. Do not use
> `last` as a health check; use `repo ls`.

> **Trap:** `woodpecker-cli` loads `.env` from its working directory. A malformed one breaks it at
> startup with no useful message — a 2-byte junk `.env` at the repo root cost an hour on 2026-08-22.

### 3. `gh` — already authenticated

```
gh auth status
```

Needs the `repo` scope, which covers PR list / merge / close.

---

## Running it

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/ship-images.sh
```

**Run it against a no-op change the first time.** A failed gate then costs nothing, and every gate
still executes.

**From any directory, and with no `.env` sourcing.** The loop loads `scripts/.env` itself and resolves
every path from the git toplevel. Both were cwd-dependent until 2026-08-24, and the second one bit
hard: `woodpecker-cli` reads a `.env` from its **working directory**, so running the loop from
`nodes/.../tofu/port` handed the CLI Port's credentials file — four keys, no `WOODPECKER_*` — and
`pipeline create` failed unauthenticated. Sourcing `scripts/.env` by hand still works and is still
what the health check above uses; the loop no longer depends on your having done it.

### The gates, in order

| Gate | Asserts | Against |
|---|---|---|
| `FR1.2` | local `HEAD` == `origin/main` | git |
| — | *idempotence:* tag already live **and** no bump PR open → stop, "already deployed" | cluster + GitHub |
| `DETECT` | change detection **succeeded**, so an empty plan means "nothing changed" and not "the detector broke" | `scripts/ci/detect-changes.sh` |
| `FR1.3` | the pipeline reached `success` | Woodpecker API |
| `FR1.4` | the cluster is not already running this tag for the bumped image | live pods |
| `FR2.1` | the PR originates from the **base repo, not a fork** | GitHub API |
| `FR2.1` | every commit carries the `weyland-ci` git author name | GitHub API |
| `FR2.1` | the PR's diff touches **nothing but** image-tag lines | GitHub API |
| `FR1.5` | **every** bumped image is live on a pod | live pods |
| `SMOKE` | every bumped workload **declares a `readinessProbe`** and reports all replicas available | live Deployments + StatefulSets |
| `TXN` | every shipped service **answers a real transaction** | the service itself, in-cluster |

**The three FR2.1 conditions are not equally strong.** Same-repo is decided by GitHub and is unspoofable — it is
the load-bearing one, and `weyland-lab` is public with **no branch protection**, so it is the only thing standing
between a stranger's PR and `main`. The `weyland-ci` author name is a *convention* set by `git config`; anyone who
can write a commit can write that string. It is defence in depth behind same-repo, never provenance on its own.

**Why `SMOKE` fails on a missing probe rather than warning.** `FR1.5` proves the right *bytes* are on the node. A
workload with no `readinessProbe` reports `1/1 Ready` the instant PID 1 is alive — indistinguishable from genuine
health. Stack the two and you get a green ship report backed by nothing that asked the application a question.
Making it a hard failure turns the probe into a shipping requirement: a workload added without one fails loudly the
first time its image is bumped. Images with no matching Deployment/StatefulSet (CI images that run as Jobs) are
**named as unchecked** rather than silently passed, and an empty workload table fails closed.

**Why `DETECT` is a gate and not a quiet pre-check.** On 2026-08-24 the loop was run from
`nodes/.../tofu/port` with a real dbt-core/sqlparse bump committed on `main`. It printed
`✓ nothing to ship` and exited **0**; three images were genuinely stale. `detect-changes.sh` resolved both
of its inputs relatively, so from any directory but the repo root its `images.tsv` was not there — and the
row-reading `while` loop sits at the **end of a pipeline**, so `grep`'s exit 2 was replaced by the loop's
exit 0. An empty plan came back with a success status, and the caller (which ran the detector as
`>/dev/null 2>&1`) had thrown away the one line that said otherwise.

Both halves are fixed: the detector anchors every path to `git rev-parse --show-toplevel` and refuses to
report "nothing to build" when its manifest is unreadable, absent, or empty; the loop reads the detector's
**exit status** and keeps its output, aborting at `DETECT` rather than collapsing "found no work" into
"could not run". **The command is now safe to run from any directory.**

This was the fourth instance in this effort of a failed result standing in for a successful one — after
`woodpecker-cli --output json` being silently ignored, `curl -sf` collapsing every non-2xx to 0, and
`promtool` exiting 0 while printing `FAILED`. It is the direction that matters: this one shipped *nothing*
while reporting success, which is invisible until someone notices the deploy never happened.

**Why `TXN` exists on top of `SMOKE` (B140).** `FR1.5` proves the right bytes are on the node; `SMOKE` proves a
probe measured *something*. Neither asks the service to do its job — and on **2026-08-24** both were green for
`feast-server` while its **online store was completely empty**: Valkey held 228 keys, all Langfuse's `bull:*`,
zero Feast keys, and every entity key returned `null` including invented ones. The `/health` probe I had
upgraded it to two days earlier reported perfect health the whole time.

`TXN` runs one real transaction per shipped service:

| Image | Transaction | Asserts |
|---|---|---|
| `weyland-dagster-user-code` | Dagster GraphQL `workspaceOrError` | `loadStatus == LOADED` **and** the location is a `RepositoryLocation`, not a `PythonError` — the assertion the `tcpSocket 4000` probe cannot make, since binding a port is not loading definitions |
| `feast-server` | `POST /get-online-features` for a **real key sampled from the offline table** | the returned **value** is non-null |

**Assert the value, never the status.** Feast answers `statuses: ["PRESENT"]` with `values: [null]` for a key it
never materialized — `PRESENT` describes the response row, not a found feature. A status-based check would stay
green against an empty store forever, which is the vacuous-check class this gate exists to eliminate. The key is
sampled from Postgres rather than hardcoded, because a hardcoded key can quietly stop existing.

**It runs in-cluster via `kubectl exec`, deliberately.** Every UI except `feast.weyland.lab` sits behind Keycloak
forward-auth and answers an unauthenticated curl with `307`. The alternative — carrying a credential into the
ship path — would put Keycloak in the deploy critical path, which is a decision to argue for explicitly rather
than drift into. In-cluster sidesteps it. Images with no transaction defined (CI images that run as Jobs) are
**named as unverified**, never silently passed.

All three gates read the same diff file, so it is deleted only after **every** one has run — deleting it early is
how `FR1.5` once passed on an empty image list, verifying nothing.

Superseded older bump PRs are closed **before** the newer one merges. Merging `#12` after `#13`
rolls images backwards.

---

## What a failure means

The command names the gate that stopped it. Cleanup is best-effort and never masks the reason.

**`FR1.2`** — you have unpushed commits, or `origin/main` moved. Push, then re-run. Nothing was
triggered; there is nothing to clean up.

**`FR1.3`** — the build failed. The failing step's log is printed inline, not just a status. Common
causes: `unpigz invalid deflate` = an oversized image layer (CUDA torch — use the CPU wheel);
buildkitd unreachable = check `k8s/woodpecker/buildkitd.yaml`.

**`FR1.4` "pipeline succeeded but opened no image-bump PR"** — this is C9 caught from the outside.
Either `deploy-handoff` genuinely failed (check its step log) or nothing needed rebuilding. The
command distinguishes them: if the tag is already live it exits 0 with "nothing to ship".

**`FR2.1` "not CI-authored"** or **"touches more than image-tag lines"** — deliberate refusal. The
PR is left open for you. Read the diff: something other than a tag moved, and that is exactly the
case automated merge must not handle.

**`FR1.5`** — merged and synced, but no pod carries the tag within 5 minutes. Check whether the Argo
app actually synced (`argocd app get <app>`), then whether the pod can pull the image
(`kubectl -n weyland describe pod <pod>` — `ImagePullBackOff` means the registry push half failed).

### Recovering from a half-completed run

The failure modes are ordered by how much state got created:

1. **Aborted before merge** — the command deletes the orphan `ci/image-bump-<sha>` branch itself.
   If that cleanup also failed it says so *underneath* the real reason; delete the branch by hand.

   **It now asks GitHub first, and fails closed.** `ORPHAN_BRANCH` is set right after the trigger and
   cleared only once the PR lookup succeeds, so an abort *between* those two points — which is where
   the 2026-08-24 run died, at `FR1.3`, after `deploy-handoff` had already opened PR #36 — used to
   reach cleanup with a branch that was not orphaned at all. It printed
   `deleting orphan branch ci/image-bump-dab283e9`; only an ISP outage stopped the delete from
   landing. Cleanup now checks for an open PR on that branch and keeps it if one exists, **or if
   GitHub cannot be reached** — a wrong "no PR" destroys the run's own output, a wrong "yes" leaves a
   branch the staleness watchdog surfaces the next morning.
2. **Merged but not rolled out** — do **not** re-run to "fix" it. The manifests already carry the
   tag; the problem is downstream. Sync the app and inspect the pod.
3. **Registry has a tag the manifests never received** — the dangerous one. Manifests are both the
   *input* to change detection (they carry the old sha) and its *output*, so the next run will diff
   from a stale sha and think nothing changed. Re-run `ship-images.sh` on a fresh commit; detection
   compares the manifest tag, so a correct bump PR is regenerated.

---

## Open-PR staleness watchdog (B131)

A CronJob in `k8s/pr-lifecycle/` asks GitHub which PRs are open across **all six active repos** —
`Algopedia`, `ServiceTransformation`, `emangini-tailwind-nextjs-contentlayer`, `startme-curator`,
`stud.io`, `weyland-lab` — applies an age budget, and POSTs a synthetic alert to the Alertmanager v2
API. Override the set for a scoped run with `PR_REPOS`.

A failure on any single repo is **fatal to the run**, not skipped: the counts must never quietly
describe a shrunken watch set. Every repo is still attempted, so one bad repo does not hide the rest.

> This is **not** the same six the `github-weyland` Port integration maps — Port carries
> `midi_real_book`, this set carries `startme-curator`. Reconciling coverage across the toolset is
> **B138**, not something to fix by quietly editing one list to match the other.

| PR kind | Identified by | Budget |
|---|---|---|
| CI image bump | branch prefix `ci/image-bump-` | **1 day** |
| everything else | — | **7 days** |

The branch prefix — not the author — is the signal: the prefix says what the PR *is*, the author only
says who pushed the button.

**Why not a `PrometheusRule`:** no metric in this cluster describes a GitHub pull request
(constraint **C3**). No pushgateway, no textfile collector, no GitHub exporter. There is no `expr`
to write.

- **No Alertmanager routing change is needed.** The top-level route is a catch-all to `telegram`,
  so an alert carrying `severity` + `summary` + `description` renders through the existing template.
- **It runs once a day, at 05:45 NY — not every 30 minutes.** Synthetic alerts carry no `endsAt`, so
  Alertmanager auto-resolves them after `resolve_timeout` (5m) and treats the next firing as a NEW
  alert. That makes the CronJob's cadence the Telegram notification rate: `*/30` would send ~48
  messages a day per stale PR. It would also violate `docs/schedules.md` **Design Rule #5** (no
  mid-day auto-runs, incident-driven 2026-08-07). The budgets here are measured in days, so a daily
  check is at most a few hours late.
- **The decision logic lives in a ConfigMap**, not inline in the container args, because
  `scripts/tests/pr-staleness.bats` extracts and executes that exact text. A tested copy sitting
  beside the deployed copy drifts, and the drift is silent.

### The GitHub token (one-time, on mother)

**A fourth token, read-only.** Three GitHub tokens already exist (CI `Contents:write` +
`Pull requests:write`, an IaC repo-scoped PAT, and a user token) — but none is deliverable to the
cluster today, and reusing the CI one would put a write-capable credential in a job that only lists
PRs. Least privilege wins; a PAT costs nothing.

1. Create a fine-grained PAT on `edtbl76/weyland-lab` with **`Pull requests: read`** and nothing else.
2. Put it in the gitignored `scripts/.env` as `PR_TOKEN`, per the lab convention. **Never paste a
   credential into a command line**, and do not use a silent `read` either — a `read -rs` that
   captures nothing produces a Secret with an *empty* value, which k8s accepts happily and which
   fails at runtime as `GITHUB_TOKEN not set`. That happened on 2026-08-22.
3. Create the Secret from the `.env` value, and **verify the stored length before trusting it**
   (`b64len` should be `ceil(chars/3)*4` — a mismatch means a stray newline or a truncated paste):

```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && echo "PR_TOKEN is ${#PR_TOKEN} chars" && kubectl -n weyland create secret generic pr-lifecycle-github --from-literal=token="$PR_TOKEN" && kubectl -n weyland get secret pr-lifecycle-github -o go-template='{{range $k,$v := .data}}{{$k}} b64len={{len $v}}{{"\n"}}{{end}}'
```

4. Then seal it (`weyland/pr-lifecycle-github` is already on the allow-list in
   `nodes/mother/lab/weyland-platform/scripts/seal-secrets.sh`):

```
/home/emangini/lab/weyland-platform/scripts/seal-secrets.sh --seal
```

3. Copy the sealed CR back into the repo and push — Argo applies it:

```
rsync -a ~/sealed-out/weyland__pr-lifecycle-github.yaml /home/emangini/lab/weyland-platform/k8s/sealed-secrets/sealed/
```

Verify the Secret decodes before the CronJob's next run — a Secret that exists but holds the wrong
bytes fails identically to one that is missing:

```
kubectl -n weyland get secret pr-lifecycle-github -o jsonpath='{.data.token}' | base64 -d | head -c 8
```

---

## Tests

The shell is tested. `ship-images.sh` merges PRs on `main` and syncs the live cluster, so its
decisions are exactly the kind that must not be verified by running them — every external binary
(`git`, `gh`, `woodpecker-cli`, `argocd`, `kubectl`, `curl`) is stubbed onto `PATH`.

```
docker run --rm -v "$PWD:/code:ro" -w /code bats/bats:latest scripts/tests/
```

`scripts/tests/detect-changes.bats` covers the detector separately, because it is the one component
whose *silence* is indistinguishable from a correct answer. Its first two cases are a matched pair —
the same fixture run from the repo root and from a subdirectory — so a green "works from elsewhere"
cannot come from a broken fixture. The fail-closed cases assert the **reason** in the output, not just
a non-zero exit: `[ "$status" -ne 0 ]` alone passes on exit 127, which is how a test written to prove
the SMOKE gate failed closed passed against a function that did not exist (2026-08-23).

Also runs in CI as the blocking `shell-tests` step in `.woodpecker.yml`, beside `shellcheck` — the step
runs `bats scripts/tests/` over the whole directory, so a new suite file needs no CI change.

---

## Related

- [argocd.md](argocd.md) — the sync mechanism and why the refresh annotation is forbidden
- [code-quality.md](code-quality.md) — the scan-suite gate
- `docs/schedules.md` — the CronJob's slot
- `scripts/ci/images.tsv` — which images are in change detection. **Nine are not** (`weyland-operator`,
  `weyland-mcp-gateway`, `weyland-mcp-compositor`, `weyland-guard`, `weyland-agent`,
  `realm-of-agents`, `ray-head`, `a2a-inspector`, `mcp-server-datahub`); `ranger` is deliberately
  version-pinned and excluded. Bringing those nine in is **B135 phase 2** — until it ships,
  `ship-images.sh` reports success while a third of the fleet is unwatched.
