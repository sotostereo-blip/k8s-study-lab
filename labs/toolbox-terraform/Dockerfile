# Terraform lab workstation: terraform + AWS CLI, talking to LocalStack (a free local AWS emulator).
FROM alpine:3.20
ARG TARGETARCH
ARG TERRAFORM_VERSION=1.12.2
RUN apk add --no-cache bash bash-completion curl jq vim nano less ncurses ttyd ca-certificates git aws-cli unzip \
 && curl -fsSL -o /tmp/tf.zip "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" \
 && unzip -q /tmp/tf.zip -d /usr/local/bin terraform && rm /tmp/tf.zip
# Providers are mirrored into the image, so `terraform init` works fast and offline in every lab.
COPY mirror.tf /opt/mirror/main.tf
RUN cd /opt/mirror && terraform providers mirror /opt/terraform/providers && rm -rf /opt/mirror
COPY terraformrc /root/.terraformrc
COPY aws-provider.tf /opt/lab/aws-provider.tf
COPY lab-ready /usr/local/bin/lab-ready
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-ready && terraform -install-autocomplete 2>/dev/null; true
ENV TERM=xterm-256color \
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
    AWS_ENDPOINT_URL=http://localstack:4566 AWS_PAGER=""
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
