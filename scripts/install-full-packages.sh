#!/bin/sh
# Paquetes y datos pesados de la imagen del laboratorio: Metasploit, nxc,
# john, hashcat y las wordlists. Se ejecuta tras install-toolkit-packages.
# Requiere SNAPSHOT_ID, PAT_COMMIT, EXPLOITDB_COMMIT y SECLISTS_COMMIT.
set -eu

snapshot="${SNAPSHOT_ID:?SNAPSHOT_ID is required}"
pat_commit="${PAT_COMMIT:?PAT_COMMIT is required}"
exploitdb_commit="${EXPLOITDB_COMMIT:?EXPLOITDB_COMMIT is required}"
seclists_commit="${SECLISTS_COMMIT:?SECLISTS_COMMIT is required}"
export DEBIAN_FRONTEND=noninteractive
printf 'snapshot=%s\n' "$snapshot"

apt-get update
# gdb-multiarch y libusb-1.0-0 van pineados a mano, el resto no.
#   gdb-multiarch: pedido explicito del owner, para que el script no se
#     desvíe de lo que registra supply-chain/tools.lock.yaml.
#   libusb-1.0-0: bettercap lo enlaza en tiempo de ejecucion (gousb es cgo), asi
#     que una version que no exista rompe el binario. Es un tripwire util.
# Cuando el snapshot avance hay que subir estos dos pines; el resto lo resuelve
# el snapshot solo.
apt-get install -y --no-install-recommends \
  gdb-multiarch=17.1-2ubuntu1 \
  hashcat \
  john \
  libffi8 \
  libgdbm6t64 \
  libpq5 \
  libreadline8t64 \
  libsqlite3-0 \
  libusb-1.0-0=2:1.0.29-2build1 \
  libxml2-16 \
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
