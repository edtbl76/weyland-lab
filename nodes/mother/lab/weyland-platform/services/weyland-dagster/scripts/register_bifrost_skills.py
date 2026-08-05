#!/usr/bin/env python3
"""Idempotent Bifrost Skills Repository loader (B111) — GitOps-durable source of truth for the Agent Skills.

Bifrost's Skills Repository stores Anthropic-style Agent Skills (frontmatter fields + a SKILL.md body + optional bundled
files) and SERVES them as a Claude Code / Codex plugin marketplace (/api/skills/serve/claude-code/.claude-plugin/
marketplace.json). So these skills are installable straight into the coding agents. This script is the durable source of
truth — a PVC wipe loses the repo, re-run to rebuild it. Mirrors register_bifrost_prompts.py. Run:
    kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/register_bifrost_skills.py
(B102: also reconciled automatically by the Dagster `registrations` group — asset bifrost_skills_registered — weekly + on-demand.)

API contract (reverse-engineered from /app/main, 2026-08-01; prefix /api/skills):
- POST /api/skills {name, version, description, skill_md_body, compatibility, allowed_tools, license, metadata} -> {skill:{id}}
  name = kebab-case (lowercase/digits/single-hyphens); version = semver MAJOR.MINOR.PATCH; skill_md_body non-empty.
  Frontmatter (name/description/license/compatibility/allowed_tools) are COLUMNS — skill_md_body is the BODY only;
  Bifrost reconstructs the full SKILL.md when serving. GET/DELETE /api/skills/{id}; versions at /api/skills/{id}/versions.

DESIGN (per the 2026-08-01 scoping decision): lab-operational skills (codifying weyland runbooks + hard-won gotchas) PLUS
a handful of generic dev skills. compatibility=claude-code,codex; allowed_tools left broad so a skill works in any agent.
Idempotent: skills created only if absent (matched by name).
"""
import os
import httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
VERSION = "1.0.0"
COMPAT = "claude-code,codex"

