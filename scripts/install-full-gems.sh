#!/bin/sh
# Gems de Ruby que no forman parte de Metasploit, para la imagen full.
#
# Cada uno va en su propio GEM_HOME: comparten gemas con el bundle de
# Metasploit (nokogiri, y los que traiga), pero al vivir aparte no tocan ese
# bundle, que esta bloqueado a proposito.
#
# Se ejecuta dentro de msf-builder, que es quien tiene el Ruby definitivo
# (3.3.8) y las herramientas de compilacion. Corre ahi y no en la imagen final
# por dos razones: la imagen final no lleva make, y las extensiones nativas de
# wpscan (yajl-ruby, ffi) deben compilarse contra ese mismo Ruby.
#
# Solo las versiones de los gems directos van fijadas. Sus dependencias
# transitivas las resuelve rubygems contra el indice del momento, que es la
# misma limitacion que ya tiene el resto del stack de Ruby de la imagen.
set -eu

export DEBIAN_FRONTEND=noninteractive
out_dir="${GEMS_OUT_DIR:?GEMS_OUT_DIR is required}"
gem_bin=/opt/ruby/bin/gem

[ -x "$gem_bin" ] || { printf 'falta %s\n' "$gem_bin" >&2; exit 2; }

install_gem() {
  nombre="$1"
  version="$2"
  gem_home="$out_dir/$nombre-gems"
  printf '== %s %s en %s\n' "$nombre" "$version" "$gem_home"
  mkdir -p "$gem_home"
  GEM_HOME="$gem_home" "$gem_bin" install --no-document "$nombre" -v "$version" --conservative
}

# El objetivo de la verificacion es detectar aqui una dependencia nativa que no
# se haya podido resolver, no comprobar el numero de version. Cada gem se
# comprueba con lo que tiene sentido en el suyo.
verify_wpscan() {
  GEM_HOME="$1" "$1/bin/wpscan" --version
}

# zsteg imprime "version unknown" en --version y sale con 1, asi que no sirve
# como comprobacion. Se verifica de dos formas: que la libreria cargue, y que un
# extractor real se ejecute sobre un PNG valido.
#
# El segundo caso importa por un bug de zsteg 0.2.14: el atajo "zsteg -e lsb"
# revienta con NoMethodError, porque decode_param_string no rellena :channels
# si no se indica ningun canal. Hay que pasar siempre los canales, por ejemplo
# "zsteg -e b1,lsb,rgba". Se comprueba esa forma, no la rota.
verify_zsteg() {
  GEM_HOME="$1" /opt/ruby/bin/ruby -e 'require "zsteg"; puts "zsteg cargada"'
  ls -1 "$1/bin"
  tmp_png=$(mktemp /tmp/zsteg-check-XXXXXX.png)
  # PNG 8x8 RGB valido, 166 bytes, generado para esta comprobacion.
  printf '%s' \
    'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAbUlEQVR42hXNQRUAUQhCUSMYgQhG' \
    'eBGIQAT6r+aPSy4HZ4YdNNzA4CFDh5llFy23sHjJ0n0gVkicQFhEVA+OPXTcweEjR+/BP/CqL/zP' \
    'EOh7N2aNzPmPbWLqB2GDwuUvOyQ0D8oWles/4ZLS8gHjmiwB7v9A2wAAAABJRU5ErkJggg==' \
    | base64 -d > "$tmp_png"
  GEM_HOME="$1" "$1/bin/zsteg" -e b1,lsb,rgba "$tmp_png" >/dev/null
  rm -f "$tmp_png"
}

# wpscan, escaner de WordPress. yajl-ruby y ffi son extensiones nativas, asi
# que --version tambien prueba que compilaron.
install_gem wpscan 4.1.0
verify_wpscan "$out_dir/wpscan-gems"

# zsteg, extraccion de datos esteganograficos. Ruby puro (iostruct, prime,
# zpng), pero se compila aqui para que siga funcionando si alguna vez una
# dependencia suya trae extension.
install_gem zsteg 0.2.14
verify_zsteg "$out_dir/zsteg-gems"

# Los shebangs de los binstubs apuntan a /opt/ruby/bin/ruby, que existe con esa
# misma ruta en la imagen final, asi que no hay que retocar nada al copiarlos.
printf 'gems ok en %s\n' "$out_dir"
