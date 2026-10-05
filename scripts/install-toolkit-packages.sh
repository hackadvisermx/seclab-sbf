#!/bin/sh
set -eu

snapshot="${SNAPSHOT_ID:?SNAPSHOT_ID is required}"
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates
sed -i "s|http://ports.ubuntu.com/ubuntu-ports/|https://snapshot.ubuntu.com/ubuntu/${snapshot}/|g" /etc/apt/sources.list.d/ubuntu.sources
sed -i '/^Snapshot:/d' /etc/apt/sources.list.d/ubuntu.sources
apt-get update
# nikto va aqui (2.1.5-3.1build1, de Ubuntu noble/resolute): es el escaner web
# clasico, menos preciso que nuclei pero cubre comprobaciones que ahi no estan.
# Trae sus propias dependencias de Perl, asi que no hace falta 'perl' a mano.
apt-get install -y --no-install-recommends \
  binutils \
  ca-certificates \
  crunch \
  curl \
  bind9-dnsutils \
  fd-find \
  file \
  gdb \
  git \
  hexedit \
  iproute2 \
  iputils-ping \
  jq \
  krb5-user \
  ldap-utils \
  less \
  libimage-exiftool-perl \
  libpcap0.8t64 \
  nmap \
  nikto \
  openssh-client \
  openssh-server \
  openvpn \
  7zip \
  procps \
  proxychains4 \
  python3 \
  python3-ldap3 \
  python3-packaging \
  python3-pip \
  ripgrep \
  samba-common-bin \
  smbclient \
  socat \
  sqlmap \
  tmux \
  unzip \
  util-linux \
  wireguard-tools \
  zsh \
  zstd

case "$(dpkg --print-architecture)" in
  amd64)
    ttyd_asset=ttyd.x86_64
    ttyd_sha256=8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55
    zoxide_asset=zoxide-0.10.0-x86_64-unknown-linux-musl.tar.gz
    zoxide_sha256=2d93385b99f3e82cf2701609a1bffcad863fbeb75aa3fe7eb6be4d29be68b1ae
    dalfox_asset=dalfox-v3.2.1-linux-x86_64-musl.tar.gz
    dalfox_sha256=99d2bbe01a7c0ac6e455cba0363900c5aef2866bd08a2cd5f00b83d7b9671c20
    ferox_asset=x86_64-linux-feroxbuster.tar.gz
    ferox_sha256=7985c00e6803b0f25d5e9139f7472279f3f4d891429627a5cedc629e53992d80
    findomain_asset=findomain-linux.zip
    findomain_sha256=7a1b90aaf291868e0fb2d643cefa238caddb7aa932b2355f0e0ce8b47a4b5083
    x8_asset=x86_64-linux-x8.gz
    x8_sha256=b3e54da4c0cc62163a3485addea6671368ee69342ea5740e56d6d6112196bd0e
    x8_url="https://github.com/Sh1Yo/x8/releases/download/v4.3.0/${x8_asset}"
    ;;
  arm64)
    ttyd_asset=ttyd.aarch64
    ttyd_sha256=b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165
    zoxide_asset=zoxide-0.10.0-aarch64-unknown-linux-musl.tar.gz
    zoxide_sha256=f1f16c5d6298d63dee467eedea1cdcd8490e43e493bea43acd416dc9033ef641
    dalfox_asset=dalfox-v3.2.1-linux-aarch64-musl.tar.gz
    dalfox_sha256=e10f3f95e3033899c0912c1b9032d35f754caeeb002b0b8153e2958e54485694
    ferox_asset=aarch64-linux-feroxbuster.zip
    ferox_sha256=1e5244e1f52e55a647b65e0c76ae7afe0b9983c1fbea30ed7c67e477175eb381
    findomain_asset=findomain-aarch64.zip
    findomain_sha256=780056cba200722f49628bf89b5cd42f3927e694bd383af679d72cf96efc1621
    x8_asset=x8-1:v4.3.0.r10.gc78f246-1-aarch64.pkg.tar.zst
    x8_sha256=35f355231ac2420eca6aa466e8fdf9f71542bb81726b46930ea9885c29ef1b4c
    x8_url="https://mirror.cyberbits.eu/blackarch/blackarch/os/aarch64/${x8_asset}"
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

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/hahwul/dalfox/releases/download/v3.2.1/${dalfox_asset}" \
  --output /tmp/dalfox.tar.gz
