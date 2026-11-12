# Tiny Git server over HTTP (git-http-backend behind lighttpd). Anonymous clone and push.
# Repositories are bare repos in /srv/git (a volume shared with the toolbox).
FROM alpine:3.20
RUN apk add --no-cache git git-daemon lighttpd \
 && git config --system http.receivepack true \
 && git config --system init.defaultBranch main \
 && git config --system --add safe.directory '*' \
 && mkdir -p /srv/git
COPY lighttpd.conf /etc/lighttpd/git.conf
EXPOSE 80
CMD ["lighttpd", "-D", "-f", "/etc/lighttpd/git.conf"]
