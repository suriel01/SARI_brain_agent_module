#!/usr/bin/env bash
# Creates a local CA and a server certificate for the Mosquitto TLS listener (port 8883).
#
# Usage:
#   scripts/gen-mqtt-certs.sh [--out DIR] [--days N] [--force] <broker-host-or-ip> [more names/IPs...]
#
# Every name/IP given becomes a subjectAltName of the server certificate; nodes must connect
# using one of them. Output (default mosquitto/certs/): ca.crt, ca.key, server.crt, server.key.
# Copy only ca.crt to the vision nodes. Keys never leave this machine and are gitignored.
# Then enable the listener: mv mosquitto/config/conf.d/tls.conf.example mosquitto/config/conf.d/tls.conf
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/mosquitto/certs"
DAYS=825
FORCE=0
NAMES=()

usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --days) DAYS="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) NAMES+=("$1"); shift ;;
  esac
done

if [[ ${#NAMES[@]} -eq 0 ]]; then
  echo "error: give at least one broker hostname or IP" >&2
  usage >&2
  exit 2
fi

mkdir -p "$OUT"
if [[ ! -w "$OUT" ]]; then
  echo "error: $OUT is not writable (the broker container chowns /mosquitto to uid 1883); run with sudo or fix ownership" >&2
  exit 1
fi
if [[ -e "$OUT/server.key" && $FORCE -eq 0 ]]; then
  echo "error: $OUT/server.key exists; use --force to replace the certificates" >&2
  exit 1
fi

SAN=""
for n in "${NAMES[@]}"; do
  if [[ "$n" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SAN+="IP:$n,"
  else
    SAN+="DNS:$n,"
  fi
done
SAN="${SAN%,}"

umask 077
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

openssl req -x509 -newkey rsa:4096 -sha256 -nodes -days "$DAYS" \
  -keyout "$OUT/ca.key" -out "$OUT/ca.crt" -subj "/CN=SARI MQTT local CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null

openssl req -newkey rsa:2048 -sha256 -nodes \
  -keyout "$OUT/server.key" -out "$TMP/server.csr" -subj "/CN=${NAMES[0]}" 2>/dev/null

cat > "$TMP/ext.cnf" <<EOF
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$SAN
EOF

openssl x509 -req -in "$TMP/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/server.crt" -days "$DAYS" -sha256 -extfile "$TMP/ext.cnf" 2>/dev/null
rm -f "$OUT/ca.srl"

# The broker runs as uid 1883 inside the container and must read server.key.
chmod 600 "$OUT/ca.key" "$OUT/server.key"
chmod 644 "$OUT/ca.crt" "$OUT/server.crt"

echo "certificates written to $OUT (SAN: $SAN)"
echo "next: mv mosquitto/config/conf.d/tls.conf.example mosquitto/config/conf.d/tls.conf"
echo "      then restart sari-mqtt; its entrypoint chowns /mosquitto (including certs) to uid 1883"
