# Flow — ServiceMonitor coverage (B148): three planes, one verdict

Why a binary "is it scraping?" check could not have caught `data-mesh/trino`, and what replaced it.
Sequence + decision matrix (Mermaid); architecture placement is in `arch.md` + the LikeC4 model.

## The bug it exists to catch

```mermaid
flowchart LR
    subgraph M["ServiceMonitor trino"]
      SEL["selector:<br/>matchLabels: app=trino"]
    end
    subgraph S["Service trino"]
      LAB["metadata.labels:<br/><b>{} — EMPTY</b>"]
      PSEL["spec.selector:<br/>app=trino"]
    end
    POD["Pod trino<br/>labels: app=trino"]

    SEL -- "matches SERVICES by<br/>their own labels" --x LAB
    PSEL -- "matches PODS<br/>(worked fine)" --> POD

    LAB -.->|no match| NOPOOL["Prometheus creates<br/><b>no scrape pool</b>"]
    NOPOOL --> NOSIG["up{job=trino} -> <i>no data</i><br/>Grafana panel -> empty<br/>kubectl get sm -> 60d"]

    style LAB fill:#ffdddd,stroke:#cc0000
    style NOPOOL fill:#ffdddd,stroke:#cc0000
    style NOSIG fill:#fff4dd,stroke:#cc8800
```

**Both selectors said `app: trino`.** One matches Services by `metadata.labels`, the other matches pods
by `spec.selector` — different objects entirely. Every affirmative check came back clean for 59 days,
because the condition produces *no series at all* rather than a bad one.

## The guard

```mermaid
sequenceDiagram
    autonumber
    participant CJ as servicemonitor-coverage<br/>(CronJob 02:45 NY)
    participant API as kube-apiserver
    participant PROM as Prometheus
    participant RES as resolver (python)
    participant CLS as classify()

    Note over CJ: unmeshed — both targets have no sidecar<br/>read-only SA, 4 list verbs, no pods/proxy

    CJ->>API: list servicemonitors · services · deploy/sts/ds
    API-->>CJ: (HTTP status checked on every fetch — fail closed)
    CJ->>PROM: GET /api/v1/targets?state=any
    PROM-->>CJ: activeTargets[]

    RES->>RES: ServiceMonitor.selector → Service.metadata.labels
    RES->>RES: Service.spec.selector → workload template labels
    Note over RES: intended = .spec.replicas (a cached read of git —<br/>Argo selfHeal on 75/78 apps keeps it honest)<br/>actual = .status.readyReplicas<br/>unresolvable → -1

    loop every ServiceMonitor
    CLS->>CLS: classify(intended, actual, targets)
    end
```

## The decision matrix

```mermaid
flowchart TD
    A["classify(intended, actual, targets)"] --> V{"non-negative int<br/>or the -1 sentinel?"}
    V -- no --> ERR["exit non-zero<br/><i>never default to 0</i>"]
    V -- "-1" --> U{"targets > 0?"}
    U -- yes --> UM["<b>unmanaged</b><br/>apiserver · kubelet"]
    U -- no --> OR["<b>orphan</b><br/>← trino"]
    V -- "&ge;0" --> I{"intended > 0?"}

    I -- yes --> R{"actual &gt; 0?"}
    R -- no --> DN["<b>down</b>"]
    R -- yes --> T{"targets &gt; 0?"}
    T -- yes --> OK["<b>ok</b>"]
    T -- no --> BL["<b>blind</b><br/>running, unmonitored"]

    I -- no --> Z{"actual &gt; 0?"}
    Z -- yes --> ZO["<b>zombie</b><br/>awake, undeclared"]
    Z -- no --> ST{"targets &gt; 0?"}
    ST -- yes --> SL["<b>stale</b>"]
    ST -- no --> SP["<b>sleeping</b><br/>parked on purpose"]

    style BL fill:#ffdddd,stroke:#cc0000
    style OR fill:#ffdddd,stroke:#cc0000
    style SP fill:#ddffdd,stroke:#00aa00
    style UM fill:#ddffdd,stroke:#00aa00
    style OK fill:#ddffdd,stroke:#00aa00
```

**`actual` is never compared to `intended`.** A rolling update sits at 3/2 for a minute; that is `ok`,
not `down`. Ordering those branches the other way pages on every deploy, and a guard that pages on
every deploy gets muted — the same argument this repo keeps making about permanently-lit alerts.

**`sleeping` is why the intended plane exists.** Without it, `0 replicas` is ambiguous input rather
than an answer: deliberately parked and crashed-at-3am are byte-identical.

**The invariant:** every live ServiceMonitor lands in exactly one verdict, and an unrecognised verdict
fails closed. There is no path where the guard checks nothing and reports success.
