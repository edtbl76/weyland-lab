# Flow: self-syncing IDP (B41)

The weyland IDP tracks the repo with no manual republish, via **two mechanisms** — chosen by whether the
artifact needs a build. The **catalog** needs no build, so Backstage's UrlReader fetches it live from public
GitHub (`type: url`, polled ~150s) and re-ingests on change — no ConfigMap copy. **TechDocs** is servable
HTML that cannot live in the repo, so a Dagster job builds it hourly and publishes to MinIO, which Backstage
serves. Catalog reads use `raw.githubusercontent.com` (uncompressed); the GitHub API path is avoided.

```mermaid
sequenceDiagram
    participant Git as GitHub (edtbl76/weyland-lab, public)
    participant Dag as Dagster (weyland_techdocs_job, hourly)
    participant S3 as MinIO (techdocs bucket)
    participant IDP as weyland IDP (Backstage)
    participant U as Developer (browser)
    Note over Git,IDP: Catalog path (no build, fetch live)
    IDP->>Git: UrlReader polls catalog yaml (~150s, raw.githubusercontent)
    Git-->>IDP: entities, ingest and re-stitch on change
    Note over Dag,S3: TechDocs path (build then publish)
    Dag->>Git: shallow clone repo
    Dag->>Dag: mkdocs build (techdocs-core)
    Dag->>S3: publish site (default/component/weyland-docs)
    Note over U,S3: Serve
    U->>IDP: open Docs tab
    IDP->>S3: fetch static TechDocs site
    S3-->>U: rendered docs
```
