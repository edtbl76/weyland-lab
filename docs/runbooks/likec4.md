# LikeC4 — architecture diagrams (B64)

The platform's **architecture / C4 diagrams** are a single LikeC4 model rendered two ways: a standalone interactive
explorer (`likec4.weyland.lab`) and **interactive embeds inside the docs** (`mkdocs-likec4`). Both build from one
source of truth. **Sequence / data-flow diagrams stay in Mermaid** (`docs/diagrams/flow-*.md`) — LikeC4 is only for
the structural C4 views.

## Why LikeC4 (and not Mermaid C4 or D2)

- **Mermaid C4** cramps and crosses edges past ~10 nodes; `c4-component-mother` (100+ directives) was unreadable.
- **D2 was evaluated and rejected** (B64): static SVG images render as a white box on the dark theme, shrink-to-fit
  to illegible on dense diagrams, non-interactive, and every diagram needs manual styling effort.
- **LikeC4** is model-based: define each element ONCE, and scoped views auto-generate the whole C4 hierarchy
  (landscape → node topology → mother's planes → per-plane / per-sub-zone). Output is **interactive** (pan / zoom /
  drill), theme-aware, and the monster diagram never exists as one dumped image — you drill into it.

## Source of truth

- **Model:** `docs/architecture/weyland.likec4` — the whole platform (system → nodes → planes → sub-zones →
  components) + relationships + view definitions. Edit this; everything else regenerates.
- **Project config:** `docs/likec4.config.json` (`{"name":"weyland"}`). **Must live under `docs/`** — see gotcha 2.
- Model structure: `weyland` (system) → `mother` (node) → `ai` / `mesh` / `ops` (zones); the dense planes `mesh`
  and `ops` are sliced into **sub-zones** (storage/query/stream/stores/ml/gov, edge/obs/platform/infra) so each
  view shows a handful of boxes, not 30 nodes. `rogueone` + external clouds are top-level.

## Two surfaces

**Standalone explorer — `likec4.weyland.lab`**
- `k8s/likec4/likec4.yaml` — a node initContainer runs `npm i -g likec4` then `likec4 build -o /site --base /
  --use-hash-history` from `/src/docs`; nginx serves the static interactive SPA. Keycloak forward-auth gated.
  Argo app `k8s/argocd/applications/likec4.yaml`.

**In-page embeds — `mkdocs-likec4`**
- `mkdocs-site.yml` has `- likec4` in plugins; the `docs-site` initContainer installs `nodejs npm`, `npm i -g
  likec4`, and `pip install mkdocs-likec4` before `mkdocs build`. The plugin shells out to the likec4 CLI to
  render each embedded view to an interactive web component at build time.
- Embed a view in any docs page (the **view-id goes in the BODY**, gotcha 1):
  ````
  ```likec4-view
  meshPlane
  ```
  ````
- Converted pages: `docs/diagrams/c4-context.md` (`index`), `c4-container.md` (`topology`),
  `c4-component-mother.md` (`mother` + `aiPlane` / `meshPlane` / `opsPlane`).

## Add or change a diagram

1. Edit `docs/architecture/weyland.likec4` — add/adjust elements + relationships; add a `view <name> of <element>
   { include * }` for a new scoped view.
2. To embed it in the docs, add a `likec4-view` fence (id in the body) to a page under `docs/`.
3. Push. Argo syncs the `likec4` app; **rollout-restart both** to rebuild from the fresh repo:
   `kubectl -n weyland rollout restart deploy/likec4 deploy/docs-site`.
4. **Verify the RENDER** (not just the build): the standalone at `likec4.weyland.lab` and a hard-refreshed embed
   page. A green build is not proof the diagram renders — see gotchas.

## Gotchas (all hit during B64 bring-up)

1. **`mkdocs-likec4` fence: view-id in the BODY, not the info string.** `` ```likec4-view `` then the id on the
   next line. Putting the id in the info string (`` ```likec4-view mother ``) is silently rejected and the fence
   renders as **raw mangled text** (it swallows following headings). The plugin README is the authority.
2. **The plugin only discovers `likec4.config.json` UNDER `docs/`** — it scans the docs tree, not the repo root.
   The model + config must live in `docs/` or the build logs `No projects discovered, using default root project`
   and every embed renders empty. (The standalone `likec4 build` is pointed at `/src/docs` to match.)
3. **`$` in a LikeC4 label is a substitution** (`${...}`) — a bare `$0` fails to compile (`substitutions must
   begin on {`). Reword (e.g. "zero cost") or escape.
4. **Nested elements are referenced by FULL dotted path** in relationships (`weyland.mother.mesh.stores.clickhouse`)
   — no bare ids from the model root.
5. **Dense planes need sub-zones.** A `view of X { include * }` over 30 flat components is unreadable even
   interactively; nest into sub-zones so the plane view shows ~6 boxes to drill into.
6. **Build reproducibility:** `npm i -g likec4` is unpinned for now (pin a version later); the standalone tar/CLI
   run on Alpine (node:22-alpine) fine.
7. **GitOps:** model lives in the repo the builds clone; a model change is live only after **push + rollout** of
   both `likec4` and `docs-site` (a manifest-only Argo sync won't rebuild the SPA if the pod template is unchanged).

## Links

- Model: [`docs/architecture/weyland.likec4`](../architecture/weyland.likec4) · config `docs/likec4.config.json`
- Manifests: `k8s/likec4/` · Argo app `k8s/argocd/applications/likec4.yaml`
- Plugin: <https://doubleslashde.github.io/mkdocs-likec4/> · LikeC4: <https://likec4.dev>
