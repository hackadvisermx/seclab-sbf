#!/bin/sh
set -eu

VPN_MODE="${VPN_MODE:-inside}"
VPN_DIR="${VPN_DIR:-/vpn}"
VPN_STATE_DIR="${VPN_STATE_DIR:-/var/lib/seclab/vpn}"
VPN_CREDENTIALS_FILE="${VPN_CREDENTIALS_FILE:-/run/secrets/lab.env}"
VPNTRY_CONFIG="${VPNTRY_CONFIG:-${VPN_DIR}/tryhackme.ovpn}"
VPNHTB_CONFIG="${VPNHTB_CONFIG:-${VPN_DIR}/hackthebox.ovpn}"
VPNCLI_CONFIG="${VPNCLI_CONFIG:-${VPN_DIR}/client.ovpn}"
TUN_INTERFACE="${VPN_TUN_INTERFACE:-tun0}"
active_file="${VPN_STATE_DIR}/active"
pid_file="${VPN_STATE_DIR}/openvpn.pid"
log_file="${VPN_STATE_DIR}/openvpn.log"
lock_dir="${VPN_STATE_DIR}/lock"

usage() {
  printf '%s\n' 'Uso: vpn-manager <list|validate|connect|status|disconnect|switch|doctor> [perfil]'
}

profile_path() {
  case "$1" in
    tryhackme|try) printf '%s\n' "$VPNTRY_CONFIG" ;;
    hackthebox|htb) printf '%s\n' "$VPNHTB_CONFIG" ;;
    client|cli) printf '%s\n' "$VPNCLI_CONFIG" ;;
    *) return 1 ;;
  esac
}

profile_label() {
  case "$1" in
    tryhackme|try) printf '%s\n' 'tryhackme' ;;
    hackthebox|htb) printf '%s\n' 'hackthebox' ;;
    client|cli) printf '%s\n' 'client' ;;
    *) return 1 ;;
  esac
}

host_only_notice() {
  printf 'VPN_MODE=host: este modo no inicia una VPN; solo conserva la compatibilidad explicita del host.\n' >&2
  printf 'Perfil: %s\n' "$1" >&2
  return 78
}

# Credenciales opcionales por perfil, leidas del archivo de secretos.
# Nunca se imprimen ni se versionan.
credential_value() {
  [ -r "$VPN_CREDENTIALS_FILE" ] || return 0
  key="$1"
  awk -v wanted="$key" '
    $0 ~ "^" wanted "=" {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' "$VPN_CREDENTIALS_FILE"
}

profile_credential_key() {
  case "$1" in
    tryhackme|try) printf 'VPNTRY' ;;
    hackthebox|htb) printf 'VPNHTB' ;;
    client|cli) printf 'VPNCLI' ;;
    *) return 1 ;;
  esac
}

has_net_admin() {
  cap_eff="$(awk '/^CapEff:/ { print $2 }' /proc/self/status)"
  cap_eff_decimal="$(printf '%d' "0x${cap_eff}")"
  [ "$((cap_eff_decimal & 4096))" -ne 0 ]
}

require_inside_root() {
  profile="$1"
  if [ "$VPN_MODE" != inside ]; then
    host_only_notice "$profile"
  fi
  if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Se requiere root para VPN_MODE=inside; usa el servicio VPN opcional.' >&2
    return 77
  fi
  if [ ! -c /dev/net/tun ]; then
    printf '%s\n' '/dev/net/tun no esta disponible como dispositivo de caracteres; no se usara --privileged.' >&2
    return 78
  fi
  if [ ! -e "/sys/class/net/${TUN_INTERFACE}" ]; then
    printf 'La interfaz %s no esta preparada; inicia el servicio VPN.\n' "$TUN_INTERFACE" >&2
    return 78
  fi
  if ! has_net_admin; then
    printf '%s\n' 'Falta CAP_NET_ADMIN; no se modificara la tabla de rutas.' >&2
    return 78
  fi
}

