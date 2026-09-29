#!/bin/sh
# Envoltorio de zsteg.
#
# Mismo motivo que el de wpscan: zsteg va en su propio GEM_HOME para no tocar
# el bundle de Metasploit, asi que sin GEM_HOME explicito el binstub aborta con
# Gem::GemNotFoundException. Se exporta solo en este proceso para que
# Metasploit no lo vea.
set -eu

GEM_HOME=/opt/zsteg-gems
export GEM_HOME
exec /opt/zsteg-gems/bin/zsteg "$@"