printf '%s  %s\n' "$dalfox_sha256" /tmp/dalfox.tar.gz | sha256sum -c -
rm -rf /tmp/dalfox
mkdir /tmp/dalfox
tar -xzf /tmp/dalfox.tar.gz -C /tmp/dalfox
install -m 0555 "/tmp/dalfox/$(basename "$dalfox_asset" .tar.gz)/dalfox" /usr/bin/dalfox
rm -rf /tmp/dalfox /tmp/dalfox.tar.gz

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/epi052/feroxbuster/releases/download/v2.13.1/${ferox_asset}" \
  --output "/tmp/ferox.${ferox_asset##*.}"
printf '%s  %s\n' "$ferox_sha256" "/tmp/ferox.${ferox_asset##*.}" | sha256sum -c -
rm -rf /tmp/ferox
mkdir /tmp/ferox
case "$ferox_asset" in
  *.tar.gz) tar -xzf "/tmp/ferox.${ferox_asset##*.}" -C /tmp/ferox ;;
  *.zip) unzip -q -o "/tmp/ferox.${ferox_asset##*.}" -d /tmp/ferox ;;
esac
install -m 0555 /tmp/ferox/feroxbuster /usr/bin/feroxbuster
rm -rf /tmp/ferox "/tmp/ferox.${ferox_asset##*.}"

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://github.com/Findomain/Findomain/releases/download/10.0.1/${findomain_asset}" \
  --output /tmp/findomain.zip
printf '%s  %s\n' "$findomain_sha256" /tmp/findomain.zip | sha256sum -c -
rm -rf /tmp/findomain
mkdir -p /tmp/findomain
unzip -q -o /tmp/findomain.zip -d /tmp/findomain
install -m 0555 /tmp/findomain/findomain /usr/bin/findomain
rm -rf /tmp/findomain /tmp/findomain.zip

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "$x8_url" \
  --output "/tmp/x8_pkg.${x8_asset##*.}"
printf '%s  %s\n' "$x8_sha256" "/tmp/x8_pkg.${x8_asset##*.}" | sha256sum -c -
rm -rf /tmp/x8_dir
mkdir -p /tmp/x8_dir
case "$x8_asset" in
  *.gz)
    gzip -dc "/tmp/x8_pkg.${x8_asset##*.}" > /tmp/x8_dir/x8
    ;;
  *.zst)
    tar --zstd -xf "/tmp/x8_pkg.${x8_asset##*.}" -C /tmp/x8_dir usr/bin/x8
    mv /tmp/x8_dir/usr/bin/x8 /tmp/x8_dir/x8
    ;;
esac
install -m 0555 /tmp/x8_dir/x8 /usr/bin/x8
rm -rf /tmp/x8_dir "/tmp/x8_pkg.${x8_asset##*.}"

# pspy 1.2.1 NO esta aqui: no hay release con binario arm64, asi que se
# compila en su propio stage (pspy-builder) del Dockerfile de full, igual que
# naabu o bettercap. Aqui solo se instala el resultado.

# enum4linux-ng 1.3.10 NO se instala aqui. Necesita impacket, y en esta imagen
# impacket solo existe dentro del venv de NetExec en /opt/nxc, que el Dockerfile
# copia DESPUES de este script. ldap3 tambien esta solo ahi. Por eso el script se
# descarga aqui (verificandose por SHA256) pero se instala mas abajo, junto al
# bloque que ya valida las AD tools, con el shebang apuntando al venv.
E4LNG_COMMIT=f34e7bb3bc2bcd10267a7257fb3658154434ccf4
E4LNG_SHA256=a948a9d105594931b083ce864c4019ffe137f3b30cba6ddf0bec331da748147d
# Se descarga por COMMIT, no por tag: el tag podria moverse y el SHA256 lo
# delata, pero atar tambien la URL al commit hace que un tag reescrito no
# sirva ni para descargar el fichero equivocado en silencio.
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://raw.githubusercontent.com/cddmp/enum4linux-ng/${E4LNG_COMMIT}/enum4linux-ng.py" \
  --output /opt/enum4linux-ng.py
printf '%s  %s\n' "$E4LNG_SHA256" /opt/enum4linux-ng.py | sha256sum -c -

GEF_COMMIT=18404074f469c70480aae071fbb77b75a2ed8507
GEF_SHA256=04cdfe961f1e9151933d32cf6b548d9e6a76a1aef8b27c020c575b8d4264ed20
install -d -m 0755 /usr/local/share/seclab/gef
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "https://raw.githubusercontent.com/hugsy/gef/${GEF_COMMIT}/gef.py" \
  --output /usr/local/share/seclab/gef/gef.py
printf '%s  %s\n' "$GEF_SHA256" /usr/local/share/seclab/gef/gef.py | sha256sum -c -
chmod 0555 /usr/local/share/seclab/gef/gef.py
install -d -m 0755 /etc/gdb
printf 'source /usr/local/share/seclab/gef/gef.py\n' > /etc/gdb/gdbinit
chmod 0444 /etc/gdb/gdbinit

