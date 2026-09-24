#!/bin/sh
set -eu

test -d /workspace
test -x /usr/local/bin/light-entrypoint
test -x /usr/bin/zsh
test -r /opt/seclab/oh-my-zsh/oh-my-zsh.sh
test -r /home/lab/.zshrc
test -r /home/lab/.tmux.conf
test -x /usr/bin/zoxide
test -x /usr/sbin/sshd
test -x /usr/bin/ttyd
test -x /usr/local/bin/vpn-manager
test -x /usr/local/bin/vpn-control
test -r /etc/ssh/sshd_config.seclab
test -s /run/ssh/sshd.pid
test -s /run/ttyd.pid

kill -0 "$(cat /run/ssh/sshd.pid)"
kill -0 "$(cat /run/ttyd.pid)"
printf 'light-health=ok\n'
