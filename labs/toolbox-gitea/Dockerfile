# GitHub Actions lab workstation: git (already logged in to the lab Gitea), tea (Gitea CLI),
# curl + jq for the Gitea API, actionlint to check workflow files, vim/nano and ttyd.
FROM alpine:3.22
ARG TARGETARCH
ARG TEA_VERSION=0.16.0
ARG ACTIONLINT_VERSION=1.7.12
RUN apk add --no-cache bash bash-completion curl jq yq-go git vim nano less ncurses ttyd ca-certificates tar unzip \
 && curl -fsSL -o /usr/local/bin/tea "https://dl.gitea.com/tea/${TEA_VERSION}/tea-${TEA_VERSION}-linux-${TARGETARCH}" \
 && chmod +x /usr/local/bin/tea \
 && curl -fsSL "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${TARGETARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin actionlint
COPY gitconfig /root/.gitconfig
COPY git-credentials /root/.git-credentials
COPY bin/ /usr/local/bin/
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod 600 /root/.git-credentials && chmod +x /entrypoint.sh /usr/local/bin/*
ENV TERM=xterm-256color GITEA_URL=http://gitea:3000 GITEA_USER=student GITEA_PASSWORD=studylab123 EDITOR=vim
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