route_token_blocked() {
  token="$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')"
  case "$token" in
    127.*|169.254.*|100.64.*|100.100.100.200*|168.63.129.16*|192.0.0.192*|172.17.*|172.18.*|172.19.*|172.2[0-9].*|172.3[01].*|::1*|FE80:*|FD7A:115C:A1E0:*|FD00:EC2:*)
      return 0
      ;;
  esac
  return 1
}

validate_profile() {
  profile="$1"
  path="$(profile_path "$profile")"
  if [ ! -f "$path" ] || [ ! -r "$path" ]; then
    printf 'perfil no disponible: %s\n' "$path" >&2
    return 66
  fi

  mkdir -p "$VPN_STATE_DIR"
  chmod 0700 "$VPN_STATE_DIR"
  sanitized="${VPN_STATE_DIR}/$(profile_label "$profile").sanitized.ovpn"
  temporary="${sanitized}.tmp.$$"
  : > "$temporary"
  chmod 0600 "$temporary"
  route_count=0
  needs_auth=0
  inline_auth=0

  while IFS= read -r line || [ -n "$line" ]; do
    skip_line=0
    line="$(printf '%s' "$line" | tr -d '\r')"
    compact="$(printf '%s' "$line" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"
    case "$compact" in
      '<AUTH-USER-PASS>')
        inline_auth=1
        ;;
      'AUTH-USER-PASS')
        needs_auth=1
        skip_line=1
        ;;
      REDIRECT-GATEWAY*)
        skip_line=1
        ;;
      DHCP-OPTIONDNS*|DHCP-OPTIONDOMAIN*|DHCP-OPTIONWINS*|DHCP-OPTIONNTP*|DHCP-OPTIONSEARCH*)
        skip_line=1
        ;;
      UP*|DOWN*|ROUTE-UP*|ROUTE-DOWN*|IPCHANGE*|IPROUTE*|CLIENT-CONNECT*|CLIENT-DISCONNECT*|SCRIPT-SECURITY*|PLUGIN*|MANAGEMENT*|SETENV*)
        printf '%s\n' 'directiva ejecutable o.global rechazada en el perfil.' >&2
        rm -f "$temporary"
        return 65
        ;;
      ROUTE0.0.0.0*|ROUTE::/0*|ROUTE0/0*|ROUTE-IPV6::/0*)
        printf '%s\n' 'ruta por defecto rechazada.' >&2
        rm -f "$temporary"
        return 65
        ;;
      ROUTEGATEWAY*)
        skip_line=1
        ;;
      ROUTE127.*|ROUTE169.254.*|ROUTE100.64.*)
        printf '%s\n' 'ruta hacia loopback, metadata o Tailscale rechazada.' >&2
        rm -f "$temporary"
        return 65
        ;;
      ROUTE-NOPULL*)
        skip_line=1
        ;;
      ROUTE-DELAY*|ROUTE-MTU*|ROUTE-TIMEOUT*)
        ;;
      DEV*)
        case "$compact" in
          DEVTUN|DEVTUN0|DEV-TYPETUN) ;;
          *)
            printf '%s\n' 'dispositivo TUN invalido en el perfil.' >&2
            rm -f "$temporary"
            return 65
            ;;
        esac
        ;;
      ROUTE*)
        for token in $line; do
          if route_token_blocked "$token"; then
            printf '%s\n' 'ruta hacia loopback, metadata, gateway Docker o Tailscale rechazada.' >&2
            rm -f "$temporary"
            return 65
          fi
        done
        route_count=$((route_count + 1))
        ;;
    esac
    if [ "$skip_line" -eq 0 ]; then
      printf '%s\n' "$line" >> "$temporary"
    fi
  done < "$path"

  if [ "$needs_auth" -eq 1 ] && [ "$inline_auth" -eq 0 ]; then
    prefix="$(profile_credential_key "$profile")"
    user_value="$(credential_value "${prefix}_USER")"
    pass_value="$(credential_value "${prefix}_PASSWORD")"
    if [ -z "$user_value" ] || [ -z "$pass_value" ]; then
      printf 'el perfil pide usuario y faltan %s_USER o %s_PASSWORD en el archivo de credenciales.\n' "$prefix" "$prefix" >&2
      printf 'definelas para que la conexion no se quede esperando entrada.\n' >&2
      rm -f "$temporary"
      return 65
    fi
    auth_file="${VPN_STATE_DIR}/$(profile_label "$profile").auth"
    umask 077
    printf '%s\n%s\n' "$user_value" "$pass_value" > "$auth_file"
    chmod 0600 "$auth_file"
    printf 'auth-user-pass %s\n' "$auth_file" >> "$temporary"
  fi

  if [ "$route_count" -gt 0 ]; then
    printf '%s\n' 'route-nopull' >> "$temporary"
  fi
  printf '%s\n' 'pull-filter ignore "redirect-gateway"' 'pull-filter ignore "route-gateway"' 'pull-filter ignore "dhcp-option"' "dev ${TUN_INTERFACE}" 'dev-type tun' 'persist-key' 'persist-tun' >> "$temporary"
  mv "$temporary" "$sanitized"
  printf '%s\n' "$sanitized"
}

