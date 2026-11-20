# Vault lab workstation: the vault CLI (same version as the server), psql, jq and a web terminal.
# On start, lab-init initializes and unseals the Vault server and keeps the root token for checks.
FROM alpine:3.22
ARG TARGETARCH
ARG VAULT_VERSION=1.19.5
RUN apk add --no-cache bash bash-completion curl jq vim nano less ncurses ttyd ca-certificates \
      postgresql17-client openssl unzip \
 && curl -fsSL -o /tmp/vault.zip "https://releases.hashicorp.com/vault/${VAULT_VERSION}/vault_${VAULT_VERSION}_linux_${TARGETARCH}.zip" \
 && unzip -q /tmp/vault.zip -d /usr/local/bin vault && rm /tmp/vault.zip
COPY lab-init lab-ready labvault /usr/local/bin/
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-init /usr/local/bin/lab-ready /usr/local/bin/labvault \
 && mkdir -p /etc/lab && chmod 700 /etc/lab
ENV TERM=xterm-256color VAULT_ADDR=http://vault:8200 PGHOST=postgres PGUSER=postgres \
    PGPASSWORD=lab-root-pw PGDATABASE=shop
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
