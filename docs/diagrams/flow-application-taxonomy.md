# Flow — Application taxonomy (B82): one registry → four surfaces

How the app-classification propagates from the single source of truth to DataHub, Port, docs, and the drift guard.
Sequence (Mermaid); the architecture placement is in `arch.md §7f` + the LikeC4 model.

```mermaid
sequenceDiagram
    autonumber
    participant REG as applications.yaml<br/>(registry — SoT)
    participant JOB as datahub_catalog_emit_job<br/>(Dagster)
    participant EMIT as emit_applications()
    participant GMS as DataHub GMS
    participant TF as tofu/port/applications.tf
    participant PORT as Port
    participant CHK as check-app-registry.sh

    Note over REG: 54 components (29 data-app + 25 pure-compute)<br/>+ excluded[] (stores / plumbing)

    rect rgb(230,240,255)
    Note over JOB,GMS: DataHub surface (baked into the image)
    JOB->>EMIT: run (after the store/domain/product emits)
    EMIT->>REG: yaml.safe_load — datahub_application:true rows
    EMIT->>GMS: 29 Application entities (ApplicationProperties + customProperties)
    EMIT->>GMS: Application Capabilities glossary (node + 30 terms)
    EMIT->>GMS: per app — Docs link · Tag(group) · Domain · Terms(capabilities)
    loop every dataset/chart/dashboard
        EMIT->>GMS: ApplicationsClass → first-match owning app (URN pattern)
    end
    GMS-->>EMIT: (29, 4157)
    end

    rect rgb(235,255,235)
    Note over TF,PORT: Port surface (same file, no rebuild)
    TF->>REG: yamldecode(file(...))
    TF->>PORT: for_each → 54 component entities<br/>(is_data_application + datahub_application_url)
    Note over PORT: relations UNMANAGED (exporter owns k8sWorkload);<br/>depends_on blueprint (avoid the mid-modify null race)
    end

    rect rgb(255,245,230)
    Note over CHK: Drift guard (CI / DoD sweep)
    CHK->>REG: applications[].key + port_component + excluded[].key
    CHK->>CHK: diff vs live Argo apps (+ alias map)
    Note over CHK: ✅ 72 Argo apps all accounted → exit 0
    end
```

**The invariant:** nothing reaches DataHub or Port that isn't in `applications.yaml`, and every deployed Argo app must
appear there (as a component or in `excluded:`) or the guard fails. Drift is impossible by construction, not discipline.
