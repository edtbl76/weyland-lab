# Demo — weyland-tool-server health, retrieval and failure checks (B239)

The checks in [runbooks/tool-server.md](../runbooks/tool-server.md), run against the live service on 2026-11-08.
Routes: [api.md § Tool server](../api.md). The request paths are already drawn in the RAG and act-guard flows
(`flow-e2e-rag`, `flow-act-tool`).

## CLI walkthrough

**1. Health in one call.**

```bash
curl -s http://192.168.1.243:30080/status | python3 -c "import json,sys; d=json.load(sys.stdin); print('status', d['status'], '| llm', d['llm']['status'], '| embedder loaded', d['model']['loaded']); print({k: v.get('status') for k, v in d.get('backends', {}).items()})"
```

Seen: `status ok | llm ok | embedder loaded True` and all four backends `ok`. Every per-backend route
(`/pgvector/health` … `/ollama/health`), `/health`, `/ready` and `/models` answered 200.

**2. Retrieval.** A search for `woodpecker-cli pipeline create edtbl76/weyland-lab --branch main` returned
`weyland-image-ci.md` and `woodpecker.md` (similarity 0.78) on both pgvector and Qdrant. The natural-language
question "how do I trigger a CI pipeline run" returned unrelated documents (`ci-reliability-signal.md`, `eval.md`).
That is the known retrieval-precision limit (B74), recorded in the runbook's symptom table, not a fault.

**3. Guard hooks.** All nine `tool_server_guard_failures_total` series read 0.

**4. Negative case.** `GET /context%2Fsearch` and `GET /neo4j%5Chealth` both returned
`HTTP 400 {"detail":"encoded path separators are not accepted"}` (the B207 refusal).

The act-path denial (`toolserver-act-gateway-only`) was not exercised from outside on purpose: if the policy were
wrong, the call would launch a real run. Its enforcement is already proven: [act-guard.md](act-guard.md) step 1
(a direct act from the LAN gets `RBAC: access denied 403`), and CI asserts the same on every run
(`scripts/integration/guard-blackbox.sh` step 5).

## Cleanup

None: health reads and one retrieval query. Nothing is written.
