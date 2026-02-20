# Cubie NAS (ARM64)

Web-based NAS management server for Cubie A5E, optimized for lightweight deployment on Debian/Ubuntu ARM64.

## Project Structure

```text
cubie-nas/
  app/
    config.py
    db.py
    deps.py
    main.py
    models.py
    schemas.py
    security.py
    routers/
      auth.py
      bonus.py
      files.py
      monitoring.py
      services.py
      storage.py
      system.py
      users.py
    services/
      file_ops.py
      monitor.py
      service_ctl.py
      ssl.py
      storage.py
      system_cmd.py
      user_ctl.py
  plugins/
    example_plugin.py
  scripts/
    generate-self-signed.sh
    install.sh
  static/
    css/style.css
    js/router.js
  templates/
    overview.html
    login.html
  systemd/
    cubie-nas.service
  .env.example
  requirements.txt
  README.md
```

## Install (ARM64 Debian/Ubuntu)

```bash
cd /home/radxa/nas102/cubie-nas
sudo bash scripts/install.sh
```

This script installs dependencies, creates virtualenv, generates TLS cert, installs `systemd` service, and starts the server.

## Safe Deploy (preserve runtime `.env` and `.venv`)

Use this for code updates to `/opt/cubie-nas` so runtime secrets and virtualenv are never deleted:

```bash
cd /home/radxa/nas102/cubie-nas
bash scripts/deploy-safe.sh
```

Dry-run preview (no changes):

```bash
bash scripts/deploy-safe.sh --dry-run
```

This script enforces rsync excludes for `.env`, `.venv/`, and `__pycache__/`, then restarts `cubie-nas` and verifies `systemctl is-active` is `active`.

Shortcut via Makefile:

```bash
make deploy-safe
```

Dry-run shortcut:

```bash
make deploy-safe-dry
```

## Manual Install (if needed)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip smartmontools util-linux exfatprogs ntfs-3g xfsprogs dosfstools samba nfs-kernel-server openssh-server vsftpd openssl ufw rsync
sudo mkdir -p /opt/cubie-nas /var/lib/cubie-nas /etc/cubie-nas /srv/nas
sudo cp -r /home/radxa/nas102/cubie-nas/* /opt/cubie-nas/
cd /opt/cubie-nas
sudo cp .env.example .env
sudo sed -i "s|change-me-to-long-random-string|$(openssl rand -hex 32)|" .env
sudo python3 -m venv .venv
sudo .venv/bin/pip install --upgrade pip
sudo .venv/bin/pip install -r requirements.txt
sudo bash scripts/generate-self-signed.sh /etc/cubie-nas/cert.pem /etc/cubie-nas/key.pem cubie-nas.local
sudo install -m 644 systemd/cubie-nas.service /etc/systemd/system/cubie-nas.service
sudo systemctl daemon-reload
sudo systemctl enable --now cubie-nas
```

## Access

- URL: `https://<cubie-ip>:8443`
- Default app admin: `admin`
- Default app password: `admin12345`
- Change it immediately in User Management.

## Systemd Controls

```bash
sudo systemctl status cubie-nas
sudo systemctl restart cubie-nas
sudo journalctl -u cubie-nas -f
```

## Firewall Commands

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 445/tcp
sudo ufw allow 2049/tcp
sudo ufw allow 8443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

## Features Included

- JWT auth login/logout with secure cookies
- Role-based access (`admin`, `user`)
- Brute-force lockout protection
- CSRF protection (double-submit token)
- HTTPS self-signed certificate generation
- Storage discovery + SMART + mount/unmount + format
- File manager: browse, sort, upload, download, rename, delete, mkdir, drag/drop upload
- Monitoring via WebSocket: CPU/RAM/temp/network speed/disk I/O/uptime
- Service controls: Samba, NFS, SSH, FTP (vsftpd)
- User management: app users + Linux users/passwords + folder ownership/mode + active sessions
- Bonus: Docker container list/start/stop, rsync backup run endpoint, plugin directory scaffold

## Performance Tuning Guide

- Keep `uvicorn` single-process (default) to reduce RAM.
- Use SQLite on SSD/fast USB storage for lower CPU overhead.
- Keep logs bounded: `journalctl --vacuum-time=7d`.
- Disable unused services:
  - `sudo systemctl disable --now vsftpd` (if FTP not needed)
  - `sudo systemctl disable --now nfs-kernel-server` (if NFS not needed)
- Keep swap enabled but small (`1-2GB`) to prevent OOM spikes.
- On large file transfers, prefer wired LAN and ext4/xfs for lower CPU overhead.

## Security Hardening Checklist

- Change default admin password immediately.
- Rotate `JWT_SECRET` in `/opt/cubie-nas/.env`.
- Replace self-signed cert with trusted LAN PKI cert if available.
- Restrict dashboard access to trusted subnets (router firewall or reverse proxy ACL).
- Disable unused protocols (Samba/NFS/FTP/SSH) through dashboard or systemctl.
- Enforce key-based SSH auth and disable password SSH login.
- Keep OS packages updated: `sudo apt update && sudo apt upgrade`.
- Backup `/opt/cubie-nas/.env` and database securely.
- Review `journalctl -u cubie-nas` and auth failures regularly.

## Notes

- Storage formatting/mount/system service operations require root service execution.
- App runs with `MemoryMax=300M` in `systemd/cubie-nas.service`.
- Snapshot support depends on filesystem (btrfs/zfs) and is not enabled by default.

## Knowledge Base (KB)

This repository includes a structured knowledge base under `/kb` that serves as long-term memory for debugging, fixes, and operational knowledge.

### Purpose

- Prevent repeated mistakes by recording every validated fix.
- Provide a searchable reference for common issues across Linux, storage, networking, SMB, USB, services, and more.
- Act as a RAG (Retrieval-Augmented Generation) store for AI coding assistants (Copilot, Codex, Claude).

### Structure

```
kb/
  INDEX.md          # Master index of all entries
  TEMPLATE.md       # Entry template (copy for new entries)
  CONTRIBUTING.md   # Quality rules and contribution guide
  linux/            # OS-level: systemd, packages, boot, logs
  smb/              # Samba config, shares, testparm
  usb/              # USB detection, hotplug, mount, power
  kernel/           # Kernel panics, modules, dmesg, drivers
  uboot/            # U-Boot config, boot sequence, serial
  networking/       # IP config, DNS, firewall, interfaces
  storage/          # Disks, partitions, fstab, SMART, mount
  permissions/      # Ownership, ACLs, chmod, NAS user mapping
  services/         # systemd units, cubie-nas service lifecycle
  docker/           # Container lifecycle, images, volumes
  git/              # Git workflows, deploy sync
  troubleshooting/  # Cross-cutting multi-category issues
  opentap/          # OpenTAP integration, test automation
  tools/            # CLI utilities, scripts, dev tooling
```

### How to Use

1. **Before debugging:** Search `/kb/INDEX.md` or the relevant category folder.
2. **After solving an issue:** Create a KB entry using `kb/TEMPLATE.md` and add it to `kb/INDEX.md`.
3. **Quality rules:** No raw logs, no speculation, only validated final fixes. See `kb/CONTRIBUTING.md`.

