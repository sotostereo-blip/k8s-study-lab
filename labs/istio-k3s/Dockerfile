# k3s server with every image the Istio labs need preloaded (airgap tarball imported at boot),
# so a lab starts without pulling istiod and the Envoy proxy from the internet.
FROM alpine:3.22 AS images
ARG TARGETARCH
ARG CRANE_VERSION=v0.20.2
RUN apk add --no-cache curl tar \
 && CRANE_ARCH=$([ "$TARGETARCH" = arm64 ] && echo arm64 || echo x86_64) \
 && curl -fsSL "https://github.com/google/go-containerregistry/releases/download/${CRANE_VERSION}/go-containerregistry_Linux_${CRANE_ARCH}.tar.gz" | tar -xz -C /usr/local/bin crane
COPY images.txt /images.txt
RUN mkdir /out && crane pull --platform "linux/${TARGETARCH}" $(grep -v '^#' /images.txt) /out/istio-lab-images.tar

FROM rancher/k3s:v1.37.2-k3s1
COPY --from=images /out/istio-lab-images.tar /var/lib/rancher/k3s/agent/images/istio-lab-images.tar
