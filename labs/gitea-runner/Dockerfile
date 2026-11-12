# act_runner in host mode: jobs run inside this container, so it needs node (for JavaScript
# actions such as actions/checkout), git, bash and a few common tools.
FROM gitea/act_runner:0.6.1
RUN apk add --no-cache nodejs npm curl jq tar zstd gzip coreutils findutils grep sed python3 zip unzip
COPY config.yaml /etc/act_runner/config.yaml
