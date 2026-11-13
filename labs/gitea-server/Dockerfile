# Gitea for the GH-200 lab, with the start script baked in (no bind mount, so the lab also starts
# when the backend itself runs in Docker and talks to the host Docker engine).
FROM gitea/gitea:28.3.0
COPY gitea-start.sh /lab/gitea-start.sh
