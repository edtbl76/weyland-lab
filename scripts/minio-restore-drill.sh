#!/usr/bin/env bash
# minio-restore-drill.sh <bucket> — print a one-off k8s Job that PROVES one bucket can be restored from the
# minio-backup mirror (PVC minio-backup on mother's NVMe, written nightly by the minio-backup CronJob). 2026-10-13.
#
# docs/dr.md listed this restore as "`mc mirror` back from the PVC" with no procedure and no test. The Job mounts the
# backup PVC READ-ONLY, mirrors /backup/minio/<bucket> into a scratch bucket `restore-drill-<bucket>`, and passes only
# when the scratch bucket matches the backup exactly (`mc diff` empty, same object count). The scratch bucket is always
# removed. It also reports how far the live bucket has moved since the backup (informational: the live bucket keeps
# changing). Run it (runbook storage-minio.md § Restore drill):
#
#   [rogueone] bash scripts/minio-restore-drill.sh ai-sessions | ssh emangini@mother 'KUBECONFIG=$HOME/.kube/config kubectl create -f -'
#
# The image and credentials are read from the CronJob manifest, so the drill cannot drift from the backup. It is never
# placed under k8s/ (Argo would apply it and re-run it on every sync).
# EXIT (this generator): 0 manifest printed · 2 no/malformed bucket, or a bucket the CronJob does not mirror.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_YAML="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/minio/backup.yaml"

bucket="${1:-}"
if [ -z "$bucket" ] || ! [[ "$bucket" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]]; then
  echo "usage: minio-restore-drill.sh <bucket>   (a bucket the minio-backup CronJob mirrors)" >&2
  exit 2
fi

mirrored="$(grep -oE 'for b in [a-z0-9 .-]+; do' "$BACKUP_YAML" | head -1 | sed -E 's/^for b in //; s/; do$//')"
[ -n "$mirrored" ] || { echo "minio-restore-drill: cannot read the bucket list from $BACKUP_YAML" >&2; exit 2; }
case " $mirrored " in
  *" $bucket "*) ;;
  *) echo "minio-restore-drill: '$bucket' is not mirrored by minio-backup (mirrored: $mirrored)" >&2; exit 2 ;;
esac

image="$(grep -oE 'image: [^ ]+' "$BACKUP_YAML" | head -1 | cut -d' ' -f2)"
[ -n "$image" ] || { echo "minio-restore-drill: cannot read the image from $BACKUP_YAML" >&2; exit 2; }

cat <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: minio-restore-drill-${bucket}-$(date +%s)
  namespace: minio
  labels: { app: minio-restore-drill, bucket: ${bucket} }
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 86400
  template:
    spec:
      restartPolicy: Never
      securityContext:
        runAsUser: 0            # the backup files are root-owned (see backup.yaml)
      containers:
        - name: mc
          image: ${image}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: false
            seccompProfile: { type: RuntimeDefault }
          resources:
            requests: { memory: 64Mi, cpu: 50m }
            limits: { memory: 256Mi }
          command: ["/bin/sh", "-c"]
          args:
            - |
              set -u
              B="${bucket}"; D="restore-drill-\$B"; SRC="/backup/minio/\$B"
              fail() { echo "DRILL FAIL bucket=\$B: \$*"; exit 2; }
              mc alias set src http://minio.minio.svc.cluster.local:9000 "\$MC_USER" "\$MC_PASS" >/dev/null || fail "cannot reach MinIO"
              [ -d "\$SRC" ] || fail "no backup of \$B on the PVC (\$SRC missing) — has minio-backup run since \$B was added?"
              n_backup=\$(find "\$SRC" -type f | wc -l)
              [ "\$n_backup" -gt 0 ] || fail "the backup of \$B is empty"
              mc mb "src/\$D" >/dev/null || fail "cannot create scratch bucket \$D (left over from an earlier drill?)"
              trap 'mc rb --force "src/\$D" >/dev/null 2>&1 && echo "scratch bucket \$D removed"' EXIT
              mc mirror --quiet "\$SRC" "src/\$D" >/dev/null || fail "mirror into \$D failed"
              n_restored=\$(mc ls --recursive "src/\$D" | wc -l)
              diffs=\$(mc diff "\$SRC" "src/\$D" | wc -l)
              live=\$(mc diff "src/\$B" "src/\$D" | wc -l)
              [ "\$n_restored" -eq "\$n_backup" ] || fail "restored \$n_restored objects, backup has \$n_backup"
              [ "\$diffs" -eq 0 ] || fail "\$diffs differences between the backup and the restore"
              echo "DRILL OK bucket=\$B backup_objects=\$n_backup restored_objects=\$n_restored differences=0 live_drift_since_backup=\$live"
          env:
            - name: MC_USER
              valueFrom: { secretKeyRef: { name: minio-creds, key: MINIO_ROOT_USER } }
            - name: MC_PASS
              valueFrom: { secretKeyRef: { name: minio-creds, key: MINIO_ROOT_PASSWORD } }
          volumeMounts:
            - { name: backup, mountPath: /backup, readOnly: true }
      volumes:
        - name: backup
          persistentVolumeClaim: { claimName: minio-backup, readOnly: true }
YAML
