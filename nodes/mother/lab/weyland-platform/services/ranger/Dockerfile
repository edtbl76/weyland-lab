# Thin image for the L5 Ranger Admin: mr3project/ranger:2.6.0 + python3.
# The base ships ONLY python2.7, but Ranger 2.6's setup (db_setup.py) is python3 — baking it here removes the
# per-boot `apt-get install python3` (and its egress dependency + memory/CPU spike) that the k8s command-wrapper
# used to do. Base is on Docker Hub, so this builds fine on mother's docker (no registry-CA trust needed).
#
# Build + import into k3s containerd (on mother), then k8s pulls the local tag (imagePullPolicy: Never):
#   docker build -t weyland/ranger:2.6.0-py3 services/ranger
#   docker save weyland/ranger:2.6.0-py3 | sudo ctr -n k8s.io images import -
FROM mr3project/ranger:2.6.0
# nosemgrep: dockerfile.security.last-user-is-root.last-user-is-root -- ROOT REQUIRED (B47 accepted exception): the
# mr3project/ranger base runs tomcat + db_setup as root; this USER root is for the apt layer and matches the base's
# runtime user. Forcing non-root risks breaking L5 Trino authz (painful bring-up). Pod securityContext mitigates.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
