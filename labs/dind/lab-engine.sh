#!/bin/sh
# Start dockerd (the normal dind entrypoint), then load the preloaded images once it answers.
dockerd-entrypoint.sh "$@" &
pid=$!
trap 'kill -TERM $pid 2>/dev/null' TERM INT
(
  until docker info >/dev/null 2>&1; do sleep 1; done
  for f in /preload/*.tar; do docker load -q -i "$f" >/dev/null || echo "preload failed: $f"; done
  echo "lab images loaded"
) &
wait $pid
