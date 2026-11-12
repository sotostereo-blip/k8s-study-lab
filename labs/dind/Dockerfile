# Docker Engine for the DCA labs, with the small images the tasks use saved inside the image.
# They are loaded with `docker load` when the engine starts, so labs do not wait for Docker Hub.
FROM alpine:3.20 AS images
ARG TARGETARCH
RUN apk add --no-cache skopeo
RUN mkdir /preload && for img in alpine:3.20 busybox:1.36 nginx:1.27-alpine python:3.12-alpine; do \
      skopeo --override-os linux --override-arch "${TARGETARCH}" copy -q \
        "docker://docker.io/library/${img}" "docker-archive:/preload/${img%%:*}.tar:${img}" || exit 1; \
    done

FROM docker:29.9.2-dind
COPY --from=images /preload /preload
COPY daemon.json /etc/docker/daemon.json
COPY lab-engine.sh /usr/local/bin/lab-engine.sh
RUN chmod +x /usr/local/bin/lab-engine.sh
ENTRYPOINT ["/usr/local/bin/lab-engine.sh"]
CMD []
