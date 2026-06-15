# U9 (cert) — mkcert wildcard cert for *.weyland.lab

One local-CA-signed wildcard cert, trusted on rogueone (the browse machine), loaded into
Traefik as a k8s TLS Secret. The mkcert CA is the **shared local CA** for the whole lab —
later, APISIX (outlier front door) signs from the same CA → trust one root, green padlock
everywhere.

> ⚠️ **Never commit the private key.** Generate outside the repo. `.gitignore` covers
> `*.key`, `*-key.pem`, `certs/` as a backstop.

---

## 1. Install mkcert + trust the local CA — on rogueone

```bash
sudo apt update && sudo apt install -y mkcert libnss3-tools   # libnss3-tools = Firefox/Chrome (NSS) trust
# If mkcert isn't in apt: grab the binary from github.com/FiloSottile/mkcert/releases,
#   chmod +x, sudo mv mkcert /usr/local/bin/mkcert
mkcert -install
```

`mkcert -install` creates the local CA and trusts it in rogueone's OS + browsers. Note the
CA location (needed to trust the CA on any other browse machine later):

```bash
mkcert -CAROOT
```

## 2. Generate the wildcard cert — on rogueone, in a non-repo dir

```bash
mkdir -p ~/weyland-certs && cd ~/weyland-certs
mkcert -cert-file weyland-wildcard.pem -key-file weyland-wildcard-key.pem "*.weyland.lab" weyland.lab
```

Confirm the SANs:

```bash
openssl x509 -in weyland-wildcard.pem -noout -subject -ext subjectAltName
```

Expected SANs: `DNS:*.weyland.lab, DNS:weyland.lab`.

## 3. Ship to mother + create the TLS Secret

On mother (make the landing dir):

```bash
mkdir -p ~/certs
```

From rogueone (ship the pair):

```bash
scp ~/weyland-certs/weyland-wildcard.pem ~/weyland-certs/weyland-wildcard-key.pem \
  emangini@mother:~/certs/
```

On mother (create the Secret — `cd` first so the paths resolve cleanly):

```bash
cd ~/certs
kubectl create secret tls weyland-wildcard-tls \
  --cert=weyland-wildcard.pem --key=weyland-wildcard-key.pem \
  -n weyland
kubectl get secret weyland-wildcard-tls -n weyland
```

Expected: `secret/weyland-wildcard-tls created`, then listed as type `kubernetes.io/tls`.

> If a UI's `Ingress` ends up in a different namespace, re-create this Secret there too —
> Traefik reads the TLS Secret from the Ingress's own namespace.

---

## Notes

- **Trust-once:** rogueone trusts the CA now. Any other browse machine: copy
  `$(mkcert -CAROOT)/rootCA.pem` over and import it into that machine's trust store.
- The cert/key files stay out of git (generated in `~/weyland-certs` on rogueone and
  `~/certs` on mother — neither is the repo). The Secret in-cluster is the real source.
