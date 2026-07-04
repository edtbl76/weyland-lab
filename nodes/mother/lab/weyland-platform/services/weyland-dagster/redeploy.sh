#!/usr/bin/env bash
# Rebuild + redeploy the Dagster user-code image ON MOTHER. Collapses the four-command litany into one,
# WITHOUT collapsing the build↔runtime anti-corruption boundary (docker build → ctr import stays explicit —
# that's why nerdctl's build-straight-into-k3s was declined at B24; see docs/arch.md §12).
#
# Usage (two commands total):
#   [rogueone] rsync -a --delete <repo>/services/weyland-dagster/ emangini@mother:~/weyland-dagster/
#   [mother]   bash ~/weyland-dagster/redeploy.sh
set -euo pipefail

IMAGE="weyland-dagster-user-code:local"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> [1/4] docker build ${IMAGE}  (context: ${DIR})"
docker build -t "${IMAGE}" "${DIR}"

echo "==> [2/4] import into k3s containerd (k8s.io namespace)"
docker save "${IMAGE}" | sudo ctr -n k8s.io images import -

echo "==> [3/4] rollout restart dagster-user-code"
kubectl -n weyland rollout restart deploy/dagster-user-code
kubectl -n weyland rollout status deploy/dagster-user-code --timeout=180s

echo "==> [4/4] verify the store-loader deps import inside the new pod"
kubectl -n weyland exec deploy/dagster-user-code -- \
  python -c "import clickhouse_connect, cassandra, pymongo, sqlalchemy_cockroachdb, opensearchpy, neo4j, qdrant_client, weaviate, sentence_transformers, librosa, confluent_kafka; print('store-loader imports OK')" \
  || echo "!! import check failed — inspect the pod (does not fail the deploy)"

echo "==> done."
