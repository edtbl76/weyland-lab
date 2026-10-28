# B69 Wave 4 — weekly code-scan suite. ONE image bundling the free static/security/quality scanners so a single
# CronJob clones the repo once and runs them all → per-tool severity counts POSTed to the Port `code-quality`
# webhook (same payload as the semgrep/trivy Jobs) + raw JSON archived to MinIO s3://scan-reports/<ts>/ (90d ILM;
# OUT itself is an emptyDir, so the upload is what makes findings outlive the pod). Built + pushed to
# registry.weyland.lab via scripts/build-push-images.sh. Pin bumps: check each tool's latest release if a URL 404s.
# Go tools are BUILT FROM SOURCE with one current toolchain (2026-10-17, B220). Every Go binary carries the Go runtime
# and modules it was built with, and upstream release builds lag: the old set carried Go-stdlib and golang.org/x/text
# advisories (gitleaks' newest release is still go1.24; kubescape/osv-scanner/shfmt releases go1.26.8–1.27.1, short
# of the go1.27.2 fixes). Building here puts every tool on go1.27.2, and gitleaks on x/text 0.41.0 (its go.mod pins
# 0.22). osv-scanner v2 needs go ≥ 1.27; kubescape's go.mod has replace directives, so it builds from a clone.
# Contract checks for the major bumps (kubescape v3 → v4, osv-scanner v1 → v2), run on this repo 2026-10-17:
#   kubescape: identical resourcesSeverityCounters + ResourceCounters (653 H / 799 M / 392 L, 163 failing resources).
#   osv-scanner: same flags and JSON shape; the osv-scanner.toml accept list still applies (0 of 7 accepted ids
#   reported). v2 reports FEWER: v1 scored an UNPINNED requirement as version 0.0.0 and listed every advisory ever
#   filed for it (91 phantoms on golden-paths/python/django alone).
# 2026-10-22: 1.27.2 -> 1.27.3 (GO-2026-6809 / CVE-2026-111943, crypto/x509; every Go tool below is rebuilt with it).
FROM golang:1.27.3 AS gotools
ENV GOTOOLCHAIN=local GOBIN=/out
# go install where the release's go.mod is clean; a clone + `go get` where a pinned module carried an advisory
# (2026-10-18, B220 — the re-scan found them): gitleaks x/crypto 0.35 → 0.55 + x/text 0.22 → 0.41; gosec x/net → 0.60,
# grpc → 1.83.2; govulncheck x/mod 0.22 → 0.40; kubescape x/image → 0.45, x/net → 0.60 (and kubescape's go.mod has
# replace directives, so it never builds via go install).
RUN set -eux; \
    go install github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.7.0; \
    go install mvdan.cc/sh/v3/cmd/shfmt@v3.14.1; \
    go install honnef.co/go/tools/cmd/staticcheck@2026.2.2; \
    git clone -q --depth 1 -b v8.30.1 https://github.com/gitleaks/gitleaks /src/gitleaks; \
    git clone -q --depth 1 -b v2.29.0 https://github.com/securego/gosec /src/gosec; \
    git clone -q --depth 1 -b v1.1.4 https://go.googlesource.com/vuln /src/vuln; \
    git clone -q --depth 1 -b v4.0.16 https://github.com/kubescape/kubescape /src/kubescape
WORKDIR /src/gitleaks
RUN go get golang.org/x/text@v0.41.0 golang.org/x/crypto@v0.55.0 && go build -o /out/gitleaks .
WORKDIR /src/gosec
RUN go get golang.org/x/net@v0.60.0 google.golang.org/grpc@v1.83.2 && go build -o /out/gosec ./cmd/gosec
WORKDIR /src/vuln
RUN go get golang.org/x/mod@v0.40.0 && go build -o /out/govulncheck ./cmd/govulncheck
WORKDIR /src/kubescape
# 2026-10-28: + go-jose/v4 4.1.6 (CVE-2026-116587, JWK RSA-key parsing DoS; kubescape v4.0.17 still pins 4.1.4) and
# x/net 0.60.0 -> 0.62.0 (GO-2026-6860/6866).
RUN go get golang.org/x/image@v0.45.0 golang.org/x/net@v0.62.0 github.com/go-jose/go-jose/v4@v4.1.6 && go build -o /out/kubescape .

FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive
# boto3 (for the MinIO archive step in scan.py) is deliberately UNPINNED: checkov pins boto3 to an EXACT version
# (3.2.257 → boto3==1.34.25), so any pin of our own that differs makes the install unsatisfiable and the image
# build dies with ResolutionImpossible. Listing it unpinned declares the dependency without fighting checkov's pin.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git xz-utils default-jre-headless \
    && rm -rf /var/lib/apt/lists/*
# 2026-10-16: the Python tools are pinned in requirements.txt (the full frozen set of the image this replaced), so a
# rebuild cannot drift and the scanners can read their own dependencies.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Static binaries (amd64). Each is a single file → drop into /usr/local/bin. trivy's release is already built with
# go1.27.3 (0.76.1, 2026-10-22, for GO-2026-6809; was 0.76.0 on go1.27.2; 0.72 → 0.76 on 2026-10-17); the other Go tools come from the gotools stage above.
RUN set -eux; \
    curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz" | tar -xz -C /usr/local/bin trivy; \
    curl -fsSL -o /usr/local/bin/hadolint "https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64"; \
    curl -fsSL "https://github.com/koalaman/shellcheck/releases/download/v0.10.0/shellcheck-v0.10.0.linux.x86_64.tar.xz" | tar -xJ --strip-components=1 -C /usr/local/bin shellcheck-v0.10.0/shellcheck; \
    curl -fsSL -o /opt/code-maat.jar "https://github.com/adamtornhill/code-maat/releases/download/v1.0.4/code-maat-1.0.4-standalone.jar"; \
    chmod +x /usr/local/bin/hadolint

# Go toolchain + Go security tools (gosec/govulncheck/staticcheck) for polyglot repos (Stud.io etc.). `go vet`
# ships with the toolchain. The analysers need the toolchain at scan time, so it is copied from the gotools stage
# (go1.27.2) along with every Go tool built there. A go.mod-less repo (weyland's own tree) no-ops these cleanly.
# Runtime GOCACHE/GOPATH default under the scan user's writable $HOME.
ENV PATH=/usr/local/go/bin:/usr/local/bin:$PATH GOTOOLCHAIN=local
COPY --from=gotools /usr/local/go /usr/local/go
COPY --from=gotools /out/ /usr/local/bin/

COPY scan.py /usr/local/bin/scan.py
COPY kubescape-exceptions.json /usr/local/share/scan-suite/kubescape-exceptions.json
RUN useradd -u 10001 -m scan
USER scan
ENTRYPOINT ["python3", "/usr/local/bin/scan.py"]
