#!/usr/bin/env bash
# init-env.sh — create or complete the SARI brain .env without ever printing secret values.
#
# Usage:
#   scripts/init-env.sh [--env-file PATH] [--replace-insecure] [--apply-mosquitto] [--apply-postgres]
#
#   --env-file PATH      target file (default: .env at the repo root)
#   --replace-insecure   regenerate variables that hold known leaked defaults (sari_password, 1234, ...)
#   --apply-mosquitto    add/update the MQTT_USER entry in mosquitto/config/passwd (via docker, keeps other users)
#   --apply-postgres     set the DB user's password to POSTGRES_PASSWORD in the running sari_postgres container
#
# Existing values are never overwritten unless --replace-insecure is given and the value is a known leaked default.
# A timestamped 0600 backup is written before any change.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
REPLACE_INSECURE=0
APPLY_MOSQUITTO=0
APPLY_POSTGRES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --replace-insecure) REPLACE_INSECURE=1; shift ;;
    --apply-mosquitto) APPLY_MOSQUITTO=1; shift ;;
    --apply-postgres) APPLY_POSTGRES=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

umask 077
INSECURE_VALUES=("SARI_SUPER_SECRET_KEY" "sari_secure_password_2026" "sari_password" "1234" "changeme")

rand_hex() { python3 -c "import secrets,sys; print(secrets.token_hex(int(sys.argv[1])))" "$1"; }
rand_urlsafe() { python3 -c "import secrets,sys; print(secrets.token_urlsafe(int(sys.argv[1])))" "$1"; }
rand_pin() { python3 -c "import secrets; p=''.join(secrets.choice('0123456789') for _ in range(6)); print(p if len(set(p))>2 else '0'+p[1:])"; }

get_value() { # prints the raw value of $1 from ENV_FILE (internal use only, never echoed to the user)
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- || true
}

is_insecure() {
  local v="$1"
  for bad in "${INSECURE_VALUES[@]}"; do [[ "$v" == "$bad" ]] && return 0; done
  return 1
}

set_value() { # replace or append NAME=VALUE atomically
  local name="$1" value="$2" tmp
  tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
  if grep -qE "^${name}=" "$ENV_FILE"; then
    NAME="$name" VALUE="$value" python3 - "$ENV_FILE" > "$tmp" <<'PY'
import os, sys
name, value = os.environ["NAME"], os.environ["VALUE"]
for line in open(sys.argv[1], encoding="utf-8"):
    sys.stdout.write(f"{name}={value}\n" if line.startswith(name + "=") else line)
PY
  else
    cat "$ENV_FILE" > "$tmp"
    [[ -s "$tmp" && "$(tail -c1 "$tmp")" != "" ]] && echo >> "$tmp"
    printf '%s=%s\n' "$name" "$value" >> "$tmp"
  fi
  chmod 600 "$tmp"
  mv "$tmp" "$ENV_FILE"
}

ADDED=(); REPLACED=(); KEPT=(); MANUAL=(); INSECURE_LEFT=()

ensure() { # ensure NAME has a value; GENERATOR is a command producing it (empty means manual)
  local name="$1" generator="${2:-}" current
  current="$(get_value "$name")"
  if [[ -n "$current" ]]; then
    if is_insecure "$current"; then
      if [[ $REPLACE_INSECURE -eq 1 && -n "$generator" ]]; then
        set_value "$name" "$($generator)"; REPLACED+=("$name")
      else
        INSECURE_LEFT+=("$name")
      fi
    else
      KEPT+=("$name")
    fi
    return
  fi
  if [[ -n "$generator" ]]; then
    set_value "$name" "$($generator)"; ADDED+=("$name")
  else
    grep -qE "^${name}=" "$ENV_FILE" || set_value "$name" ""
    MANUAL+=("$name")
  fi
}

gen_secret_key() { rand_hex 32; }
gen_password() { rand_urlsafe 24; }
gen_mqtt_user() { echo "sari_brain"; }
gen_node_keys() { echo "Jetson-PTZ_1:$(rand_urlsafe 32)"; }

