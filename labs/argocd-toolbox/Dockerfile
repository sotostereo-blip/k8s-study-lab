# Argo lab workstation: the k8s toolbox (kubectl, helm, jq, ttyd) plus git, the argocd,
# argo and kubectl-argo-rollouts CLIs (and Argo Events), and the install manifests applied at lab start.
FROM k8s-study-lab/toolbox:3
ARG TARGETARCH
ARG ARGOCD_VERSION=v3.5.7
ARG ROLLOUTS_VERSION=v1.10.2
ARG WORKFLOWS_VERSION=v4.1.6
ARG EVENTS_VERSION=v1.9.11
RUN apk add --no-cache git yq \
 && curl -fsSL -o /usr/local/bin/argocd "https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-linux-${TARGETARCH}" \
 && curl -fsSL -o /usr/local/bin/kubectl-argo-rollouts "https://github.com/argoproj/argo-rollouts/releases/download/${ROLLOUTS_VERSION}/kubectl-argo-rollouts-linux-${TARGETARCH}" \
 && curl -fsSL "https://github.com/argoproj/argo-workflows/releases/download/${WORKFLOWS_VERSION}/argo-linux-${TARGETARCH}.gz" | gunzip > /usr/local/bin/argo \
 && chmod +x /usr/local/bin/argocd /usr/local/bin/kubectl-argo-rollouts /usr/local/bin/argo \
 && curl -fsSL -o /opt/argocd-install.yaml "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml" \
 && curl -fsSL -o /opt/rollouts-install.yaml "https://github.com/argoproj/argo-rollouts/releases/download/${ROLLOUTS_VERSION}/install.yaml" \
 && curl -fsSL -o /opt/workflows-install.yaml "https://github.com/argoproj/argo-workflows/releases/download/${WORKFLOWS_VERSION}/install.yaml" \
 && curl -fsSL -o /opt/events-install.yaml "https://github.com/argoproj/argo-events/releases/download/${EVENTS_VERSION}/install.yaml" \
 && git config --system init.defaultBranch main \
 && git config --system user.name "Lab Student" \
 && git config --system user.email "student@lab.local" \
 && git config --system --add safe.directory '*'
COPY argocd /opt/argocd
COPY rollouts /opt/rollouts
COPY workflows /opt/workflows
COPY events /opt/events
RUN mv /opt/argocd-install.yaml /opt/argocd/install.yaml \
 && mv /opt/rollouts-install.yaml /opt/rollouts/install.yaml \
 && mv /opt/workflows-install.yaml /opt/workflows/install.yaml \
 && mv /opt/events-install.yaml /opt/events/install.yaml
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
COPY lab-bootstrap lab-ready lab-repo /usr/local/bin/
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-bootstrap /usr/local/bin/lab-ready /usr/local/bin/lab-repo
