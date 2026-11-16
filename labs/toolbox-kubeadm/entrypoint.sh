#!/bin/bash
# A new SSH key for every lab (shared with the nodes through /lab), then wait for the kubeconfig
# that `kubeadm init` writes on the control plane, then start the web terminal.
mkdir -p /lab/ssh /root/.kube
[ -s /lab/ssh/id_ed25519 ] || ssh-keygen -q -t ed25519 -N '' -C lab -f /lab/ssh/id_ed25519
until [ -s /lab/kubeconfig.yaml ]; do sleep 1; done
cp /lab/kubeconfig.yaml /root/.kube/config && chmod 600 /root/.kube/config
exec ttyd -W -p 7681 -t fontSize=14 -t titleFixed="k8s lab" bash