list_profiles() {
  for profile in tryhackme hackthebox client; do
    path="$(profile_path "$profile")"
    if [ -f "$path" ] && [ -r "$path" ]; then
      printf '%-12s %s\n' "$profile" "$path"
    else
      printf '%-12s %s (no montado)\n' "$profile" "$path"
    fi
  done
}

active_name() {
  if [ -r "$active_file" ]; then
    IFS= read -r value < "$active_file" || true
    printf '%s\n' "$value"
  fi
}

status() {
  printf 'mode=%s\n' "$VPN_MODE"
  printf 'state=%s\n' "$VPN_STATE_DIR"
  active="$(active_name)"
  if [ -n "$active" ]; then
    pid=""
    if [ -s "$pid_file" ]; then
      IFS= read -r pid < "$pid_file" || true
    fi
    case "$pid" in
      ''|*[!0-9]*) pid="" ;;
    esac
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      printf 'active=%s\n' "$active"
      printf 'pid=%s running\n' "$pid"
    else
      printf 'active=%s stale\n' "$active"
      printf '%s\n' 'pid=missing'
    fi
  else
    printf '%s\n' 'active=none'
  fi
  if [ "$VPN_MODE" = inside ]; then
    if [ -c /dev/net/tun ]; then printf '%s\n' 'tun=present'; else printf '%s\n' 'tun=absent'; fi
    if [ -e "/sys/class/net/${TUN_INTERFACE}" ]; then printf 'tun_interface=%s present\n' "$TUN_INTERFACE"; else printf 'tun_interface=%s absent\n' "$TUN_INTERFACE"; fi
    if has_net_admin; then printf '%s\n' 'net_admin=present'; else printf '%s\n' 'net_admin=absent'; fi
  fi
}

acquire_lock() {
  mkdir -p "$VPN_STATE_DIR"
  if ! mkdir "$lock_dir" 2>/dev/null; then
    lock_pid=""
    if [ -s "$lock_dir/pid" ]; then
      IFS= read -r lock_pid < "$lock_dir/pid" || true
    fi
    case "$lock_pid" in
      ''|*[!0-9]*) lock_pid="" ;;
    esac
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
      printf '%s\n' 'ya existe una operacion VPN activa.' >&2
      return 75
    fi
    rm -rf "$lock_dir"
    if ! mkdir "$lock_dir" 2>/dev/null; then
      printf '%s\n' 'no se pudo recuperar el lock VPN.' >&2
      return 75
    fi
  fi
  printf '%s\n' "$$" > "$lock_dir/pid"
  trap 'rm -rf "$lock_dir" 2>/dev/null || true' EXIT INT TERM
}

