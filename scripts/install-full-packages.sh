#!/bin/sh
# Paquetes y datos de la imagen full. Se ejecuta sobre light.
# Requiere SNAPSHOT_ID, PAT_COMMIT, EXPLOITDB_COMMIT y SECLISTS_COMMIT.
set -eu

snapshot="${SNAPSHOT_ID:?SNAPSHOT_ID is required}"
pat_commit="${PAT_COMMIT:?PAT_COMMIT is required}"
exploitdb_commit="${EXPLOITDB_COMMIT:?EXPLOITDB_COMMIT is required}"
seclists_commit="${SECLISTS_COMMIT:?SECLISTS_COMMIT is required}"
export DEBIAN_FRONTEND=noninteractive
printf 'snapshot=%s\n' "$snapshot"

apt-get update
apt-get install -y --no-install-recommends \
  hashcat \
  john \
  libffi8 \
  libgdbm6t64 \
  libpq5 \
  libreadline8t64 \
  libsqlite3-0 \
  libxml2 \
  libxslt1.1 \
  libyaml-0-2 \
  pocl-opencl-icd \
  zlib1g

git clone --depth 1 https://github.com/swisskyrepo/PayloadsAllTheThings.git /tmp/pat
git -C /tmp/pat fetch --depth 1 origin "$pat_commit"
git -C /tmp/pat checkout --detach "$pat_commit"
test "$(git -C /tmp/pat rev-parse HEAD)" = "$pat_commit"
rm -rf /tmp/pat/.git
install -d -m 0755 /usr/local/share/seclab/payloads
cp -r /tmp/pat/. /usr/local/share/seclab/payloads/
rm -rf /tmp/pat

git clone --depth 1 https://gitlab.com/exploit-database/exploitdb.git /tmp/exploitdb
git -C /tmp/exploitdb fetch --depth 1 origin "$exploitdb_commit"
git -C /tmp/exploitdb checkout --detach "$exploitdb_commit"
test "$(git -C /tmp/exploitdb rev-parse HEAD)" = "$exploitdb_commit"
rm -rf /tmp/exploitdb/.git
install -d -m 0755 /opt/exploitdb
cp -r /tmp/exploitdb/. /opt/exploitdb/
rm -rf /tmp/exploitdb
ln -sf /opt/exploitdb/searchsploit /usr/local/bin/searchsploit

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://raw.githubusercontent.com/danielmiessler/SecLists/${seclists_commit}/Passwords/Leaked-Databases/rockyou.txt.tar.gz" \
  --output /tmp/rockyou.tar.gz
printf '%s  %s\n' '47c070a029bcdb4cbd0e02c69fed136ef46dce4048ddbadf177daa5e885b8172' /tmp/rockyou.tar.gz | sha256sum -c -
tar -xzf /tmp/rockyou.tar.gz -C /usr/local/share/seclab/wordlists/
chmod 0644 /usr/local/share/seclab/wordlists/rockyou.txt
rm -f /tmp/rockyou.tar.gz

apt-get clean
rm -rf /var/lib/apt/lists/*
