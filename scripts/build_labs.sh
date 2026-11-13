#!/bin/sh
# Download and build the lab images ahead of time, so the first lab of each kind starts fast.
# Optional: the app builds an environment's images the first time you open one of its labs.
#
#   sh scripts/build_labs.sh                 # every environment (~15 GB of disk, 15-40 minutes)
#   sh scripts/build_labs.sh single-node linux   # only these (names: ls labs/envs)
set -e
cd "$(dirname "$0")/.."
envs="${*:-single-node two-node secure-node argocd linux docker gitea prometheus terraform aws}"
for e in $envs; do
  f="labs/envs/$e/compose.yaml"
  [ -f "$f" ] || { echo "unknown environment: $e (see labs/envs/)"; exit 1; }
  # the Argo CD toolbox is built FROM the Kubernetes toolbox image
  if [ "$e" = argocd ] && ! docker image inspect k8s-study-lab/toolbox:3 >/dev/null 2>&1; then
    echo "== base image k8s-study-lab/toolbox:3"
    docker compose -p k8slab -f labs/envs/single-node/compose.yaml build toolbox
  fi
  echo "== $e"
  docker compose -p k8slab -f "$f" pull --ignore-buildable --quiet
  docker compose -p k8slab -f "$f" build
done
echo "Lab images ready."
