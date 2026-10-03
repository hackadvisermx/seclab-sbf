#!/bin/sh
# Valida que cada `uses: owner/repo@<sha>` de los workflows exista de verdad.
#
# Actionlint y el schema de Actions no comprueban que un SHA exista, asi que
# un SHA mal transcrito (un caracter de mas o de menos) solo falla en el
# runner, con "unable to find version", y despues de esperar todo el build.
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo_root"

if ! command -v gh >/dev/null 2>&1; then
	printf '%s\n' 'gh no disponible; se omite la verificacion de pines' >&2
	exit 0
fi

gh_ok=0
if GH_PROMPT_DISABLED=1 gh auth status >/dev/null 2>&1; then
	if curl -sS -I --connect-timeout 2 --max-time 3 https://api.github.com >/dev/null 2>&1; then
		gh_ok=1
	else
		printf '%s\n' 'api.github.com no accesible: se omite la verificacion online de pines' >&2
	fi
else
	printf '%s\n' 'gh sin sesion: se omite la verificacion de pines (no se puede consultar la API)' >&2
fi

failed=0
checked=0

# owner/repo@sha, sin tags ni ramas: solo commits inmutables.
pins=$(grep -rhoE 'uses:[[:space:]]*[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[A-Za-z0-9._-]+' .github/workflows \
	| sed -E 's/.*uses:[[:space:]]*//' | sort -u)

for pin in $pins; do
	owner_repo=${pin%@*}
	sha=${pin##*@}

	case "$sha" in
	[0-9a-f]*) ;;
	*)
		printf '%s\n' "pin no inmutable (debe ser un commit): $pin" >&2
		failed=$((failed + 1))
		continue
		;;
	esac

	checked=$((checked + 1))
	if [ "$gh_ok" -eq 0 ]; then
		continue
	fi
	if ! gh api "repos/$owner_repo/commits/$sha" >/dev/null 2>&1; then
		printf '%s\n' "SHA inexistente: $pin" >&2
		failed=$((failed + 1))
	fi
done

if [ "$checked" -eq 0 ]; then
	printf '%s\n' 'no se encontro ningun uses: con SHA en los workflows' >&2
	exit 1
fi

if [ "$failed" -ne 0 ]; then
	printf '%s\n' "verify-pins: $failed pin(es) invalidos de $checked" >&2
	exit 1
fi

printf '%s\n' "verify-pins: $checked pines de acciones validos"
