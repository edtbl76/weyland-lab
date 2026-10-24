# mlflow-upgrade-drill, container `mlflow` (the image under test). Waits for `pg` to finish the restore, then runs the
# REAL `mlflow db upgrade` against the restored copy (timed), starts the server on it (127.0.0.1, local artifact dir,
# no MinIO, no network), and asks it /health and the AI Gateway's endpoint list, which is read from that database.
# Prints `upgrade: ok <seconds>` (or `upgrade: FAILED`), `health: <body>`, `endpoints: <n>`. Always signals done.
set -u
# The live command's scheme (the wrapper reads it from k8s/mlflow/mlflow.yaml), so the driver choice is production's.
DB="${MLFLOW_DRILL_DB_SCHEME:?the wrapper passes the live URI scheme}://postgres@127.0.0.1:5432/mlflow"
echo "connect scheme: ${MLFLOW_DRILL_DB_SCHEME}"
i=0
while [ ! -f /shared/ready ] && [ "$i" -lt 1200 ]; do sleep 1; i=$((i + 1)); done
[ -f /shared/ready ] || { echo "upgrade: FAILED (the restore never finished)"; touch /shared/done; exit 1; }
echo "image mlflow: $(python -c 'import mlflow; print(mlflow.__version__)')"
start=$(date +%s)
if mlflow db upgrade "$DB" > /tmp/upgrade.log 2>&1; then
  echo "upgrade: ok $(( $(date +%s) - start ))"
else
  echo "upgrade: FAILED"; tail -15 /tmp/upgrade.log; touch /shared/done; exit 1
fi
grep -E "Running upgrade" /tmp/upgrade.log | sed 's/^.*Running upgrade/migration:/' || true
mlflow server --host 127.0.0.1 --port 5000 --backend-store-uri "$DB" --artifacts-destination /tmp/art \
  --serve-artifacts --workers 1 > /tmp/server.log 2>&1 &
n=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)" 2>/dev/null \
      || [ "$n" -ge 90 ]; do sleep 2; n=$((n + 1)); done
echo "health: $(python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5).read().decode())" 2>&1 | tail -1)"
echo "endpoints: $(python -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('http://127.0.0.1:5000/api/3.0/mlflow/gateway/endpoints/list', timeout=20))
print(len(d.get('endpoints') or []))" 2>&1 | tail -1)"
touch /shared/done
