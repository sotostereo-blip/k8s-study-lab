# k3s with the Gateway API: k3s ships the Gateway API CRDs and Traefik; this turns on Traefik's
# Gateway provider (GatewayClass `traefik`, listeners on port 80/443).
FROM rancher/k3s:v1.37.2-k3s1
COPY traefik-gateway.yaml /var/lib/rancher/k3s/server/manifests/traefik-gateway.yaml
