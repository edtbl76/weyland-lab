# LAN DNS — weyland-lan-dns (`*.weyland.lab`)

`weyland-lan-dns` is a standalone **CoreDNS** (weyland ns, `k8s/coredns-lan.yaml`) that is authoritative for the
private lab domain and forwards everything else to public resolvers. It is **separate from k3s kube-dns**.

## Architecture (post-2026-07-18)

Three DNS consumers, each independent so one failure can't cascade:

| Who | Resolves `*.weyland.lab` via | Resolves external via |
|---|---|---|
| **mother (the node)** | systemd-resolved drop-in → `192.168.1.243:53` (this CoreDNS) — `nodes/mother/host/systemd/resolved.conf.d/weyland-lab.conf` | the per-link router resolver (`192.168.1.1`) — **independent of any pod** |
| **LAN clients** | `mother:53` (the CoreDNS hostPort, LAN IP only) | forwarded by this CoreDNS (`. → 1.1.1.1 9.9.9.9`) |
| **in-cluster pods** | cluster CoreDNS `coredns-custom` forward → `192.168.1.243` | cluster CoreDNS |

Exposure: the **Deployment** binds `hostPort: 53` **pinned to `hostIP: 192.168.1.243`** (the LAN IP). The Service
is **ClusterIP** (for in-cluster clients + `:9153` metrics). It is deliberately **NOT `type: LoadBalancer`** — see
the incident.

## ⚠️ Incident 2026-07-18 — hostPort:53 captured the node's own resolver

**Symptom:** total host DNS failure on mother. `getent hosts <anything>` empty; `nslookup … 127.0.0.53` timed out
even though systemd-resolved was up and bound; new pods stuck `ContainerCreating` (couldn't pull the `pause`
sandbox image → argocd-repo-server down → **Argo couldn't sync anything**); a whole pod wave (keycloak, mlflow,
neo4j, litellm, open-webui, ray) stalled.

**Root cause:** weyland-lan-dns was `type: LoadBalancer` → k3s **ServiceLB (klipper)** ran an `svclb` pod with
**hostPort 53 on `0.0.0.0`**. The CNI turns a hostPort into a DNAT in the `OUTPUT` chain matching
**`ADDRTYPE match dst-type LOCAL`** — which includes **`127.0.0.53`**, systemd-resolved's stub. So the node's own
resolver was silently routed *through* this pod. When the pod crash-looped (and a disk-pressure image GC removed
the `pause` image), the **orphaned DNAT black-holed every host DNS query** to a dead pod IP → deadlock (the DNS pod
couldn't restart because it needed `pause`, which needed DNS).

Confirm the capture if it recurs:
```
sudo iptables-save | grep -n 53          # look for CNI-HOSTPORT-DNAT / CNI-DN-* DNATing :53 to a pod IP
sudo iptables -t nat -L OUTPUT -n -v     # rule: CNI-HOSTPORT-DNAT for ADDRTYPE match dst-type LOCAL
```

**Emergency recovery (one-time, not git-managed):**
```
kubectl -n weyland scale deploy weyland-lan-dns --replicas=0     # stop it recreating the hostPort
sudo iptables -t nat -F CNI-DN-<hash>                            # flush the orphaned :53 DNAT chain
getent hosts registry-1.docker.io                               # host DNS restored → pods can pull `pause` again
```

**Permanent fix (in git):** `hostIP: 192.168.1.243` on the hostPort (scopes the DNAT to `-d 192.168.1.243`, never
`127.0.0.53`) + Service `ClusterIP` (no svclb) + the systemd-resolved drop-in so the node resolves weyland.lab
*without* its external path depending on this pod.

## Deploy

1. **Node drop-in** (external DNS independence) — from the repo root:
   ```
   rsync -av nodes/mother/host/systemd/resolved.conf.d/weyland-lab.conf emangini@mother:/tmp/weyland-lab.conf
   ```
   then on mother: `sudo install -m 0644 /tmp/weyland-lab.conf /etc/systemd/resolved.conf.d/weyland-lab.conf && sudo systemctl restart systemd-resolved`
2. **Manifest**: push `k8s/coredns-lan.yaml`, sync the `coredns-lan` Argo app (manual-sync), scale the deploy back to 1.

## Verify (all must pass)
```
ss -tulpn 'sport = :53'                          # systemd-resolved on 127.0.0.53 AND CoreDNS on 192.168.1.243 only
getent hosts google.com                          # external still resolves (via router, unaffected)
getent hosts registry.weyland.lab                # 192.168.1.243 (via drop-in → CoreDNS)
nslookup keycloak.weyland.lab 192.168.1.243      # LAN serving
sudo iptables -t nat -S CNI-HOSTPORT-DNAT        # no :53 DNAT except scoped to -d 192.168.1.243
kubectl run d --rm -i --restart=Never --image=busybox -- nslookup keycloak.weyland.lab   # in-cluster path
```
