# B69 Wave 4 — weekly code-scan suite. ONE image bundling the free static/security/quality scanners so a single
# CronJob clones the repo once and runs them all → per-tool severity counts POSTed to the Port `code-quality`
# webhook (same payload as the semgrep/trivy Jobs) + raw JSON archived to MinIO s3://scan-reports/<ts>/ (90d ILM;
# OUT itself is an emptyDir, so the upload is what makes findings outlive the pod). Built + pushed to
# registry.weyland.lab via scripts/build-push-images.sh. Pin bumps: check each tool's latest release if a URL 404s.
FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive
# boto3 (for the MinIO archive step in scan.py) is deliberately UNPINNED: checkov pins boto3 to an EXACT version
# (3.2.257 → boto3==1.34.25), so any pin of our own that differs makes the install unsatisfiable and the image
# build dies with ResolutionImpossible. Listing it unpinned declares the dependency without fighting checkov's pin.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git xz-utils default-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir 'setuptools<81' checkov==3.2.257 bandit==1.7.10 semgrep==1.90.0 \
         ruff==0.9.10 pip-audit==2.7.3 detect-secrets==1.5.0 mypy==1.14.1 boto3

# Static binaries (amd64). Each is a single file → drop into /usr/local/bin.
RUN set -eux; \
    curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz" | tar -xz -C /usr/local/bin gitleaks; \
    curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_Linux-64bit.tar.gz" | tar -xz -C /usr/local/bin trivy; \
    curl -fsSL -o /usr/local/bin/hadolint "https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64"; \
    curl -fsSL -o /usr/local/bin/kubescape "https://github.com/kubescape/kubescape/releases/download/v3.0.8/kubescape-ubuntu-latest"; \
    curl -fsSL -o /usr/local/bin/osv-scanner "https://github.com/google/osv-scanner/releases/download/v1.9.1/osv-scanner_linux_amd64"; \
    curl -fsSL "https://github.com/koalaman/shellcheck/releases/download/v0.10.0/shellcheck-v0.10.0.linux.x86_64.tar.xz" | tar -xJ --strip-components=1 -C /usr/local/bin shellcheck-v0.10.0/shellcheck; \
    curl -fsSL -o /opt/code-maat.jar "https://github.com/adamtornhill/code-maat/releases/download/v1.0.4/code-maat-1.0.4-standalone.jar"; \
    curl -fsSL "https://github.com/mvdan/sh/releases/download/v3.10.0/shfmt_v3.10.0_linux_amd64" -o /usr/local/bin/shfmt; \
    chmod +x /usr/local/bin/hadolint /usr/local/bin/kubescape /usr/local/bin/osv-scanner /usr/local/bin/shfmt

# Go toolchain + Go security tools (gosec/govulncheck/staticcheck) for polyglot repos (Stud.io etc.). `go vet`
# ships with the toolchain. GOBIN → /usr/local/bin (world-readable, on PATH for uid 10001); a go.mod-less repo
# (weyland's own tree) no-ops these cleanly. Runtime GOCACHE/GOPATH default under the scan user's writable $HOME.
ENV PATH=/usr/local/go/bin:/usr/local/bin:$PATH
RUN set -eux; \
    curl -fsSL "https://go.dev/dl/go1.23.4.linux-amd64.tar.gz" | tar -xz -C /usr/local; \
    GOBIN=/usr/local/bin go install github.com/securego/gosec/v2/cmd/gosec@v2.21.4; \
    GOBIN=/usr/local/bin go install golang.org/x/vuln/cmd/govulncheck@v1.1.3; \
    GOBIN=/usr/local/bin go install honnef.co/go/tools/cmd/staticcheck@2024.1.1; \
    rm -rf /root/.cache/go-build /root/go/pkg

COPY scan.py /usr/local/bin/scan.py
RUN useradd -u 10001 -m scan
USER scan
ENTRYPOINT ["python3", "/usr/local/bin/scan.py"]
