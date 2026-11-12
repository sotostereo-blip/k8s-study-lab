#!/bin/bash
# Log tea in as soon as Gitea is up (lab-ready does it too), then serve the web terminal.
( for i in $(seq 1 120); do lab-ready && break; sleep 2; done ) >/dev/null 2>&1 &
exec ttyd -W -p 7681 -t fontSize=14 -t titleFixed="github actions lab" bash
