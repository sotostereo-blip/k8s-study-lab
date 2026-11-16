# A Kubernetes node built with kubeadm (CKA tasks on etcd, kubeadm upgrade and kubeadm join).
# Base: the kind node image (systemd, containerd, kubeadm/kubelet/kubectl 1.36.4, control-plane images).
# Added: sshd, etcdctl/etcdutl, and a local apt repository with kubeadm/kubelet/kubectl 1.37.2, so the
# upgrade is done with the real commands (apt-get install kubeadm=1.37.2-1.1 ...) without internet.
# apt keeps kind's /etc/default/kubelet without asking (on a real node the package owns that file).
FROM kindest/node:v1.36.4
ARG TARGETARCH
ARG ETCD_VERSION=v3.6.8
ARG K8S_MINOR=v1.37
ARG K8S_NEW=1.37.2-1.1
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server vim-tiny nano less jq curl gnupg dpkg-dev \
 && curl -fsSL "https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-${TARGETARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin --strip-components=1 "etcd-${ETCD_VERSION}-linux-${TARGETARCH}/etcdctl" "etcd-${ETCD_VERSION}-linux-${TARGETARCH}/etcdutl" \
 && mkdir -p /etc/apt/keyrings /opt/k8s-repo \
 && curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" | gpg --dearmor -o /etc/apt/keyrings/k8s.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/k8s.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /" > /etc/apt/sources.list.d/k8s-online.list \
 && apt-get update \
 && apt-get install -y --download-only kubeadm=${K8S_NEW} kubelet=${K8S_NEW} kubectl=${K8S_NEW} \
 && cp /var/cache/apt/archives/*.deb /opt/k8s-repo/ \
 && cd /opt/k8s-repo && dpkg-scanpackages . /dev/null > Packages && gzip -k Packages \
 && { echo "Origin: lab"; echo "Label: lab"; echo "Date: $(date -Ru)"; echo "SHA256:"; \
      for f in Packages Packages.gz; do echo " $(sha256sum $f | cut -d' ' -f1) $(stat -c%s $f) $f"; done; } > Release \
 && rm /etc/apt/sources.list.d/k8s-online.list \
 && rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list \
 && echo "deb [trusted=yes] file:/opt/k8s-repo ./" > /etc/apt/sources.list.d/kubernetes.list \
 && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb \
 && printf 'Dpkg::Options { "--force-confdef"; "--force-confold"; };\n' > /etc/apt/apt.conf.d/90-lab-keep-config \
 && mkdir -p /run/sshd \
 && printf 'PermitRootLogin prohibit-password\nPasswordAuthentication no\n' > /etc/ssh/sshd_config.d/lab.conf
COPY kubeadm.yaml /kind/lab/kubeadm.yaml
COPY lab-node /usr/local/bin/lab-node
COPY lab-node.service /etc/systemd/system/lab-node.service
COPY bashrc /root/.bashrc
COPY lab-etcdctl /usr/local/lib/lab/etcdctl
RUN chmod +x /usr/local/bin/lab-node /usr/local/lib/lab/etcdctl \
 && ln -sf /etc/systemd/system/lab-node.service /etc/systemd/system/multi-user.target.wants/lab-node.service \
 && ln -sf /usr/lib/systemd/system/ssh.service /etc/systemd/system/multi-user.target.wants/ssh.service
