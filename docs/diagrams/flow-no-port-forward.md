# Flow — LAN access: NodePorts only, and the guard that keeps it that way

How anything off the cluster reaches an in-cluster service, and how `scripts/check-no-port-forward.sh` decides that a
line in the repo is a port-forward instruction. Runbook: [lan-access.md](../runbooks/lan-access.md). Demo:
[no-port-forward.md](../demos/no-port-forward.md).

## Reaching a service from rogueone

```mermaid
sequenceDiagram
    participant R as rogueone (script / DataGrip / trainer)
    participant N as mother 192.168.1.243:<nodePort>
    participant P as NetworkPolicy (target's front door)
    participant S as target pod
    R->>N: connect to the -lan NodePort
    Note over N: externalTrafficPolicy Local keeps the client IP 192.168.1.230
    N->>P: packet from 192.168.1.230
    alt target has its own auth (GMS token, a password, Kuma login)
        P-->>S: admitted (no policy, or the caller is listed)
        S-->>R: answers, and its auth decides
    else target has NO auth (Trino, Valkey, OpenSearch, MLflow)
        P-->>S: admitted only if the source matches ipBlock 192.168.1.230/32
        S-->>R: answers rogueone, nobody else on the LAN
    end
    Note over R,S: STRICT-mTLS or noauth-by-design targets (weyland-postgres, trino-noauth) have no NodePort, so the work runs in-cluster
```

## Is this line a port-forward instruction?

```mermaid
flowchart TD
    A[a line in a scanned file] --> B{contains port-forward?}
    B -->|no| C{Python client call?<br/>kubernetes.stream portforward}
    C -->|yes| FAIL[hit: file and line, exit 1]
    C -->|no| D{IntelliJ menu step?<br/>an arrow then the Forward Ports action}
    D -->|no| OK[not an instruction]
    B -->|yes| E{a token after it, before a backtick or a closing paren,<br/>is a resource svc/x pod/x deploy/x<br/>or a port mapping 9090:9090?}
    E -->|yes| FAIL
    E -->|no| F{imperative or route in prose?<br/>the word then the or a<br/>or a route word in front of it}
    F -->|no| OK
    F -->|yes| G{negated just before?<br/>not, never, no, without}
    G -->|yes| OK
    G -->|no| FAIL
    D -->|yes| G
```

The scan itself fails closed: zero files scanned is exit 2 (a wrong root is "could not run", never "clean").
`docs/backlog.md`, notebooks (`.ipynb` outputs are recorded data), generated trees and the guard's own files are not
scanned.

## Watching the NodePorts (B219)

```mermaid
sequenceDiagram
    participant T as rogueone user timer (every 15 min)
    participant W as lan_nodeport_watch.py
    participant K as kubectl (live cluster)
    participant N as mother NodePorts
    participant U as Uptime Kuma push monitor lan-nodeports
    T->>W: run
    W->>K: get svc, deploy+sts, nodes
    K-->>W: NodePort inventory, replicas, node InternalIP
    loop every NodePort
        alt workload parked (replicas 0)
            W-->>W: list as parked, no probe
        else no probe defined for it
            W-->>W: UNPROBED, exit 1
        else
            W->>N: protocol probe (HTTP < 500, Redis PONG, pg SSL byte, MySQL greeting)
            N-->>W: answer or nothing
        end
    end
    W->>U: push status up (exit 0) or down with the findings (exit 1/2)
    Note over U: a missed heartbeat (watcher not running) alerts too, after 1200 s
```

rogueone is the vantage point because the rogueone-only ports refuse every other source; an in-cluster probe would only
ever see "refused". The first run found the MySQL NodePort had never worked (a server-first protocol behind a PERMISSIVE
sidecar); MySQL was unmeshed and the watcher now reports `30 up, 3 parked, 33 NodePort(s) — exit 0`.
