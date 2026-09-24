#!/bin/sh
set -eu

: "${OH_MY_ZSH_COMMIT:?OH_MY_ZSH_COMMIT is required}"
: "${ZSH_AUTOSUGGESTIONS_COMMIT:?ZSH_AUTOSUGGESTIONS_COMMIT is required}"
: "${ZSH_SYNTAX_HIGHLIGHTING_COMMIT:?ZSH_SYNTAX_HIGHLIGHTING_COMMIT is required}"
: "${ZSH_COMPLETIONS_COMMIT:?ZSH_COMPLETIONS_COMMIT is required}"
: "${ZOXIDE_PLUGIN_COMMIT:?ZOXIDE_PLUGIN_COMMIT is required}"

install_root=/opt/seclab/oh-my-zsh
mkdir -p "$install_root/custom/plugins"

fetch_repository() {
  url="$1"
  commit="$2"
  destination="$3"
  rm -rf "$destination"
  git init -q "$destination"
  git -C "$destination" remote add origin "$url"
  for attempt in 1 2 3; do
    if git -C "$destination" fetch --depth 1 origin "$commit"; then
      break
    fi
    if [ "$attempt" -eq 3 ]; then
      return 1
    fi
    sleep $((attempt * 2))
  done
  git -C "$destination" checkout --detach "$commit"
  test "$(git -C "$destination" rev-parse HEAD)" = "$commit"
  rm -rf "$destination/.git"
}

fetch_repository https://github.com/ohmyzsh/ohmyzsh "$OH_MY_ZSH_COMMIT" "$install_root"
fetch_repository https://github.com/zsh-users/zsh-autosuggestions "$ZSH_AUTOSUGGESTIONS_COMMIT" "$install_root/custom/plugins/zsh-autosuggestions"
fetch_repository https://github.com/zsh-users/zsh-syntax-highlighting "$ZSH_SYNTAX_HIGHLIGHTING_COMMIT" "$install_root/custom/plugins/zsh-syntax-highlighting"
fetch_repository https://github.com/zsh-users/zsh-completions "$ZSH_COMPLETIONS_COMMIT" "$install_root/custom/plugins/zsh-completions"
fetch_repository https://github.com/ajeetdsouza/zoxide "$ZOXIDE_PLUGIN_COMMIT" "$install_root/custom/plugins/zoxide"
cp -R /usr/local/share/seclab/pentest-lab "$install_root/custom/plugins/pentest-lab"
chmod -R a+rX "$install_root"
