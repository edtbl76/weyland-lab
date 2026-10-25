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
# Production's start-up order: rotate the KEK if needed (the manifest's ConfigMap script, B227 follow-on), then migrate.
if [ -n "${MLFLOW_CRYPTO_KEK_PASSPHRASE:-}" ]; then
  # the script prints its own "kek: ..." verdict line, failure included (the drill's verdict reads it)
  sh /drill/rotate-kek-if-needed.sh "$DB" 2>&1 | tail -3
fi
start=$(date +%s)
if mlflow db upgrade "$DB" > /tmp/upgrade.log 2>&1; then
  echo "upgrade: ok $(( $(date +%s) - start ))"
else
  echo "upgrade: FAILED"; tail -15 /tmp/upgrade.log; touch /shared/done; exit 1
fi
grep -E "Running upgrade" /tmp/upgrade.log | sed 's/^.*Running upgrade/migration:/' || true
# Production's worker count and env (the wrapper copies the live container's literal env values into this container):
# 3.17's guarded gateway calls itself, so a one-worker drill deadlocks where two workers do not.
mlflow server --host 127.0.0.1 --port 5000 --backend-store-uri "$DB" --artifacts-destination /tmp/art \
  --serve-artifacts --workers "${MLFLOW_DRILL_WORKERS:?the wrapper passes the live --workers}" > /tmp/server.log 2>&1 &
n=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)" 2>/dev/null \
      || [ "$n" -ge 90 ]; do sleep 2; n=$((n + 1)); done
echo "health: $(python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5).read().decode())" 2>&1 | tail -1)"
echo "endpoints: $(python -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('http://127.0.0.1:5000/api/3.0/mlflow/gateway/endpoints/list', timeout=20))
print(len(d.get('endpoints') or []))" 2>&1 | tail -1)"
# A REAL request through the gateway (guardrails + judge included) to the restored copy's own endpoint and secret:
# the call that failed in production on 2026-10-25 while every list above passed.
echo "chat: $(python -c "
import json, urllib.request, urllib.error
ep = 'ollama-qwen25-7b'
req = urllib.request.Request('http://127.0.0.1:5000/gateway/mlflow/v1/chat/completions', headers={'Content-Type': 'application/json'},
    data=json.dumps({'model': ep, 'max_tokens': 5, 'messages': [{'role': 'user', 'content': 'Reply with the word OK.'}]}).encode())
try:
    r = json.load(urllib.request.urlopen(req, timeout=170))
    t = ((r.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
    print(('ok ' + ep + ' answered') if t.strip() else 'FAILED empty answer')
except urllib.error.HTTPError as e:
    print('FAILED HTTP', e.code, e.read().decode(errors='replace')[:160])
except Exception as e:
    print('FAILED', type(e).__name__, str(e)[:160])" 2>&1 | tail -1)"
touch /shared/done
