#!/bin/sh
# wpscan (escáner de WordPress) para la imagen full.
#
# Se ejecuta dentro de msf-builder, que es quien tiene el Ruby definitivo
# (3.3.8) y las herramientas de compilacion. Corre aqui y no en la imagen final
# por dos razones: la imagen final no lleva make, y las extensiones nativas de
# wpscan (yajl-ruby, ffi) deben compilarse contra ese mismo Ruby.
#
# Se instala en un GEM_HOME propio: comparte nokogiri con Metasploit, pero al
# vivir aparte no toca el bundle bloqueado de msfconsole.
#
# Solo la version de wpscan va fijada. Sus dependencias transitivas las
# resuelve rubygems contra el indice del momento, que es la misma limitacion
# que ya tiene el resto del stack de Ruby de la imagen.
set -eu

export DEBIAN_FRONTEND=noninteractive
gem_home="${WPSCAN_GEM_HOME:?WPSCAN_GEM_HOME is required}"
gem_bin=/opt/ruby/bin/gem

[ -x "$gem_bin" ] || { printf 'falta %s\n' "$gem_bin" >&2; exit 2; }

mkdir -p "$gem_home"
GEM_HOME="$gem_home" "$gem_bin" install --no-document wpscan -v 4.1.0 --conservative

# --version falla si el binario no arranca, que es la unica forma de detectar
# aqui una dependencia nativa que no se haya podido compilar.
GEM_HOME="$gem_home" "$gem_home/bin/wpscan" --version

# El shebang del binstub apunta a /opt/ruby/bin/ruby, que existe con esa misma
# ruta en la imagen final, asi que no hay que retocar nada al copiarlo.
printf 'wpscan ok en %s\n' "$gem_home"
