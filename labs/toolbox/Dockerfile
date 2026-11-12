# Lab workstation: the shell you get in the browser (ttyd) with kubectl ready.
FROM alpine:3.20
ARG TARGETARCH
ARG KUBECTL_VERSION=v1.31.4
ARG HELM_VERSION=v3.16.3
RUN apk add --no-cache bash bash-completion curl jq vim nano less ncurses ttyd ca-certificates openssl tar \
 && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
 && chmod +x /usr/local/bin/kubectl \
 && curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" | tar -xz -C /tmp \
 && mv /tmp/linux-${TARGETARCH}/helm /usr/local/bin/helm && rm -rf /tmp/linux-*
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV KUBECONFIG=/root/.kube/config TERM=xterm-256color
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
