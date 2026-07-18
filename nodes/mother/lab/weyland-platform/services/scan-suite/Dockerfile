# B69 Wave 4 — weekly code-scan suite. ONE image bundling the free static/security/quality scanners so a single
# CronJob clones the repo once and runs them all → per-tool severity counts POSTed to the Port `code-quality`
# webhook (same payload as the semgrep/trivy Jobs) + raw JSON saved to /mnt/minio/scan-reports. Built + pushed to
# registry.weyland.lab via scripts/build-push-images.sh. Pin bumps: check each tool's latest release if a URL 404s.
FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git xz-utils default-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir checkov==3.2.257 bandit==1.7.10 semgrep==1.90.0

# Static binaries (amd64). Each is a single file → drop into /usr/local/bin.
RUN set -eux; \
    curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz" | tar -xz -C /usr/local/bin gitleaks; \
    curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v0.56.2/trivy_0.56.2_Linux-64bit.tar.gz" | tar -xz -C /usr/local/bin trivy; \
    curl -fsSL -o /usr/local/bin/hadolint "https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64"; \
    curl -fsSL -o /usr/local/bin/kubescape "https://github.com/kubescape/kubescape/releases/download/v3.0.8/kubescape-ubuntu-latest"; \
    curl -fsSL -o /usr/local/bin/osv-scanner "https://github.com/google/osv-scanner/releases/download/v1.9.1/osv-scanner_linux_amd64"; \
    curl -fsSL "https://github.com/koalaman/shellcheck/releases/download/v0.10.0/shellcheck-v0.10.0.linux.x86_64.tar.xz" | tar -xJ --strip-components=1 -C /usr/local/bin shellcheck-v0.10.0/shellcheck; \
    curl -fsSL -o /opt/code-maat.jar "https://github.com/adamtornhill/code-maat/releases/download/v1.0.4/code-maat-1.0.4-standalone.jar"; \
    chmod +x /usr/local/bin/hadolint /usr/local/bin/kubescape /usr/local/bin/osv-scanner

COPY scan.py /usr/local/bin/scan.py
RUN useradd -u 10001 -m scan
USER scan
ENTRYPOINT ["python3", "/usr/local/bin/scan.py"]
