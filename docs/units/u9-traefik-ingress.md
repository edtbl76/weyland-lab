# U9 (ingress) — Traefik + TLS for platform UIs

Puts platform UIs behind Traefik (k3s default ingress controller) over HTTPS using the
shared wildcard cert. Plain k8s `Ingress` (no Traefik CRDs) for portability. Per-UI:
the TLS Secret must exist in that UI's namespace.

Starting with **n8n** (carries RL #6 secure-cookie + RL #7 drop-HTTP). Commands run on
mother unless noted.

---

## n8n

### 1. Put the wildcard TLS Secret in the n8n namespace

Traefik reads the Secret from the Ingress's own namespace, and n8n lives in `n8n`:

```bash
cd ~/certs
kubectl create secret tls weyland-wildcard-tls \
  --cert=weyland-wildcard.pem --key=weyland-wildcard-key.pem \
  -n n8n
kubectl get secret weyland-wildcard-tls -n n8n
```

### 2. Sync + apply the updated n8n manifest

```bash
# from repo box:
scp nodes/mother/lab/weyland-platform/k8s/n8n/n8n.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/n8n/n8n.yaml

# on mother:
kubectl apply -f ~/lab/weyland-platform/k8s/n8n/n8n.yaml
kubectl rollout restart deployment/n8n -n n8n
kubectl rollout status deployment/n8n -n n8n
```

### 3. Verify the Ingress + pod

```bash
kubectl get ingress -n n8n
kubectl get pods -n n8n -l app=n8n
```

Expected: Ingress `n8n` with host `n8n.weyland.lab`; pod Running.

### 4. Hit it over HTTPS — from rogueone (cert trusted there)

```bash
curl -sI https://n8n.weyland.lab        # expect HTTP/2 200, valid TLS (no -k needed)
curl -svo /dev/null https://n8n.weyland.lab 2>&1 | grep -Ei 'subject:|issuer:|SSL certificate verify'
```

Expected: `200`, and the cert `issuer` is the mkcert local CA, verify `ok`. Then open
`https://n8n.weyland.lab` in the browser → green padlock, n8n loads, login works, no
"insecure cookie" complaints.

> If you get a 404 from Traefik on 443 (not from n8n), the TLS Ingress may not be bound to
> the websecure entrypoint — add annotation
> `traefik.ingress.kubernetes.io/router.entrypoints: websecure` to the Ingress and re-apply.
> (Traefik-specific; only if needed.)

### 5. Drop the LAN HTTP NodePort (RL #7) — AFTER HTTPS confirmed

Once HTTPS works, change the n8n `Service` from `type: NodePort` to `type: ClusterIP`
(remove the `nodePort:` line) so raw `http://mother:30082` is no longer exposed; access is
HTTPS-only via Traefik. Re-apply and confirm the NodePort is gone:

```bash
kubectl get svc n8n -n n8n        # expect ClusterIP, no 30082
```

---

## Other UIs (repeat the pattern)

For Dagster, Headlamp, APISIX dashboard: create `weyland-wildcard-tls` in that UI's
namespace, add a plain `Ingress` (host `<ui>.weyland.lab`, backend = the UI service),
add the host to rogueone `/etc/hosts`, validate over HTTPS, then drop its NodePort.
