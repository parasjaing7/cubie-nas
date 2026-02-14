#!/usr/bin/env bash
set -euo pipefail

CERT_FILE=${1:-/etc/cubie-nas/cert.pem}
KEY_FILE=${2:-/etc/cubie-nas/key.pem}
CN=${3:-cubie-nas.local}

mkdir -p "$(dirname "$CERT_FILE")"
openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -subj "/CN=$CN" \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE"
chmod 600 "$KEY_FILE"

echo "Generated certificate: $CERT_FILE"
