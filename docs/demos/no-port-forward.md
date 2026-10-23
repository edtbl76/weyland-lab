# Demo — LAN access by NodePort only, and the no-port-forward guard

The lab reaches in-cluster services from rogueone by LAN NodePort only. Until 2026-10-17 that rule lived in one agent
memory note and one runbook line, so 44 port-forward instructions survived across the docs and four pieces of code
(`store-park.sh`, both trainer entrypoints), and one was copied forward while a runbook was being edited. This demo
shows the seven NodePorts that replaced them, proves the no-auth ones admit rogueone and refuse everyone else, and
shows `scripts/check-no-port-forward.sh` passing, failing (exit 1) and refusing to grade nothing (exit 2).
Runbook: [lan-access.md](../runbooks/lan-access.md). Flow: [flow-no-port-forward.md](../diagrams/flow-no-port-forward.md).

There is no UI deliverable — the CLI walkthrough is the whole demo (repo tooling + Services).

## CLI walkthrough (RUN 2026-10-17 against live infra, commit `a2020ef8`)

**1. Every new NodePort answers from rogueone — at the protocol level, not just TCP:**

[rogueone]
```
L=192.168.1.243; curl -s "http://$L:30909/api/v1/query?query=up" | jq -r .status; curl -s --cacert "$(mkcert -CAROOT)/rootCA.pem" "https://$L:30843/v1/info" | jq -r .nodeVersion.version; curl -s "http://$L:30920/_cluster/health" | jq -r .status; (printf 'PING\r\n'; sleep 1) | nc -w3 $L 30379 | head -1
```
(B233, 2026-10-23: Trino's NodePort is `:30843`, HTTPS + a login; the old plain-HTTP `:30808` was removed in stage 3 —
[runbooks/trino.md § Authentication](../runbooks/trino.md#authentication-b233-2026-10-23).)
Output (run): `success` (136 `up` series) · `468` (Trino) · `yellow` (single-node OpenSearch) · `+PONG` (Valkey). The
same run: Uptime Kuma `:30301` → `HTTP 302` (its own login), GMS `:30818/health` → `HTTP 200`, musicbrainz-postgres
`:30544` answered the Postgres SSL probe.

**2. The no-auth NodePorts refuse anyone who is not rogueone.** From a pod (source IP is a pod IP, not
`192.168.1.230`), with the unpinned Prometheus port as the control:

[rogueone]
```
kubectl -n weyland exec deploy/litellm -- python -c "
import socket
for n, p in (('prometheus (control)', 30909), ('trino', 30843), ('valkey', 30379), ('opensearch', 30920)):
    s = socket.socket(); s.settimeout(4)
    try: s.connect(('192.168.1.243', p)); print(n, 'CONNECTED')
    except Exception as e: print(n, 'REFUSED', type(e).__name__)
    finally: s.close()"
```
Output (run):
```
prometheus (control) CONNECTED
trino REFUSED ConnectionRefusedError
valkey REFUSED ConnectionRefusedError
opensearch REFUSED ConnectionRefusedError
```
The control connecting is what makes the three refusals mean "the policy said no", not "the path is broken".

**3. Code that used to port-forward now uses a NodePort.** `store-park.sh` reads each parked store's DataHub schedule
through `datahub-gms-lan`:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh status
```
Output (run): four rows, e.g. `cassandra  git=0  live(desired/ready)=0/  datahub=paused  (config 286899f6bbda)`, exit 0.
The trainer entrypoints' three NodePorts (`:30500`, `:30990`, `:30800`) were reached from a bridge-network container on
rogueone the same day (`nc -z` → all three reachable).

**4. The guard passes on the repo:**

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-no-port-forward.sh
```
Output (run): `no-port-forward: OK — no port-forward commands in 7281 file(s).` exit 0.

**5. The negative case — the guard fails on a port-forward, and names the line.** A scratch tree outside the repo with
one runbook holding a forward command (built with `%s` so this demo page never contains the literal):

[rogueone]
```
D=$(mktemp -d); mkdir -p "$D/docs/runbooks"; printf 'Reach Prometheus:\nkubectl -n monitoring port-%s svc/prometheus 9090:9090\nThe lab never port-forwards.\n' forward > "$D/docs/runbooks/example.md"; SCAN_ROOT="$D" bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-no-port-forward.sh; echo "exit $?"
```
Output (run): one hit, `docs/runbooks/example.md:2: kubectl -n monitoring …`, then `FAIL — 1 port-forward command(s).
The lab is NodePorts only: …` and `exit 1`. Line 3 ("The lab never port-forwards.") is prose that rejects the practice
and is not reported.

**6. It refuses to grade nothing (exit 2), and it would have caught the original problem:**

[rogueone]
```
SCAN_ROOT="$D/nothing-here" bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-no-port-forward.sh; echo "exit $?"
```
Output (run): `no-port-forward: scanned nothing under … — refusing to report clean (exit 2)`, `exit 2`. Run against
the tree before the purge (`git archive 1122c5bb`): `FAIL — 44 port-forward command(s).`, exit 1.

**7. The tests:** `scripts/tests/no-port-forward.bats` (11 cases, CI `shell-tests`) and the rogueone pins in
`scripts/tests/write-surface-netpol.bats` (Valkey, Trino, OpenSearch each pinned with `ip=192.168.1.230/32`).

## The NodePort watcher (B219, run 2026-10-17/18)

**8. Every NodePort answers, at the protocol level, from rogueone:**

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/lan_nodeport_watch.py --no-push
```
Output (first run, 2026-10-17): `DOWN data-mesh/mysql-lan:30306 [mysql] — no greeting (server-first protocol swallowed —
a PERMISSIVE sidecar?)` · `29 up, 3 parked, 33 NodePort(s) — exit 1` — a real break nobody had noticed. After MySQL was
unmeshed: `30 up, 3 parked, 33 NodePort(s) — exit 0`, and the timer runs show the same in
`journalctl --user -u lan-nodeport-watch`.

**9. The alert fires.** Point the probes at an unreachable address so every port is DOWN:

[rogueone]
```
LAN_NODEPORT_HOST=192.0.2.1 python3 /home/edwardmangini/IdeaProjects/weyland/scripts/lan_nodeport_watch.py
```
Output (run 2026-10-18): `0 up, 3 parked, 33 NodePort(s) — exit 1`, pushed `down` to the Kuma monitor `lan-nodeports`
(Telegram alert); the next normal run pushed `up` (exit 0). UAT: in Uptime Kuma (`kuma.weyland.lab`), `lan-nodeports`
shows the red beat followed by green.

## Teardown

Steps 1–4, 6 and 8 are read-only; step 9 pushes one `down` heartbeat, cleared by the next timer run. Step 5 writes only to a `mktemp -d` scratch directory outside the repo — remove it with
`rm -r "$D"` (or leave it to the OS tmp cleaner). Nothing is created in the cluster.
