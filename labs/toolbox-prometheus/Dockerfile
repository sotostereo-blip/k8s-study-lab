# Prometheus lab workstation: promtool, amtool, curl, jq, yq, python3 + prometheus_client, ttyd.
# The config files the learner edits are seeded into the shared /lab volume (see entrypoint.sh).
FROM prom/prometheus:v3.15.1 AS prometheus
FROM prom/alertmanager:v0.34.2 AS alertmanager
FROM alpine:3.22
RUN apk add --no-cache bash bash-completion curl jq yq-go vim nano less ncurses ttyd ca-certificates \
      python3 py3-prometheus-client procps
COPY --from=prometheus /bin/promtool /usr/local/bin/promtool
COPY --from=alertmanager /bin/amtool /usr/local/bin/amtool
COPY amtool.yml /etc/amtool/config.yml
COPY seed /opt/lab-seed
COPY lab-ready promql-compare promq /usr/local/bin/
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-ready /usr/local/bin/promql-compare /usr/local/bin/promq \
 && promtool --version >/dev/null && amtool --version >/dev/null
ENV TERM=xterm-256color PROM=http://prometheus:9090 AM=http://alertmanager:9093
WORKDIR /root
HEALTHCHECK --interval=2s --timeout=2s --retries=30 CMD test -e /lab/.seeded
ENTRYPOINT ["/entrypoint.sh"]
