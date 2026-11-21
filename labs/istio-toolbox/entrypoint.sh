#!/bin/bash
# Wait for the k3s kubeconfig, point it at the "server" host, install Istio in the background,
# start the web terminal.
mkdir -p /root/.kube
until [ -s /output/kubeconfig.yaml ]; do sleep 1; done
sed 's#https://127.0.0.1:6443#https://server:6443#' /output/kubeconfig.yaml > /root/.kube/config
chmod 600 /root/.kube/config
lab-bootstrap &
exec ttyd -W -p 7681 -t fontSize=14 -t titleFixed="istio lab" bash
