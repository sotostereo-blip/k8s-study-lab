# LFCS lab server: Ubuntu 24.04 with systemd as PID 1 (systemctl, journalctl, timers work),
# common admin tools, sshd and a web terminal (ttyd as a systemd service on port 7681).
# The same image runs the second host `server2` (sshd only, no web terminal).
FROM ubuntu:24.04
ENV container=docker DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      systemd systemd-sysv systemd-resolved- dbus ca-certificates locales-all- \
      bash-completion vim nano less man-db- file tree jq procps psmisc lsof htop sysstat \
      iproute2 iputils-ping dnsutils net-tools curl wget traceroute netcat-openbsd tcpdump \
      lvm2 parted fdisk e2fsprogs xfsprogs dosfstools acl quota attr kmod util-linux \
      cron at logrotate rsyslog- openssh-server openssh-client sudo \
      tar gzip bzip2 xz-utils zip unzip rsync \
      ufw nftables iptables chrony git python3 nginx-light ttyd openssl apt-utils \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
# Units that make no sense in a container (no real console, kernel modules or udev triggers).
RUN systemctl mask getty@tty1.service console-getty.service systemd-modules-load.service \
      systemd-udev-trigger.service systemd-udevd.service systemd-udevd-control.socket \
      systemd-udevd-kernel.socket sys-kernel-config.mount sys-kernel-debug.mount \
      sys-kernel-tracing.mount systemd-remount-fs.service systemd-firstboot.service \
      lvm2-monitor.service lvm2-lvmpolld.socket chrony.service \
      apt-daily.timer apt-daily-upgrade.timer motd-news.timer dpkg-db-backup.timer e2scrub_all.timer fstrim.timer \
 && systemctl disable nginx.service \
 && sed -i 's/^\(\s*udev_sync\s*=\).*/\1 0/; s/^\(\s*udev_rules\s*=\).*/\1 0/' /etc/lvm/lvm.conf \
 && printf 'activation {\n  udev_sync = 0\n  udev_rules = 0\n}\n' > /etc/lvm/lvmlocal.conf
# SSH: root on one host can log in to the other with the lab key (like a jump host in the exam).
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh \
 && ssh-keygen -q -t ed25519 -N '' -C lab-root -f /root/.ssh/id_ed25519 \
 && cp /root/.ssh/id_ed25519.pub /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys \
 && printf 'Host *\n    StrictHostKeyChecking accept-new\n' > /etc/ssh/ssh_config.d/50-lab.conf \
 && systemctl enable ssh.service
COPY ttyd.service /etc/systemd/system/ttyd.service
COPY lab-ready /usr/local/bin/lab-ready
COPY bashrc /root/.bashrc
RUN chmod +x /usr/local/bin/lab-ready && systemctl enable ttyd.service \
 && rm -rf /var/log/journal /var/lib/dbus/machine-id && : > /etc/machine-id
# Empty machine-id: every container gets its own. No /var/log/journal: the journal is volatile
# (in /run) until someone makes it persistent, as on a fresh minimal install.
STOPSIGNAL SIGRTMIN+3
WORKDIR /root
CMD ["/sbin/init"]
