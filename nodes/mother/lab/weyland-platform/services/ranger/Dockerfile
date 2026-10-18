# Thin image for the L5 Ranger Admin: mr3project/ranger:2.6.0 + python3.
# The base ships ONLY python2.7, but Ranger 2.6's setup (db_setup.py) is python3 — baking it here removes the
# per-boot `apt-get install python3` (and its egress dependency + memory/CPU spike) that the k8s command-wrapper
# used to do. Base is on Docker Hub, so this builds fine on mother's docker (no registry-CA trust needed).
#
# Build + import into k3s containerd (on mother), then k8s pulls the local tag (imagePullPolicy: Never):
#   docker build -t weyland/ranger:2.6.0-py3 services/ranger
#   docker save weyland/ranger:2.6.0-py3 | sudo ctr -n k8s.io images import -
FROM mr3project/ranger:2.6.0
# ROOT REQUIRED (B47 accepted exception): the mr3project/ranger base runs tomcat + db_setup as root; this USER root
# is for the apt layer and matches the base's runtime user. Forcing non-root risks breaking L5 Trino authz (painful
# bring-up). Pod securityContext mitigates.
# nosemgrep: dockerfile.security.last-user-is-root.last-user-is-root
USER root
# Debian 11 (bullseye) is END OF LIFE: its packages left deb.debian.org, so `apt-get update` 404'd and this image could
# not be rebuilt at all (found 2026-10-17, B220). Point apt at archive.debian.org — the final bullseye + bullseye-security
# set, frozen — and `apt-get upgrade` so the fixes published before EOL land (libtirpc 1.3.1-1+deb11u1, …). This keeps
# the image BUILDABLE; it does not make it supported: no new fixes will come (python3.9 has none). The real fix is
# rebuilding Ranger Admin on a maintained Debian (backlog B221). Check-Valid-Until=false: archive Release files expire.
RUN sed -i -e 's|http://deb.debian.org/debian-security|http://archive.debian.org/debian-security|' \
           -e 's|http://deb.debian.org/debian|http://archive.debian.org/debian|' /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
