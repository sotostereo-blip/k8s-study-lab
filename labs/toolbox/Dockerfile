# Lab workstation: the shell you get in the browser (ttyd) with kubectl ready.
FROM alpine:3.20
ARG TARGETARCH
ARG KUBECTL_VERSION=v1.37.2
ARG HELM_VERSION=v3.16.3
ARG TRIVY_VERSION=0.76.2
ARG KUBELINTER_VERSION=v0.8.3
RUN apk add --no-cache bash bash-completion curl jq vim nano less ncurses ttyd ca-certificates openssl tar \
 && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
 && chmod +x /usr/local/bin/kubectl \
 && curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" | tar -xz -C /tmp \
 && mv /tmp/linux-${TARGETARCH}/helm /usr/local/bin/helm && rm -rf /tmp/linux-* \
 && TRIVY_ARCH=$([ "$TARGETARCH" = arm64 ] && echo ARM64 || echo 64bit) \
 && curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-${TRIVY_ARCH}.tar.gz" | tar -xz -C /usr/local/bin trivy \
 && KL_SUFFIX=$([ "$TARGETARCH" = arm64 ] && echo _arm64 || echo "") \
 && curl -fsSL -o /usr/local/bin/kube-linter "https://github.com/stackrox/kube-linter/releases/download/${KUBELINTER_VERSION}/kube-linter-linux${KL_SUFFIX}" \
 && chmod +x /usr/local/bin/kube-linter \
 && trivy image --download-db-only --cache-dir /opt/trivy --no-progress
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
# trivy uses the vulnerability database baked into the image (fast, offline, same result for the checker)
ENV KUBECONFIG=/root/.kube/config TERM=xterm-256color \
    TRIVY_CACHE_DIR=/opt/trivy TRIVY_SKIP_DB_UPDATE=true TRIVY_SKIP_JAVA_DB_UPDATE=true TRIVY_NO_PROGRESS=true TRIVY_PKG_TYPES=os
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
