# ${{ values.name }} — runbook

Scaffolded via the weyland IDP golden path (B3). Fill in the specifics, then delete this line.

- **Image:** `${{ values.image }}`
- **Namespace:** `${{ values.namespace }}` · **Port:** `${{ values.port }}` · **URL:** `https://${{ values.name }}.weyland.lab`
- **Manifest:** `nodes/mother/lab/weyland-platform/k8s/${{ values.name }}/${{ values.name }}.yaml`
- **Mesh:** joined (`sidecar.istio.io/inject: "true"`) — drop the label in the manifest if not needed.

## Deploy
```
kubectl apply -f k8s/${{ values.name }}/${{ values.name }}.yaml && kubectl rollout status deploy/${{ values.name }} -n ${{ values.namespace }}
```

## Verify
```
kubectl get pods -n ${{ values.namespace }} -l app=${{ values.name }}
```
Then browse `https://${{ values.name }}.weyland.lab` (needs a `192.168.1.243 ${{ values.name }}.weyland.lab` line if resolving via `/etc/hosts`; CoreDNS wildcard covers in-LAN).

## TODO
- [ ] Resource limits tuned for the workload
- [ ] Secrets wired (if any) — create out-of-band, never commit
- [ ] Added to `docs/arch.md` component inventory + `docs/hosts.md` + `docs/api.md`
- [ ] If it talks to STRICT-mTLS Postgres, confirm the mesh label is present
