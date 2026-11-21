# Istio lab workstation: the k8s toolbox (kubectl, helm, jq, ttyd) plus istioctl 1.31.4,
# the Istio install file used at lab start. (k3s itself installs the Gateway API CRDs.)
FROM k8s-study-lab/toolbox:3
ARG TARGETARCH
ARG ISTIO_VERSION=1.31.4
RUN apk add --no-cache yq \
 && curl -fsSL "https://github.com/istio/istio/releases/download/${ISTIO_VERSION}/istioctl-${ISTIO_VERSION}-linux-${TARGETARCH}.tar.gz" | tar -xz -C /usr/local/bin istioctl
COPY istio /opt/istio
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
COPY lab-bootstrap lab-ready lab-app /usr/local/bin/
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-bootstrap /usr/local/bin/lab-ready /usr/local/bin/lab-app