disconnect() {
  if [ "$VPN_MODE" != inside ]; then
    host_only_notice 'cualquiera'
  fi
  if [ ! -s "$active_file" ]; then
    printf '%s\n' 'no hay VPN activa.'
    return 0
  fi
  acquire_lock
  profile="$(active_name)"
  if [ -s "$pid_file" ]; then
    IFS= read -r pid < "$pid_file" || true
    case "$pid" in
      ''|*[!0-9]*) printf '%s\n' 'PID de VPN invalido.' >&2; return 70 ;;
    esac
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
      attempt=0
      while kill -0 "$pid" 2>/dev/null && [ "$attempt" -lt 20 ]; do
        sleep 1
        attempt=$((attempt + 1))
      done
      if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null || true
      fi
    fi
  fi
  rm -f "$active_file" "$pid_file" "$log_file" "${VPN_STATE_DIR}"/*.sanitized.ovpn "${VPN_STATE_DIR}"/*.auth
  printf 'VPN desconectada: %s\n' "$profile"
}

connect() {
  profile="${1:-}"
  if [ -z "$profile" ]; then
    usage >&2
    return 64
  fi
  require_inside_root "$profile"
  canonical="$(profile_label "$profile")"
  path="$(profile_path "$canonical")"
  case "$path" in
    /vpn/*) ;;
    *)
      printf '%s\n' 'el perfil debe estar bajo /vpn en VPN_MODE=inside.' >&2
      return 65
      ;;
  esac
  acquire_lock
  if [ -s "$active_file" ]; then
    existing_pid=""
    if [ -s "$pid_file" ]; then
      IFS= read -r existing_pid < "$pid_file" || true
    fi
    case "$existing_pid" in
      ''|*[!0-9]*) existing_pid="" ;;
    esac
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
      printf '%s\n' 'ya existe una VPN activa; usa switch.' >&2
      return 75
    fi
    rm -f "$active_file" "$pid_file" "$log_file" "${VPN_STATE_DIR}"/*.sanitized.ovpn "${VPN_STATE_DIR}"/*.auth
  fi
  sanitized="$(validate_profile "$canonical")"
  if ! /usr/sbin/openvpn --config "$sanitized" --daemon --writepid "$pid_file" --log "$log_file" --verb 3; then
    printf '%s\n' 'OpenVPN no pudo iniciar.' >&2
    return 69
  fi
  sleep 1
  pid=""
  if [ -s "$pid_file" ]; then
    IFS= read -r pid < "$pid_file" || true
  fi
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    printf '%s\n' 'OpenVPN termino durante el arranque.' >&2
    rm -f "$pid_file" "$log_file" "$sanitized"
    return 69
  fi
  printf '%s\n' "$canonical" > "$active_file"
  printf 'VPN conectada: %s\n' "$canonical"
}

doctor() {
  status
  for profile in tryhackme hackthebox client; do
    if [ -f "$(profile_path "$profile")" ]; then
      if validate_profile "$profile" >/dev/null; then
        printf 'profile=%s valid\n' "$profile"
      else
        printf 'profile=%s invalid\n' "$profile"
      fi
    fi
  done
}

command="${1:-}"
case "$command" in
  list) list_profiles ;;
  validate) [ "$#" -eq 2 ] || { usage >&2; exit 64; }; validate_profile "$2" ;;
  connect) [ "$#" -eq 2 ] || { usage >&2; exit 64; }; connect "$2" ;;
  status) status ;;
  disconnect) disconnect ;;
  switch)
    [ "$#" -eq 2 ] || { usage >&2; exit 64; }
    if [ "$VPN_MODE" != inside ]; then
      host_only_notice "$2"
    fi
    disconnect
    connect "$2"
    ;;
  doctor) doctor ;;
  *) usage >&2; exit 64 ;;
esac