# Staging de payloads de post-explotacion (offline, inmutable)
# linpeas.sh, winPEAS.bat, winPEASany.exe, socat estatico (amd64/arm64) y nc.exe (x86/x64)
install -d -m 0755 /usr/local/share/seclab/payloads/post-exploit

PEASS_RELEASE="20261003-ea9b2e92"
PEASS_BASE="https://github.com/peass-ng/PEASS-ng/releases/download/${PEASS_RELEASE}"

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${PEASS_BASE}/linpeas.sh" \
  --output /usr/local/share/seclab/payloads/post-exploit/linpeas.sh
printf '%s  %s\n' '795e315c42c58e27841e4ee2798a73a9309694f0454b34707299bb090e04b98d' /usr/local/share/seclab/payloads/post-exploit/linpeas.sh | sha256sum -c -

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${PEASS_BASE}/winPEAS.bat" \
  --output /usr/local/share/seclab/payloads/post-exploit/winPEAS.bat
printf '%s  %s\n' '11e4ea92ce2465f3d30c5a56fd4aeba2aecaf4d1c2670ac42bd61c4db2becf87' /usr/local/share/seclab/payloads/post-exploit/winPEAS.bat | sha256sum -c -

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${PEASS_BASE}/winPEASany.exe" \
  --output /usr/local/share/seclab/payloads/post-exploit/winPEASany.exe
printf '%s  %s\n' 'af0154c95d2897e78450d93a05479efca8b315b51e82ad70cd1dc4f94a5ecff5' /usr/local/share/seclab/payloads/post-exploit/winPEASany.exe | sha256sum -c -

SOCAT_STATIC_BASE="https://github.com/ernw/static-toolbox/releases/download/socat-v1.7.4.4"
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${SOCAT_STATIC_BASE}/socat-1.7.4.4-x86_64" \
  --output /usr/local/share/seclab/payloads/post-exploit/socat_linux_amd64
printf '%s  %s\n' '19fd284b8d48feff2a15cc37bd9ba070223da575e4e84623aea4b88f6efeb597' /usr/local/share/seclab/payloads/post-exploit/socat_linux_amd64 | sha256sum -c -

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${SOCAT_STATIC_BASE}/socat-1.7.4.4-aarch64" \
  --output /usr/local/share/seclab/payloads/post-exploit/socat_linux_arm64
printf '%s  %s\n' '758f023d9a27ae3b7f5f633ef41bed65b812af0dd86b4afede37925e405ddc3d' /usr/local/share/seclab/payloads/post-exploit/socat_linux_arm64 | sha256sum -c -

case "$(dpkg --print-architecture)" in
  amd64) ln -sf socat_linux_amd64 /usr/local/share/seclab/payloads/post-exploit/socat ;;
  arm64) ln -sf socat_linux_arm64 /usr/local/share/seclab/payloads/post-exploit/socat ;;
esac

NC_COMMIT="fa87aa42c460d34966efb998a1788efca6db11a7"
NC_BASE="https://raw.githubusercontent.com/int0x33/nc.exe/${NC_COMMIT}"
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${NC_BASE}/nc.exe" \
  --output /usr/local/share/seclab/payloads/post-exploit/nc.exe
printf '%s  %s\n' 'e8fbec25db4f9d95b5e8f41cca51a4b32be8674a4dea7a45b6f7aeb22dbc38db' /usr/local/share/seclab/payloads/post-exploit/nc.exe | sha256sum -c -

curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${NC_BASE}/nc64.exe" \
  --output /usr/local/share/seclab/payloads/post-exploit/nc64.exe
printf '%s  %s\n' '3e59379f585ebf0becb6b4e06d0fbbf806de28a4bb256e837b4555f1b4245571' /usr/local/share/seclab/payloads/post-exploit/nc64.exe | sha256sum -c -

