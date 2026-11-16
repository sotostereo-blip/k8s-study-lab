#!/bin/sh
# Get the lab images ahead of time, so the first lab of each kind starts fast.
# Optional: the app gets an environment's images the first time you open one of its labs.
#
#   sh scripts/build_labs.sh                     # every environment (~15 GB of disk)
#   sh scripts/build_labs.sh single-node linux   # only these (names: ls labs/envs)
#
# Ready-made images are downloaded from LAB_IMAGE_REGISTRY when it has them (published by
# .github/workflows/lab-images.yml); the others are built here (15-40 minutes for all).
# LAB_IMAGE_REGISTRY= sh scripts/build_labs.sh   always builds here (after you edit labs/).
set -e
cd "$(dirname "$0")/.."
REG="${LAB_IMAGE_REGISTRY-ghcr.io/sotostereo-blip/k8s-study-lab}"
envs="${*:-single-node two-node secure-node argocd linux docker gitea prometheus terraform aws}"
for e in $envs; do
  f="labs/envs/$e/compose.yaml"
  [ -f "$f" ] || { echo "unknown environment: $e (see labs/envs/)"; exit 1; }
  echo "== $e"
  if [ -n "$REG" ]; then
    for img in $(docker compose -p k8slab -f "$f" config --images | grep '^k8s-study-lab/' | sort -u); do
      remote="$REG/${img#k8s-study-lab/}"
      if docker pull -q "$remote" >/dev/null 2>&1; then
        docker tag "$remote" "$img" && echo "downloaded $img"
      fi
    done
  fi
  # the Argo CD toolbox is built FROM the Kubernetes toolbox image
  if [ "$e" = argocd ] && ! docker image inspect k8s-study-lab/toolbox:3 >/dev/null 2>&1; then
    echo "building base image k8s-study-lab/toolbox:3"
    docker compose -p k8slab -f labs/envs/single-node/compose.yaml build toolbox
  fi
  docker compose -p k8slab -f "$f" pull --ignore-buildable --quiet
  if [ -n "$REG" ]; then
    # builds only the images that are still missing, then removes the containers it created
    out=$(docker compose -p k8slab -f "$f" create --quiet-pull 2>&1) || { echo "$out"; exit 1; }
    docker compose -p k8slab -f "$f" down -v >/dev/null 2>&1
  else
    docker compose -p k8slab -f "$f" build
  fi
done
echo "Lab images ready."
