# DCA lab workstation: docker CLI + compose + buildx, talking to the dind engine (service "docker").
FROM docker:29.9.2-cli
RUN apk add --no-cache bash bash-completion curl jq vim nano less ncurses git ttyd ca-certificates tree \
 && mkdir -p /lab
COPY lab-ready /usr/local/bin/lab-ready
COPY bashrc /root/.bashrc
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/lab-ready
ENV TERM=xterm-256color DOCKER_HOST=tcp://docker:2375 EDITOR=vim
WORKDIR /lab
ENTRYPOINT ["/entrypoint.sh"]
