#!/bin/sh
set -eu

snapshot="${SNAPSHOT_ID:?SNAPSHOT_ID is required}"
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates
sed -i "s|http://ports.ubuntu.com/ubuntu-ports/|https://snapshot.ubuntu.com/ubuntu/${snapshot}/|g" /etc/apt/sources.list.d/ubuntu.sources
sed -i '/^Snapshot:/d' /etc/apt/sources.list.d/ubuntu.sources
apt-get update
apt-get install -y --no-install-recommends \
  binutils \
  ca-certificates \
  curl \
  dnsutils \
  fd-find \
  file \
  gdb \
  git \
  iproute2 \
  iputils-ping \
  jq \
  less \
  nmap \
  openssh-client \
  openssh-server \
  openvpn \
  p7zip-full \
  procps \
  python3 \
  ripgrep \
  socat \
  sqlmap \
  tmux \
  unzip \
  util-linux \
  wireguard-tools \
  zsh

case "$(dpkg --print-architecture)" in
  amd64)
    ttyd_asset=ttyd.x86_64
    ttyd_sha256=8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55
    zoxide_asset=zoxide-0.10.0-x86_64-unknown-linux-musl.tar.gz
    zoxide_sha256=2d93385b99f3e82cf2701609a1bffcad863fbeb75aa3fe7eb6be4d29be68b1ae
    ;;
  arm64)
    ttyd_asset=ttyd.aarch64
    ttyd_sha256=b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165
    zoxide_asset=zoxide-0.10.0-aarch64-unknown-linux-musl.tar.gz
    zoxide_sha256=f1f16c5d6298d63dee467eedea1cdcd8490e43e493bea43acd416dc9033ef641
    ;;
  *)
    printf 'unsupported architecture: %s\n' "$(dpkg --print-architecture)" >&2
    exit 1
    ;;
esac

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/tsl0922/ttyd/releases/download/1.7.7/${ttyd_asset}" \
  --output /tmp/ttyd
printf '%s  %s\n' "$ttyd_sha256" /tmp/ttyd | sha256sum -c -
install -m 0555 /tmp/ttyd /usr/bin/ttyd
rm -f /tmp/ttyd

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/ajeetdsouza/zoxide/releases/download/v0.10.0/${zoxide_asset}" \
  --output /tmp/zoxide.tar.gz
printf '%s  %s\n' "$zoxide_sha256" /tmp/zoxide.tar.gz | sha256sum -c -
rm -rf /tmp/zoxide
mkdir /tmp/zoxide
tar -xzf /tmp/zoxide.tar.gz -C /tmp/zoxide
install -m 0555 /tmp/zoxide/zoxide /usr/bin/zoxide
rm -rf /tmp/zoxide /tmp/zoxide.tar.gz

rm -f /etc/ssh/ssh_host_*
apt-get clean
rm -rf /var/lib/apt/lists/*
