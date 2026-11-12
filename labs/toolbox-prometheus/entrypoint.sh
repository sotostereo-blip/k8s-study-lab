#!/bin/bash
# Seed the shared /lab volume (Prometheus and Alertmanager read their config from it).
if [ ! -e /lab/.seeded ]; then
  cp -a /opt/lab-seed/. /lab/ && chmod -R a+rX /lab && touch /lab/.seeded
fi
mkdir -p /root/answers
exec ttyd -W -p 7681 -t fontSize=14 -t titleFixed="prometheus lab" bash