chmod 0555 /usr/local/share/seclab/payloads/post-exploit/*

git clone --depth 1 --branch v10.4.9 https://github.com/projectdiscovery/nuclei-templates.git /tmp/nuclei-templates
test "$(git -C /tmp/nuclei-templates rev-parse HEAD)" = "893122ffce8ebf8e264f15d2cd3960cb1dd36d6c"
rm -rf /tmp/nuclei-templates/.git
install -d -m 0755 /usr/local/share/seclab/nuclei-templates
cp -r /tmp/nuclei-templates/. /usr/local/share/seclab/nuclei-templates/
rm -rf /tmp/nuclei-templates

SECLAB_SECLISTS_COMMIT=eccfbd405af82194e125a450a0076dbe4252d6f9
SECLAB_SECLISTS_BASE="https://raw.githubusercontent.com/danielmiessler/SecLists/${SECLAB_SECLISTS_COMMIT}"
install -d -m 0755 /usr/local/share/seclab/wordlists
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${SECLAB_SECLISTS_BASE}/Discovery/Web-Content/common.txt" \
  --output /usr/local/share/seclab/wordlists/common.txt
printf '%s  %s\n' '47fb86ca6fb3f97e5491161581900d6d99851fb16764eacddf16aa85617c956a' /usr/local/share/seclab/wordlists/common.txt | sha256sum -c -
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${SECLAB_SECLISTS_BASE}/Discovery/Web-Content/raft-small-words.txt" \
  --output /usr/local/share/seclab/wordlists/raft-small-words.txt
printf '%s  %s\n' '1aadf7dafde5ca68f5e5160c9206f7be6f6fc701775cdea30ba01bbb6d8db8ad' /usr/local/share/seclab/wordlists/raft-small-words.txt | sha256sum -c -
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${SECLAB_SECLISTS_BASE}/Discovery/DNS/subdomains-top1million-5000.txt" \
  --output /usr/local/share/seclab/wordlists/subdomains-top5000.txt
printf '%s  %s\n' 'e331367c140298cb179114fdeefa78f58f696219f0dec017a28bb79487cfcf19' /usr/local/share/seclab/wordlists/subdomains-top5000.txt | sha256sum -c -
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  "${SECLAB_SECLISTS_BASE}/Discovery/Web-Content/DirBuster-2007_directory-list-2.3-small.txt" \
  --output /usr/local/share/seclab/wordlists/directory-list-2.3-small.txt
printf '%s  %s\n' '77f7aba81570b24c30965bfc4652cf6c99ee4e5ed38f1eab96f2e102981a6d90' /usr/local/share/seclab/wordlists/directory-list-2.3-small.txt | sha256sum -c -
chmod 0644 /usr/local/share/seclab/wordlists/*


case "$(dpkg --print-architecture)" in
  amd64) pwntools_requirements=/tmp/pwntools-requirements-x86_64.txt ;;
  arm64) pwntools_requirements=/tmp/pwntools-requirements-aarch64.txt ;;
esac
python3 -m pip install --no-cache-dir --break-system-packages --require-hashes \
  -r "$pwntools_requirements"
rm -f /tmp/pwntools-requirements-aarch64.txt /tmp/pwntools-requirements-x86_64.txt
python3 -c "from pwn import p32; assert p32(1) == b'\x01\x00\x00\x00'"
# Con el python DEL SISTEMA, no el que sale en el PATH. El PATH de la imagen
# antepone el venv de NetExec, y ahi no esta pwntools: vive en
# /usr/lib/python3/dist-packages. El import de arriba lo hacia el python del
# venv y por eso hay que repetirlo aqui con /usr/bin/python3.
#
# Se comprueba `p32`, que es lo minimo, pero tambien que unicorn carga, que es
# donde se rompe si el pin del wheel no casa con la version de Python.
/usr/bin/python3 -c "from pwn import p32, ELF; assert p32(1) == b'\x01\x00\x00\x00'"
/usr/bin/python3 -c "import unicorn, packaging; print('pwntools+unicorn+packaging ok en', unicorn.__version__)"

# El objetivo de esto es que el pip y el setuptools de la imagen no sirvan
# para instalar nada en runtime: sin pip, `tester` no puede meter paquetes ni
# aunque tuviera permiso de escritura.
#
# python3-setuptools se quita de la lista a proposito. En Ubuntu 24.04 venia
# preinstalado en la imagen y dpkg lo tenia registrado, asi que se podia purgar.
# En 26.04 ya no viene, y lo que se desinstala al final es el que instalo pip en
# /usr/local, que dpkg nunca registro: al pedir el purge de python3-setuptools
# apt falla con "uninstall-no-record-file" y el build entero muere en este paso.
# Por eso se purgan solo los paquetes que SI registro dpkg.
apt-get purge -y python3-pip python3-wheel
apt-get autoremove -y --purge

# Comprobacion de que ARRANCAN, no solo de que existen. Sin esto el build da
# verde con una tool rota, que ya paso una vez con las de impacket: el binario
# estaba y no hacia nada.
#
# pspy y enum4linux-ng NO se comprueban aqui: los dos los instala el Dockerfile
# DESPUES de este script (el binario de pspy con un COPY, y enum4linux-ng con
# el venv de NetExec, que no existe todavia). Se validan mas abajo, donde ya
# estan los dos en su sitio.
nikto -Version >/dev/null 2>&1 || { printf 'nikto no arranca\n' >&2; exit 1; }
printf '%s\n' 'nikto ok'

rm -f /etc/ssh/ssh_host_*
apt-get clean
rm -rf /var/lib/apt/lists/*
