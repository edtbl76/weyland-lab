# APISIX gateway — runbook

An Apache APISIX API gateway in front of the tool-server, at `http://192.168.1.243:30090`. Dashboard:
<https://apisix.weyland.lab>. Written by B239 (2026-11-08), which found no runbook for operating it.

> **Usage, measured 2026-11-08:** zero requests on every route over the previous 7 days
> (`increase(apisix_http_status[7d])`). Every caller in the lab reaches the tool-server and the stores directly. So
> it is deployed and working, but nothing depends on it. Whether to keep it is an owner decision (B239 finding 18).

## How it is built

| Part | Object (ns `weyland`) | Role |
|---|---|---|
| Gateway | Deployment `weyland-apisix` (`apache/apisix:3.9.0-debian`), `k8s/apisix.yaml` | port 9080, NodePort **30090**; Prometheus metrics on 9091 |
| Config store | StatefulSet `weyland-apisix-etcd` (PVC `etcd-data`), `k8s/apisix-etcd.yaml` | routes and upstreams live here, not in a manifest |
| Dashboard | Deployment `weyland-apisix-dashboard`, `k8s/apisix-dashboard.yaml` | the web UI |

- **Routes** (defined in `scripts/lib/apisix_routes.py`, checked and restored by `scripts/apisix-routes.py`): one upstream, `weyland-tool-server`, and five
  prefix routes onto it: `/context/*`, `/pipeline/*`, `/qdrant/*`, `/weaviate/*`, `/neo4j/*`.
- **The admin API** listens on `127.0.0.1:9180` inside the gateway pod only. The admin key is the `APISIX_ADMIN_KEY`
  env from Secret `apisix-secret` (sealed in git).
- The tool-server's own protections still apply behind the gateway: its act routes are denied to every caller but
  the MCP gateway (Istio policy `toolserver-act-gateway-only`, [tool-server.md](tool-server.md)).

## Is it healthy?

```bash
kubectl -n weyland get deploy weyland-apisix weyland-apisix-dashboard; kubectl -n weyland get sts weyland-apisix-etcd
```

A request through the gateway to a read route:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.1.243:30090/qdrant/health
```

Expected: `200` (the tool-server's `/qdrant/health`). An unrouted path returns `404`; `GET /context/search` returns
`405` (it is a POST route).

The routes as stored (read-only, from etcd; the etcd image has no shell, so call `etcdctl` directly):

```bash
kubectl exec -n weyland sts/weyland-apisix-etcd -- etcdctl get /apisix/routes --prefix --keys-only
```

Expected: `/apisix/routes/1` to `/apisix/routes/5`. One route's definition:
`kubectl exec -n weyland sts/weyland-apisix-etcd -- etcdctl get /apisix/routes/3 --print-value-only`.

Traffic per route:

```bash
curl -s 'http://192.168.1.243:30909/api/v1/query' --data-urlencode 'query=sum by (route) (increase(apisix_http_status[7d]))'
```

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| every route `404` | the routes are gone from etcd (a lost or reset `etcd-data` PVC) | `apisix-routes.py check`, then `restore` (below) |
| a route `502`/`503` | the tool-server is down | [tool-server.md](tool-server.md) |
| gateway pod not ready | etcd unreachable | `kubectl -n weyland logs sts/weyland-apisix-etcd --tail=100` |

## Check and restore the routes

The routes are defined in git (`scripts/lib/apisix_routes.py`: the upstream and the five routes, as the records
APISIX keeps in etcd), and `scripts/apisix-routes.py` compares them with etcd or writes back what drifted. It talks to
etcd with `etcdctl` in the etcd pod, because the gateway's admin API listens only on its pod's localhost.

[rogueone]
```bash
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/apisix-routes.py check
```

Expected: `apisix-routes: in sync (6 records: 1 upstream, 5 routes)`, exit 0 (checked live 2026-11-08). Exit 1 lists
each missing or changed record (timestamps are ignored); exit 2 means etcd could not be reached.

To put back what drifted (only those records are written, the upstream before the routes, then it checks again):

[rogueone]
```bash
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/apisix-routes.py restore
```

`restore` writes to etcd, so run it only to repair. Its logic is tested against a fake etcd
(`scripts/tests/test_apisix_routes.py`), and the live write was proven on 2026-11-08 with the owner's go:
- route 5 was backed up (`etcdctl get /apisix/routes/5 --print-value-only`), then deleted, and `/neo4j/health`
  through the gateway went to `404`;
- `check` reported `/apisix/routes/5: missing` (exit 1), and `restore` wrote back only that record and re-checked
  in sync;
- the route answered `200` on the first try, the other routes were unaffected, and the record matched the backup
  apart from its timestamps.

If a restore ever writes something wrong, put the saved value back with `etcdctl put <key> '<saved json>'`.

This replaces the old seed (`deploy-apisix.sh` running `routes-init.sh` in the gateway pod), which could not work:
the gateway image has no `curl`, and the script expected `APISIX_ADMIN_KEY` in `scripts/.env`, which no longer holds
it (B239 finding 18).

## Logs and restart

```bash
kubectl -n weyland logs deploy/weyland-apisix -c apisix --tail=200
```

```bash
kubectl -n weyland rollout restart deploy/weyland-apisix
```

Routes survive a gateway restart (they are in etcd). Restarting etcd keeps them too, as long as its PVC is kept.

## Restore

There is no `dr.md` row. The routes are reproducible from git with `apisix-routes.py restore`; recording that as the
reproducible reason belongs to B240 (DR catalog gaps).