# --- prepare file and backup ---
if [[ -f "$ENV_FILE" ]]; then
  BACKUP="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  cp -p "$ENV_FILE" "$BACKUP"; chmod 600 "$BACKUP"
else
  : > "$ENV_FILE"; BACKUP=""
fi
chmod 600 "$ENV_FILE"

ensure SARI_SECRET_KEY gen_secret_key
ensure SARI_SECURITY_PIN rand_pin
ensure SARI_ADMIN_PASSWORD gen_password
ensure SARI_SIREN_TOKEN gen_password
ensure SARI_NODE_KEYS gen_node_keys
ensure MQTT_USER gen_mqtt_user
ensure MQTT_PASSWORD gen_password
ensure POSTGRES_PASSWORD gen_password
ensure TELEGRAM_BOT_TOKEN
ensure TELEGRAM_ALLOWED_CHAT_IDS

# --- optional: sync broker credentials ---
if [[ $APPLY_MOSQUITTO -eq 1 ]]; then
  PASSWD_FILE="$ROOT/mosquitto/config/passwd"
  [[ -f "$PASSWD_FILE" ]] || { : > "$PASSWD_FILE"; chmod 600 "$PASSWD_FILE"; }
  docker run --rm -e U="$(get_value MQTT_USER)" -e P="$(get_value MQTT_PASSWORD)" \
    -v "$ROOT/mosquitto/config:/m" eclipse-mosquitto:2.0 \
    sh -c 'mosquitto_passwd -b /m/passwd "$U" "$P"' >/dev/null
  echo "mosquitto: entry for MQTT_USER written to mosquitto/config/passwd (restart sari-mqtt to load it)"
fi

# --- optional: rotate the database password in place ---
if [[ $APPLY_POSTGRES -eq 1 ]]; then
  if docker ps --format '{{.Names}}' | grep -qx sari_postgres; then
    PGPW="$(get_value POSTGRES_PASSWORD)" python3 -c 'import os; print("ALTER USER sari_user WITH PASSWORD \x27%s\x27;" % os.environ["PGPW"].replace("\x27","\x27\x27"))' \
      | docker exec -i sari_postgres psql -q -U sari_user -d sari_db >/dev/null
    echo "postgres: sari_user password updated to POSTGRES_PASSWORD"
  else
    echo "postgres: container sari_postgres is not running; start it and re-run with --apply-postgres" >&2
  fi
fi

if [[ -n "$BACKUP" ]] && cmp -s "$BACKUP" "$ENV_FILE"; then
  rm -f "$BACKUP"; BACKUP=""
fi

# --- report (names only, never values) ---
join() { local IFS=", "; echo "$*"; }
echo "env file: $ENV_FILE (mode 600)"
[[ -n "$BACKUP" ]] && echo "backup:   $BACKUP"
[[ ${#ADDED[@]} -gt 0 ]]         && echo "generated:        $(join "${ADDED[@]}")"
[[ ${#REPLACED[@]} -gt 0 ]]      && echo "replaced insecure: $(join "${REPLACED[@]}")"
[[ ${#KEPT[@]} -gt 0 ]]          && echo "kept as is:       $(join "${KEPT[@]}")"
[[ ${#MANUAL[@]} -gt 0 ]]        && echo "fill in by hand:  $(join "${MANUAL[@]}")"
[[ ${#INSECURE_LEFT[@]} -gt 0 ]] && echo "WARNING insecure default still set: $(join "${INSECURE_LEFT[@]}") (re-run with --replace-insecure)"

cat <<'EOF'

Next steps:
  - Read your PIN / admin password locally:   grep -E '^(SARI_SECURITY_PIN|SARI_ADMIN_PASSWORD)=' .env
  - Give each Jetson its key from SARI_NODE_KEYS as SARI_NODE_KEY in the Jetson's own env file.
  - If MQTT_* or POSTGRES_PASSWORD were generated or replaced, run with --apply-mosquitto / --apply-postgres.
EOF
