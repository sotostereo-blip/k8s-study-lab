# AWS lab workstation: AWS CLI (+ jq) talking to LocalStack, a free local AWS emulator.
FROM alpine:3.20
RUN apk add --no-cache bash bash-completion curl jq vim nano less ncurses ttyd ca-certificates aws-cli
COPY lab-ready /usr/local/bin/lab-ready
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-ready
ENV TERM=xterm-256color \
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
    AWS_ENDPOINT_URL=http://localstack:4566 AWS_PAGER=""
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
