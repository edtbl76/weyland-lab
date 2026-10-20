# Ranger Admin 2.6.0 for L5 (Trino authorization), on a MAINTAINED base (B221, 2026-10-20).
#
# WHY A REBASE: the only amd64 Ranger 2.6.0 image is the third-party mr3project/ranger:2.6.0, built on Debian 11, which
# is end of life — its packages left the mirrors (B220 kept it buildable via archive.debian.org, a frozen archive with
# 178 HIGH/CRITICAL that will never be fixed). Ranger Admin itself is a self-contained tree under /opt/mr3-run, so this
# copies that tree UNCHANGED onto Ubuntu 24.04 LTS with a maintained Java 8 (Temurin) and Python 3. Ranger stays 2.6.0: no schema
# migration, nothing changes for the Trino plugin. (B221's extended check: the official apache/ranger:2.9.0 carries 251
# bundled-jar findings itself, so an upgrade would buy no security — backlog B221.)
#
# WHAT CHANGES vs the old image: Debian 11 → Ubuntu 24.04 LTS; Java 8u342 → Temurin 8u504 (same major:
# install.properties requires 1.8); python 3.9 → 3.12 (db_setup.py / dba_script.py import only the stdlib); pgjdbc 42.3.2 → 42.7.14; the
# bundled Solr (247 MB, unused — audit_store is empty) and the MSSQL driver are NOT copied. Everything the k8s manifest
# relies on keeps its path: /opt/mr3-run/ranger/{start-ranger.sh,ranger-admin,conf,key}, JAVA_HOME, the ranger user.
#
# Every input is pinned (digests, a checksum). Build: scripts/build-push-images.sh with RANGER_TAG=<next free tag>.

# ── the Ranger 2.6.0 tree (taken, not run) ─────────────────────────────────────────────────────────────────────────
FROM mr3project/ranger:2.6.0@sha256:3f1bae7b655688784bbd50fdaa0d37ad97aee075095e5790566ac5a8d780603e AS upstream

# ── the current PostgreSQL JDBC driver, checksum-verified (Maven Central's published SHA-1 matched) ───────────────
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f AS fetch
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /postgresql-42.7.14.jar https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.14/postgresql-42.7.14.jar \
    && echo "73914527305a40cce504b0d3d90b23caf565136912d607ae8ae7c5895512332c  /postgresql-42.7.14.jar" | sha256sum -c -

# ── runtime: Ubuntu 24.04 LTS + Temurin Java 8 ─────────────────────────────────────────────────────────────────────
# Ubuntu, not Debian 13 (2026-10-20): trivy on debian:trixie-slim itself showed 43 HIGH OS findings with no fix yet
# (64 with Python 3.13), where this base with the same packages shows 0 HIGH/CRITICAL (146 packages scanned).
FROM eclipse-temurin:8u504-b01-jre-noble@sha256:ba4338edfcaa9eb1df572afca9134710f0e033a1b3c836eca976cdc2f5e38f12
# What Ranger's start-ranger.sh / setup.sh / ranger-admin-services.sh call beyond the base: python3 (db_setup.py),
# procps (ps, kill), passwd (useradd/groupadd/usermod for unix_user=ranger), bc, hostname.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends python3 procps passwd bc hostname \
    && rm -rf /var/lib/apt/lists/*
# The upstream image's ranger user (uid/gid 1000) owns the tree; setup.sh expects it (install.properties unix_user).
# Ubuntu images ship `ubuntu` at uid 1000, so it is removed first.
RUN userdel -r ubuntu 2>/dev/null; groupadd -g 1000 ranger && useradd -u 1000 -g 1000 -m -s /bin/sh ranger
# JAVA_HOME keeps the old image's path (/usr/local/openjdk-8) as a link, in case a script or operator expects it.
# PYTHONWARNINGS: Ranger 2.6.0's db_setup.py has old-style string escapes ("\ "); Python 3.12+ prints a SyntaxWarning
# quoting each offending source line — ~200 lines per boot, containing "[E]" and "error", which log-based alerts match.
# Behaviour is unchanged (the escape stays literal), so silence only that warning class.
RUN ln -s /opt/java/openjdk /usr/local/openjdk-8
ENV JAVA_HOME=/opt/java/openjdk \
    LANG=C.UTF-8 \
    PYTHONWARNINGS=ignore::SyntaxWarning
COPY --from=upstream --chown=1000:1000 /opt/mr3-run/ranger/ranger-admin /opt/mr3-run/ranger/ranger-admin
COPY --from=upstream --chown=1000:1000 /opt/mr3-run/ranger/start-ranger.sh /opt/mr3-run/ranger/start-ranger.sh
COPY --from=upstream --chown=1000:1000 /opt/mr3-run/ranger/conf /opt/mr3-run/ranger/conf
COPY --from=upstream --chown=1000:1000 /opt/mr3-run/ranger/key /opt/mr3-run/ranger/key
COPY --from=upstream --chown=1000:1000 /opt/mr3-run/ranger/work-dir /opt/mr3-run/ranger/work-dir
COPY --from=upstream --chown=1000:1000 /opt/mr3-run/ranger/work-local-dir /opt/mr3-run/ranger/work-local-dir
COPY --from=fetch /postgresql-42.7.14.jar /opt/mr3-run/lib/postgresql-42.7.14.jar
WORKDIR /opt/mr3-run/ranger
# ROOT REQUIRED (B47 accepted exception, unchanged): setup.sh runs useradd/usermod and chowns the tree at every boot.
# nosemgrep: dockerfile.security.last-user-is-root.last-user-is-root
USER root
CMD ["bash"]
