# Terminal for the kubeadm lab: the Kubernetes toolbox + an SSH client for `ssh controlplane` / `ssh node01`.
FROM k8s-study-lab/toolbox:3
RUN apk add --no-cache openssh-client \
 && mkdir -p /root/.ssh && chmod 700 /root/.ssh \
 && printf 'Host controlplane node01\n    User root\n    IdentityFile /lab/ssh/id_ed25519\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null\n    LogLevel ERROR\n' > /root/.ssh/config
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