# (name, category, description, body). body = SKILL.md instructions (no frontmatter — that's the columns).
SKILLS = [
    # ============================ deploy / gitops ============================
    ("deploy-via-argo", "deploy",
     "Deploy a change to the weyland k3s cluster the GitOps way: edit the manifest, push, let Argo CD sync.",
     """Use when deploying or changing anything on the weyland cluster.

The cluster is GitOps via **Argo CD** — you do NOT `kubectl apply` to deploy. The flow is:
1. Edit the manifest in the repo (under `k8s/`).
2. Commit and **push** — Argo detects the change and syncs (auto-sync, or the user syncs in the UI).
3. Verify the rollout: `kubectl -n weyland rollout status deploy/<name>` (kubectl runs on **mother**).

Gotchas:
- After editing manifests, always **remind the user to push** and name the exact file paths — an un-pushed manifest never deploys.
- CRDs / configs over ~256KB exceed the last-applied-annotation limit → add `argocd.argoproj.io/sync-options: ServerSideApply=true`.
- A Helm-based Argo app's `releaseName` must match the live release or Argo re-installs a duplicate.
- Do NOT hand-edit live resources (`kubectl edit`) — it drifts from git and Argo reverts it. Change git instead."""),

    ("dagster-redeploy", "deploy",
     "Redeploy the Dagster user-code image after a pipeline change — new registry tag, bump BOTH deployments.",
     """Use when shipping a change to the Dagster pipeline (weyland-dagster / weyland_pipeline).

`redeploy.sh` is OBSOLETE. The real flow:
1. **rsync the source to mother FIRST** (`rsync`, never scp) — if you build before syncing, the image bakes STALE source. A Docker `Using cache` line on the COPY layer means the new code did NOT ship.
2. Build a **new image with a NEW registry tag** and push to `registry.weyland.lab`.
3. Bump that tag in **BOTH** `k8s/.../dagster/user-code.yaml` **AND** `dbt-docs.yaml` — they share the image; missing one leaves half the system on old code.
4. Push → Argo rolls both.

Verify the code-location loaded in the Dagster UI (no import error) before declaring done."""),

    ("bifrost-restore", "deploy",
     "Rebuild the Bifrost gateway from git after a PVC loss — clients, VK scoping, prompts, in this exact order.",
     """Use to restore the Bifrost agent-gateway (MCP clients, virtual-key tool scoping, prompt repo) after a PVC wipe.

Order matters — each step depends on the prior:
1. Apply `bifrost.yaml` (the `mcp-runtime` initContainer stages node+chromium for stdio MCP servers).
2. `kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_mcp_clients.py` — recreate MCP clients (API).
3. `kubectl -n weyland exec -i deploy/bifrost -c bifrost -- /runtime/usr/bin/python3 - < scripts/attach_bifrost_vk_mcp.py` — attach clients to VKs. The governance **API cannot attach** runtime-registered clients ("failed to get MCP client: not found"); this writes the `governance_virtual_key_mcp_configs` join by INTEGER PK, resolved by client name.
4. `kubectl -n weyland rollout restart deploy/bifrost` — REQUIRED: the /mcp multiplexer builds its per-VK tool registry in memory at boot; tools do NOT flow until this.
5. `... exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_prompts.py` — reload the Prompt Repository.
6. Re-authorize Hugging_Face + Linear in the Bifrost UI (OAuth grant is interactive)."""),

    ("sealed-secrets", "deploy",
     "Manage cluster secrets as GitOps with Sealed Secrets — encrypt, commit, and adopt without bricking.",
     """Use when adding or rotating a Kubernetes secret that must live in the (public) git repo.

Secrets are GitOps via **Sealed Secrets** — never commit a plain `Secret`. Encrypt with `kubeseal` against the cluster's controller cert, commit the `SealedSecret`, and Argo/the controller decrypts it in-cluster.

Gotchas:
- The controller works by an **allow-list**, not a filter — a `SealedSecret` only unseals for the exact name+namespace it was sealed for.
- **The controller's private key is a bricking risk** — back it up. Lose it and every SealedSecret is unrecoverable.
- To adopt an existing plain Secret under Sealed Secrets, add the `sealedsecrets.bitnami.com/managed: "true"` annotation first, or the controller refuses to overwrite it."""),

    # ============================ diagnose / ops ============================
    ("diagnose-pod-oom", "ops",
     "Diagnose an OOM-killed pod on the single-node cluster and find the memory culprit.",
     """Use when a pod restarted unexpectedly or the cluster feels starved.

**mother is a single k3s node**, so one pod OOM can cascade into a total outage, and there is **no node-OOM alert** — you have to look.
1. Confirm the kill: `kubectl -n weyland describe pod <pod>` → look for `OOMKilled` / exit 137.
2. Find what the kernel killed and why: on mother, `journalctl -k | grep -i oom` — the `oom_memcg` / `Killed process` lines name the cgroup and the RSS at kill time.
3. Identify the heavy tenants: `kubectl top pods -n weyland --sort-by=memory` (historic culprits: trino, cassandra, mlflow, opensearch, sonarqube).

Fixes: raise the victim's limit if legitimate, or cap the hog. Note B79 moved Ollama off mother to rogueone and grew mother to 64GB, which resolved the chronic ~97%-committed wall."""),

    ("k8s-rwo-recreate", "ops",
     "Set the correct update strategy for single-instance workloads on a ReadWriteOnce volume.",
     """Use when writing or reviewing a Deployment that mounts a ReadWriteOnce PVC with a single replica.

Single-instance RWO Deployments (qdrant, neo4j, weaviate, postgres, n8n, bifrost, and similar) MUST use:
```yaml
strategy:
  type: Recreate
```
With the default `RollingUpdate`, the new pod tries to mount the RWO volume while the old pod still holds it → the volume is `Multi-Attach`-blocked and the rollout **deadlocks** (new pod `ContainerCreating` forever, old pod never terminates). `Recreate` tears down the old pod first. This is correct regardless of node count."""),

    ("prove-layer-before-fixing", "ops",
     "Isolate which side of a client/server boundary is actually broken with one decisive diagnostic before fixing.",
     """Use when a request fails across a boundary (client↔server, app↔proxy, pod↔service) and the cause is ambiguous.

Do NOT start fixing the side you assume is broken. Run ONE decisive diagnostic that isolates the layer:
- **App vs Istio/Envoy:** hit the app on the pod's **loopback** (`127.0.0.1:<port>`) — that bypasses the inbound sidecar. Works on loopback but not via the Service → it's Envoy/mesh. Fails on loopback too → it's the app.
- **DNS vs connectivity:** resolve the name, then connect to the resolved IP directly.
- **Auth vs transport:** retry with auth stripped / a known-good token.

One clean isolation beats three speculative fixes. Read the ACTUAL error and the FULL logs — don't grep for the pattern you expect to find (confirmation bias); the freeze/failure is often not where you assumed."""),

    ("join-istio-mesh", "ops",
     "Wire a new in-cluster client to a strict-mTLS service (Postgres, Neo4j) so it doesn't fail opaquely.",
     """Use when a new in-cluster workload must talk to a mesh service and you get an opaque `ECONNRESET` / connection reset.

weyland Postgres (and peers) run **STRICT mTLS**. A client that is NOT in the Istio mesh has no client cert → the sidecar resets the connection with no useful error.
- Ensure the client's namespace/pod has **sidecar injection** (istio-injection) so it presents a mesh identity, OR add an explicit `PeerAuthentication`/`DestinationRule` exception (discouraged).
- Confirm the client SA matches any `AuthorizationPolicy` that gates the service.

Separately, **long-lived bulk connections stall behind Envoy** (e.g. Neo4j Bolt bulk loads): add a `DestinationRule` with `connectionPool.tcp.tcpKeepalive` for that host, or Envoy silently drops the idle-looking long connection mid-transfer."""),

    # ============================ data mesh ============================
    ("wake-sleep-store", "data-mesh",
     "Wake or sleep a data-mesh store on demand via the Port → store-scaler path.",
     """Use to bring a parked data-mesh store (ClickHouse, Cassandra, a vector store, etc.) up or down without hand-scaling.

The lab has a wake/sleep "easy button": a Port self-service action → the self-hosted **port-agent** → the **store-scaler** service → scales the store's Deployment/StatefulSet. Trigger it from Port rather than `kubectl scale`, so state stays consistent with the catalog.

Notes: the sticky-sleep behavior (auto-sleep after idle) is PARKED — stores stay whatever you set them to. For a Tier-2 store that must serve real queries, wake it AND confirm its data is hydrated (see `tier2-store-hydration`) before pointing a consumer at it."""),

    ("datahub-emit-governance", "data-mesh",
     "Emit DataHub governance (domains, data products, glossary) from git via the custom emitter.",
     """Use to publish or update DataHub catalog governance for the data mesh.

On DataHub 1.13 the standard ingestion paths for governance are dead — the lab emits **from git** via a custom emitter (`weyland_pipeline/datahub_emit.py`): domains, data products, and glossary terms are declared in the repo and pushed with `MetadataChangeProposalWrapper`s.

Connection: use the **in-cluster GMS service URL** (not the ingress) and mint a **service token via the admin API** — UI-created tokens die on a GMS reset; durable tokens go in `acryl-datahub-actions` extraEnvs. Table-level Stats come from the ingestion-source profiling; custom-emitted stores (qdrant/weaviate/etc.) need a `DatasetProfile` (rowCount) emitted directly."""),

    ("swap-embedding-model", "data-mesh",
     "Swap the RAG embedding model correctly — all four embedders, matched query/index dims.",
     """Use to change the embedding model behind retrieval (e.g. bge-small → bge-base).

The query embedder and the index embedder MUST produce the same dimension, or retrieval silently returns garbage. The RAG stack has **four embedders** (across the tool-server and the ingest pipeline) — swap ALL of them together.

Steps (see runbook `embedding-model-swap.md`): update the model name (e.g. `BAAI/bge-base-en-v1.5`, 768-dim) everywhere, keep the topic-prefix convention if used, **re-embed / re-index the whole corpus** (old vectors at the old dim are unusable), then re-run the golden eval set to confirm precision didn't regress. B74 established bge-base(768)+topic-prefix beats bge-small on identifier-heavy queries."""),

    ("tier2-store-hydration", "data-mesh",
     "Hydrate a Tier-2 store (ClickHouse, Cassandra) from lakeFS using native ingest.",
     """Use to load a Tier-2 analytical store from the lakehouse.

Hydrate via **native S3-from-lakeFS ingest**, not a row-by-row loader:
- **ClickHouse:** `INSERT ... SELECT ... FROM s3('<lakeFS-s3-endpoint>/...', ...)` — native `s3()` table function reads the parquet directly. DataHub's SQLAlchemy source needs the CH password via a `users.d/` XML drop-in (not the DSN). Size ~8Gi.
- **Cassandra:** single-node, 3G heap. Rows with an empty partition key must map to a `__UNKNOWN__` sentinel or the insert rejects. Watch the headless-service DNS race on startup (client connects before the pod is Ready).

Confirm row counts against the lakeFS source after load; a partial ingest looks "done" but under-counts."""),

    # ============================ llm / eval ============================
    ("run-eval-suite", "llm",
     "Run the weyland RAG eval suite (3 lanes) and score it — deliberately, it's long-running.",
     """Use to evaluate RAG quality after a retrieval/model/prompt change.

B84 is a **3-lane eval suite** (a panel of judges, `mlflow.evaluate`, and Promptfoo) over a ~20-question golden set (conceptual + lexical) — it is NOT a model bake-off. Trigger it through the tool-server act tools:
1. `POST /evals/run` (via the gateway `/mcp-act`, or the operator) — generates the question set and runs all models. **Long-running (~40-60 min of CPU)** and it competes with the single loaded Ollama model. Fire deliberately.
2. When that completes, `POST /evals/score` — judge-panel scoring (~70 min).

Read results in MLflow (traces + eval runs). Note the golden set once overturned a prior premise (dense retrieval wins on identifiers), so let the numbers, not intuition, decide."""),

    ("use-model-gateway", "llm",
     "Route an LLM call to the right weyland gateway lane — LiteLLM vs MLflow Gateway vs Bifrost.",
     """Use when wiring any component to the lab's LLMs, so it lands on the correct lane.

Lane separation matters:
- **Agentic / tool-calling → LiteLLM** (transparent proxy; preserves tool schemas). Use the use-case aliases: `wl-coding`, `wl-agentic`, `wl-rag`, `wl-reason`, `wl-judge`, `wl-search`, `wl-default`, `wl-speed`, `wl-big-oss` — each has a server-side fallback chain ending in a free/always-on rung, so a call always lands. Point at the alias, not a raw model.
- **Chat / eval → MLflow AI Gateway** (normalizing; adds guardrails/budget) — but it **breaks tool schemas**, so never use it for tool-calling.
- **Agent MCP tools → Bifrost** (`bifrost.weyland.lab/mcp`, virtual-key auth) — the agent-edge front door for MCP, separate from the LLM lanes.

$0 budget: prefer the free hosted (groq/gemini/cerebras) and local (ollama) rungs; paid providers are escalation-only in the fallback chains."""),

    ("remote-training-rogueone", "llm",
     "Run a model-training job on rogueone (GPU) with the MinIO registry and persistent Ray.",
     """Use to train/fine-tune on the rogueone GPU box (RTX 5000 Ada, 16GB).

Key rule: **build the training/ray image ON rogueone, not mother** — rogueone's docker trusts the `registry.weyland.lab` mkcert CA; mother's build-docker does NOT (push → `x509: certificate signed by unknown authority`). k3s on mother PULLS fine (trust is separate). Do NOT rsync the repo to rogueone — it syncs itself via git.

Flow: build+push the image on rogueone → bump the tag in `k8s/ray/ray-head.yaml` (Argo rolls the head) → submit from mother: `kubectl -n weyland exec deploy/ray-head -- ray job submit --address http://localhost:8265 -- python /home/ray/train_genre.py --source mart`. Env parity is everything for the native edge worker (patch-exact Python + pinned pyarrow/numpy/pandas/boto3). MLflow artifacts must write DIRECT to MinIO (`s3://` artifact_location), not through the serve-artifacts proxy (gunicorn timeout on large models)."""),

    # ============================ meta ============================
    ("weyland-conventions", "meta",
     "The house rules for operating in the weyland lab — SSH, hosts, tooling, budget, workflow.",
     """Load this before doing operational work in the weyland lab. The non-negotiable conventions:

- **SSH** as user `emangini` (NOT `edwardmangini`). Refer to machines by **hostname** (`mother`, `rogueone`), never bare IPs, in commands you hand the user.
- **Transfer files with `rsync`, never `scp`** — the user reacts strongly to scp.
- **`kubectl` runs on mother.** Give mother-side commands; don't assume a repo checkout on rogueone.
- **Commands: one line each, no backslash continuations, no placeholders** — resolve pod names/creds inline via `$(...)`. Put the runnable command LAST in your message.
- **Provide commands; don't run** operational mutations the user should run themselves. Confirm before NEW changes (propose → yes → build); remove old/broken things FIRST.
- **$0 budget** — free tiers + self-hosted only; no paid models/services unless explicitly funded.
- **Workflow:** this project uses its own AIDLC workflow (NOT superpowers). Design docs go under `aidlc-docs/` (gitignored); the canonical backlog is `docs/backlog.md`. It's a homelab — weigh for experimentation and learning, don't over-engineer.
- **git:** the user handles ALL git; never give git info or commit for them."""),

    # ============================ content / knowledge ============================
    ("distill-doc", "content",
     "Turn a lab-specific docs page into a generic, shareable writeup of the underlying process/concept — strips lab specifics + secrets, outputs a Google Doc.",
     """Use when the user wants to turn an internal docs-site page into a generic, shareable writeup of the underlying process, concept, or technique — stripping everything lab/org-specific so it can be handed to someone outside.

**Input:** one or more source pages — a repo markdown path or a docs-site URL. Read the FULL source before writing anything.

**Generalize — this is the whole point:**
- **STRIP** every organization-specific: proper nouns (project/service/pod/host names, internal codenames), IPs, hostnames, URLs, backlog/ticket numbers, internal file paths, ports, and anything secret or credential-shaped. **A shared doc must never leak internal topology or secrets — a hard rule, not a nicety.** When a concrete detail is load-bearing, replace it with a generic placeholder (`<your-gpu-host>`, `a 16GB GPU`, `the ingestion service`), never the real value.
- **KEEP** the transferable substance: the technique, the *why* (decision rationale + tradeoffs), the gotchas and failure modes, and the ordered steps. That is what the reader is there for.
- **DEFAULT: keep ONE concrete worked example** with generic values — a reader learns more from "here's how it looks" than pure abstraction. An `--abstract` flag drops worked examples.
- Preserve structure (headings, numbered steps); convert any org-specific diagram to a generic one. **Title the output by the concept, not the source page.**

**Output:**
- **Default → a Google Doc** via the Google Drive/Docs MCP; return the shareable link (PDF = one-click download from Docs).
- `--md` → write generalized markdown to a scratch file instead.

**Before finalizing, show a short audit** — Stripped / Kept / ⚠️ possibly-still-identifying — so the user can catch over- or under-generalization. Multiple pages → offer to combine into one writeup or one Doc each."""),

    # ============================ generic dev ============================
    ("systematic-debugging", "generic",
     "Debug any failure by isolating the layer and proving the fix, instead of guessing.",
     """Use on any bug, test failure, or unexpected behavior — before proposing a fix.

1. **Reproduce** it reliably; capture the exact error and FULL output (don't pre-grep for the pattern you expect).
2. **Isolate the failing layer** with one decisive diagnostic that splits the system in half (loopback vs proxy, unit vs integration, with/without input X).
3. **Form one hypothesis** that explains ALL the evidence, not just the convenient part.
4. **Fix, then verify with the SAME reproduction** — a fix isn't real until the original repro passes.

Anti-patterns: fixing the layer you assumed without proving it; declaring success without re-running the check; changing several things at once so you can't tell what worked."""),

    ("pin-your-deps", "generic",
     "Pin dependency versions and verify in a throwaway before shipping, to avoid silent drift outages.",
     """Use when writing a Dockerfile or install step, or when a service that "worked for weeks" suddenly breaks.

Unpinned installs (`pip install fastapi some-lib`) let a later rebuild pull incompatible versions that hang or crash — a real weyland outage came from fastapi-mcp 0.4.0 silently pulling starlette 1.x. Rules:
- **Pin the whole interacting set** to versions you validated, not just the top-level package.
- Before rebuilding a production image, **validate the exact version combo in a throwaway** (a scratch pod / venv) — prove the handshake/behavior, THEN build.
- Record WHY each pin exists in a comment, so a future bump is deliberate."""),

    ("verify-before-done", "generic",
     "Never claim work is complete without running the verification and reading the output.",
     """Use before saying anything is fixed, passing, complete, or deployed.

Evidence before assertions, always:
- Run the ACTUAL verification command (the test, the health probe, the end-to-end call) and READ its output — don't infer success from "it should work."
- Confirm the specific behavior you claim: if you say "/mcp returns tools," show the tools/list result; if you say "no hang," show the 200.
- If a step was skipped or a test failed, say so plainly with the output. Report outcomes faithfully — done-and-verified stated plainly, gaps stated as gaps."""),

    ("idempotent-register-script", "generic",
     "Write a GitOps-durable register script that (re)creates external resources idempotently.",
     """Use when codifying UI/PVC-managed state (API resources, catalog entries) as a durable, re-runnable script.

Pattern (see register_bifrost_mcp_clients.py / _prompts.py / _skills.py):
- The script's data structure is the **source of truth** in git; running it makes the target match.
- **Resolve references by NAME, not by generated ID** — IDs are reassigned on a restore; names are stable.
- **Idempotent**: fetch existing (by name), create only what's absent; never duplicate on re-run.
- Make each item's write **atomic**; on partial failure, don't leave half-state.
- If the change needs a reload to take effect (in-memory caches), the script should say so — a DB/state write alone often does nothing until a restart."""),
]

def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    existing = {s["name"] for s in c.get("/api/skills?limit=1000").json().get("skills") or []}   # limit: default is 50, we have more
    created = skipped = 0
    for name, category, description, body in SKILLS:
        if name in existing:
            skipped += 1; continue
        r = c.post("/api/skills", json={
            "name": name, "version": VERSION, "description": description,
            "skill_md_body": body, "compatibility": COMPAT, "allowed_tools": "",
            "license": "MIT", "metadata": {"category": category},
        })
        ok = r.status_code < 300
        print(f"skill  {'CREATED' if ok else 'FAILED '} [{category}] {name}{'' if ok else ' ' + r.text[:140]}")
        created += ok
    print(f"\ndone. {created} created, {skipped} existing. {len(SKILLS)} skills total.")

if __name__ == "__main__":
    main()
