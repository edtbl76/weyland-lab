# Demo — LikeC4 architecture diagrams (B64)

**What this shows:** the architecture (C4) diagrams are ONE LikeC4 model rendered two ways — an interactive
standalone explorer (`likec4.weyland.lab`) and interactive embeds inside the docs — and how to change a diagram
(edit the model, rebuild, verify the render). Read-only to view; the "change" walkthrough edits the model.

**Diagram/runbook:** [runbooks/likec4.md](../runbooks/likec4.md) · model: `docs/architecture/weyland.likec4`.

## Prerequisites

- The `likec4` and `docs-site` Deployments are Running (`kubectl -n weyland get deploy likec4 docs-site`).
- Keycloak SSO reachable (both surfaces are forward-auth gated).

## UI walkthrough — explore the model

1. **Standalone explorer** — open <https://likec4.weyland.lab>. The left nav is a clean tree:
   - top-level overviews: **weyland — system landscape** (home) · **node topology** · **rogueone — GPU edge** ·
     **mother — the three planes** · **AI plane**;
   - a **Data mesh /** folder (overview · storage + catalog · query + BI · streaming · Tier-2 stores · feature
     store + ML · governance);
   - an **Ops /** folder (overview · ingress + SSO + DNS · observability · delivery + governance · infra + tooling).
2. Open **weyland — node topology** → confirm the MS-A2 topology: `mother`, `hermes`, `whisper` (no `openclaw` —
   dropped B28; Ollama shows on `rogueone`, not a CT). **Drag to pan, scroll to zoom.**
3. Open **mother — the three planes**, then click into **Data mesh / Tier-2 stores** → the 9 Tier-2 stores as a
   focused view (not 30 nodes at once — the point of the sub-zones). Click any node for its details.
4. **In-page embed** — open <https://docs.weyland.lab> → **Architecture** (arch.md §2): the System context renders
   as the SAME interactive `index` view inline. Also **Diagrams → C4 Context / Container / Component (mother)**.

**Expected:** every view is interactive (pan/zoom/drill), theme-matched to the dark docs, and consistent between
the explorer and the embeds because they build from the one model.

## CLI walkthrough — change a diagram end-to-end

The model is the single source of truth; a change flows to both surfaces on rebuild.

1. Edit the model (add or adjust an element / relationship / view):
   ```
   $EDITOR docs/architecture/weyland.likec4
   ```
2. Push (both builds clone the repo), then rebuild both — on **mother**:
   ```
   kubectl -n weyland rollout restart deploy/likec4
   kubectl -n weyland rollout restart deploy/docs-site
   ```
3. Watch the build render the model (look for a clean `likec4 build` / `mkdocs build`, no `err:` and the
   `weyland` project discovered) — on **mother**:
   ```
   kubectl -n weyland logs -f -c build $(kubectl -n weyland get po -l app=likec4 --sort-by=.metadata.creationTimestamp -o name | tail -1)
   ```
4. **Verify the RENDER**, not just the build (the B64 lesson — a green build is not proof): hard-refresh
   `likec4.weyland.lab` and the embedded page and confirm your change appears.

**Expected:** the edit shows in the explorer AND the docs embeds after the rebuild.

## Gotchas to reproduce (if a diagram won't render)

- **In-page embed shows raw text** → the `likec4-view` fence needs the view-id in the **body**, not the info
  string, and the model must live UNDER `docs/`. See [runbooks/likec4.md](../runbooks/likec4.md).
- **`likec4 build` errors** → a `$` in a label (substitution) or a bad dotted path; the log names the line.

## Cleanup

**Read-only demo** for viewing. The CLI walkthrough only edits the model in git — revert your test edit (or don't
commit it) and rebuild; nothing is created in any datastore.
