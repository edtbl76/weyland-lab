# U9 (prereq) — CoreDNS LAN Resolver — Deploy & Validate

Stands up a SEPARATE CoreDNS on mother as the LAN resolver for `weyland.lab`
(wildcard `*.weyland.lab → 192.168.1.243`), forwarding everything else to
`1.1.1.1` / `9.9.9.9`. Manifest: `k8s/coredns-lan.yaml`. Does NOT touch k3s kube-dns.

Commands run from `mother` unless noted.

---

## ⚠️ Pre-check — is port 53 already taken on mother?

Ubuntu often runs `systemd-resolved` on `127.0.0.53:53`. If it also binds the LAN
IP, the ServiceLB can't claim `:53`. Check first:

```bash
sudo ss -lunp | grep ':53'
sudo ss -ltnp | grep ':53'
```

- Only `127.0.0.53:53` (systemd-resolved) → **fine**, that's loopback-only.
- Something on `0.0.0.0:53` or `192.168.1.243:53` → that must be freed first. If it's
  resolved's stub listener, disable it: set `DNSStubListener=no` in
  `/etc/systemd/resolved.conf`, then `sudo systemctl restart systemd-resolved`.

Report what's on :53 before applying — don't fight an existing binder.

---

## 1. Sync + apply

```bash
scp nodes/mother/lab/weyland-platform/k8s/coredns-lan.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/coredns-lan.yaml

kubectl apply -f ~/lab/weyland-platform/k8s/coredns-lan.yaml
```

Expected: configmap, deployment, service all created.

## 2. Pod up + LoadBalancer got mother's IP

```bash
kubectl get pods -n weyland -l app=weyland-lan-dns
kubectl get svc weyland-lan-dns -n weyland
```

Expected: pod `Running` 1/1; service `EXTERNAL-IP` shows `192.168.1.243` (k3s ServiceLB).

## 3. Resolve a lab name (the wildcard) — from mother

```bash
dig @192.168.1.243 n8n.weyland.lab +short
dig @192.168.1.243 anything.weyland.lab +short
```

Expected: both return `192.168.1.243` (wildcard working — any subdomain resolves).

## 4. Resolve a public name (the forwarder)

```bash
dig @192.168.1.243 cloudflare.com +short
```

Expected: real public IP(s) — proves `forward . 1.1.1.1 9.9.9.9` works.

## 5. Test from your workstation (not mother)

```bash
dig @192.168.1.243 headlamp.weyland.lab +short
```

Expected: `192.168.1.243`. Confirms a LAN client can use mother as a resolver.

---

## 6. Activation — how clients resolve weyland.lab

Two paths, chosen per the **cellular model** (platform clients vs outliers):

### 6a. LAN / platform-side devices → point DNS at CoreDNS (mother)

For devices that can use mother as their resolver:

- **Whole LAN:** set the router's DHCP "DNS server" to `192.168.1.243`; clients pick it up
  on next lease.
- **Per machine:** set that machine's DNS to `192.168.1.243` (NetworkManager:
  `sudo nmcli connection modify "<conn>" ipv4.dns 192.168.1.243 ipv4.ignore-auto-dns yes && sudo nmcli connection up "<conn>"`).

Gets the full wildcard (`*.weyland.lab`). Trade-off: mother becomes that client's resolver,
so its uptime matters for that client's DNS. Use ONE resolver (don't add a public
secondary — an empty/NXDOMAIN for a lab name counts as "success" and won't retry mother).
Verify with a bare lookup: `dig n8n.weyland.lab +short` → `192.168.1.243`.

### 6b. Outlier machines (e.g. rogueone) → static /etc/hosts

An outlier must NOT depend on the platform's DNS service. Use a local static map instead —
`/etc/hosts` is checked before any DNS server, so rogueone's own resolver is untouched and
`weyland.lab` names resolve with zero runtime dependency on mother's DNS. No wildcard, so
list each UI hostname (append more as UIs are added):

```bash
echo "192.168.1.243  n8n.weyland.lab dagster.weyland.lab headlamp.weyland.lab apisix.weyland.lab" | sudo tee -a /etc/hosts
```

Verify with `getent` / `ping` — **NOT `dig`** (dig queries DNS only and ignores /etc/hosts):

```bash
getent hosts n8n.weyland.lab     # expect: 192.168.1.243  n8n.weyland.lab
```

---

## Status (2026-06-08)

- CoreDNS deployed on mother; ServiceLB EXTERNAL-IP `192.168.1.243`; pod Running.
- Validated on mother: `*.weyland.lab` → `192.168.1.243` (wildcard), `cloudflare.com` → real IPs (forward).
- rogueone (outlier) activated via `/etc/hosts` (6b) — confirmed working.
- LAN-wide router DHCP activation (6a): optional, deferred to when desired.
