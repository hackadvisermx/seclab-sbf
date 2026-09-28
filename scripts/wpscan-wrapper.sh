#!/bin/sh
# Envoltorio de wpscan.
#
# wpscan se instalo en /opt/wpscan-gems para no tocar el bundle bloqueado de
# Metasploit, y por eso su GEM_HOME no forma parte del entorno de la imagen. Sin
# esto, el binstub no encuentra sus propias gemas y aborta con
# Gem::GemNotFoundException.
#
# El GEM_HOME se fija solo en este proceso a proposito: si se exportara en la
# imagen, Metasploit tambien lo veria y podria resolver gemas equivocadas.
set -eu

GEM_HOME=/opt/wpscan-gems
export GEM_HOME
exec /opt/wpscan-gems/bin/wpscan "$@"
