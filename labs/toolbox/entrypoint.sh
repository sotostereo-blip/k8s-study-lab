#!/bin/bash
# Wait for the k3s server to write its kubeconfig, point it at the "server" host, start the web terminal.
mkdir -p /root/.kube
until [ -s /output/kubeconfig.yaml ]; do sleep 1; done
sed 's#https://127.0.0.1:6443#https://server:6443#' /output/kubeconfig.yaml > /root/.kube/config
chmod 600 /root/.kube/config
exec ttyd -W -p 7681 -t fontSize=14 -t titleFixed="k8s lab" bash
