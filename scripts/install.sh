#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/cubie-nas"
DATA_DIR="/var/lib/cubie-nas"
CONF_DIR="/etc/cubie-nas"
SERVICE_FILE="/etc/systemd/system/cubie-nas.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install.sh"
  exit 1
fi

apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  smartmontools util-linux exfatprogs ntfs-3g xfsprogs dosfstools \
  samba nfs-kernel-server openssh-server vsftpd \
  openssl ufw rsync curl

mkdir -p "$APP_DIR" "$DATA_DIR" "$CONF_DIR" /srv/nas
cp -r . "$APP_DIR"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  sed -i "s|change-me-to-long-random-string|$(openssl rand -hex 32)|" "$APP_DIR/.env"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f /etc/cubie-nas/cert.pem || ! -f /etc/cubie-nas/key.pem ]]; then
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -subj "/CN=cubie-nas.local" \
    -keyout /etc/cubie-nas/key.pem \
    -out /etc/cubie-nas/cert.pem
  chmod 600 /etc/cubie-nas/key.pem
fi

install -m 644 "$APP_DIR/systemd/cubie-nas.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable cubie-nas
systemctl restart cubie-nas

echo "Installation completed."
echo "Open: https://$(hostname -I | awk '{print $1}'):8443"
