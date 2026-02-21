# Cubie NAS

Turn your Cubie A5E (or any ARM64 Debian/Ubuntu board) into a full-featured network-attached storage appliance with a modern web interface — no cloud subscription required.

![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-ARM64_Debian-orange)
![Python](https://img.shields.io/badge/python-3.9%2B-green)

---

## What You Get

| Feature | Description |
|---------|-------------|
| **Dashboard** | Live system health (CPU, RAM, temperature, uptime), storage overview, network speeds, service status — all updating in real time via WebSocket |
| **File Manager** | Browse, upload (drag & drop), download, rename, delete files across SD, USB, and NVMe drives — with path-traversal protection |
| **SMB Sharing** | Create and manage Samba shares from the UI — pick a folder, set access (everyone or specific users), one-click add/remove |
| **User Management** | Create app users and Linux system users, change passwords, assign admin/user roles, delete accounts |
| **Storage** | Detect USB and NVMe drives, format (ext4/exfat), mount/unmount, one-click provision as SMB share with wipe/repartition option |
| **Services** | Start, stop, enable, disable Samba, SSH, NFS, and FTP from the UI |
| **Network** | View current IP/gateway/DNS, switch between DHCP and static, see ethernet/WiFi/Bluetooth/hotspot status |
| **Terminal** | Full browser-based terminal (xterm.js) — PTY over WebSocket, one session per user |
| **Log Viewer** | Live-streaming journal logs for all NAS services — color-coded, filterable, auto-scrolling |
| **Backup Status** | Syncthing integration card — shows sync status if installed, or a helpful prompt if not |
| **Docker** | List, start, and stop Docker containers (if Docker is installed) |
| **Security** | JWT auth with secure cookies, CSRF protection, brute-force lockout, rate limiting, security headers on every response, systemd sandboxing |

---

## Quick Start

### Requirements

- ARM64 board running Debian 11+ or Ubuntu 20.04+ (tested on Cubie A5E / Radxa)
- Root (sudo) access
- Internet connection for initial package install

### One-Command Install

```bash
git clone https://github.com/parasjaing7/cubie-nas.git
cd cubie-nas
sudo bash scripts/install.sh
```

This will:
1. Install all system packages (Samba, NFS, SSH, FTP, smartmontools, etc.)
2. Copy the app to `/opt/cubie-nas`
3. Generate a random JWT secret and `.env` config
4. Create a Python virtual environment and install dependencies
5. Generate a self-signed TLS certificate
6. Enable and start the `cubie-nas` systemd service

When it finishes, you'll see:
```
Installation completed.
Open: https://<your-device-ip>:8443
```

### First Login

1. Open `https://<your-device-ip>:8443` in your browser
2. Accept the self-signed certificate warning
3. Log in with: **admin** / **admin12345**
4. **Change the default password immediately** via Users page

---

## Updating

After pulling new code, deploy without losing your config or data:

```bash
cd /home/radxa/nas102/cubie-nas
git pull
bash scripts/deploy-safe.sh
```

This syncs code to `/opt/cubie-nas` while preserving `.env`, `.venv/`, and database, then restarts the service.

Preview what would change (dry run):
```bash
bash scripts/deploy-safe.sh --dry-run
```

Or use the Makefile shortcut:
```bash
make deploy-safe        # deploy + restart
make deploy-safe-dry    # preview only
```

---

## Managing the Service

```bash
sudo systemctl status cubie-nas     # check status
sudo systemctl restart cubie-nas    # restart
sudo systemctl stop cubie-nas       # stop
sudo journalctl -u cubie-nas -f     # live logs
```

---

## Firewall Setup

Recommended firewall rules (applied automatically via Settings > Firewall in the UI, or manually):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 445/tcp     # Samba
sudo ufw allow 2049/tcp    # NFS
sudo ufw allow 8443/tcp    # Cubie NAS web UI
sudo ufw --force enable
```

---

## Configuration

All runtime configuration lives in `/opt/cubie-nas/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_HOST` | `0.0.0.0` | Listen address |
| `APP_PORT` | `8443` | Listen port |
| `JWT_SECRET` | *(auto-generated)* | Secret for signing auth tokens — keep this safe |
| `JWT_EXPIRE_MINUTES` | `120` | Session duration |
| `NAS_ROOT` | `/srv/nas` | Root directory for file browsing |
| `DATABASE_URL` | `sqlite:////var/lib/cubie-nas/cubie_nas.db` | Database path |
| `TLS_CERT_FILE` | `/etc/cubie-nas/cert.pem` | TLS certificate path |
| `TLS_KEY_FILE` | `/etc/cubie-nas/key.pem` | TLS private key path |
| `CORS_ORIGINS` | *(empty)* | Comma-separated allowed origins (if using a reverse proxy) |
| `COMMAND_TIMEOUT_SEC` | `20` | Timeout for system commands (2–300) |
| `LOG_LEVEL` | `info` | Logging level |

---

## Security Checklist

After installation, harden your device:

- [ ] Change the default admin password (`admin12345`)
- [ ] Back up `/opt/cubie-nas/.env` — it contains your JWT secret
- [ ] Replace the self-signed TLS cert with a trusted one if available
- [ ] Restrict web UI access to your LAN (router firewall or reverse proxy)
- [ ] Disable unused services (FTP, NFS) if you only need Samba
- [ ] Enable key-based SSH and disable password login
- [ ] Keep the OS updated: `sudo apt update && sudo apt upgrade`

---

## Storage & Drives

Cubie NAS automatically detects connected drives:

| Drive Type | Detection | Icon |
|------------|-----------|------|
| SD Card | `mmcblk*` devices | SD card |
| USB | `TRAN=usb` in lsblk | USB drive |
| NVMe | `TRAN=nvme` or `/dev/nvme*` | NVMe SSD |

From the **NAS** page you can:
- Format a drive as ext4 or exfat
- Mount/unmount drives
- Wipe and repartition a drive
- Provision a drive as an SMB share in one step

---

## Performance

Measured on Cubie A5E (ARM64, 4GB RAM):

| Scenario | Peak RAM | Steady RAM |
|----------|----------|------------|
| Idle | 76 MB | 76 MB |
| Dashboard (live WebSocket + polling) | 94 MB | 93 MB |
| File manager (large folder) | 94 MB | 94 MB |
| Terminal session | 94 MB | 94 MB |
| Log streaming (all services) | 225 MB | 224 MB |

Memory is capped at **300 MB** by systemd (`MemoryMax=300M`). Typical usage stays under 100 MB.

### Performance Tips

- Keep uvicorn single-process (default) to minimize RAM
- Use ext4 or xfs on SSD/USB for lower CPU overhead
- Prune journal logs: `sudo journalctl --vacuum-time=7d`
- Disable unused services to free resources
- Keep a small swap partition (1–2 GB) as OOM safety net

---

## Architecture

```
Browser ──── HTTPS :8443 ──── FastAPI (uvicorn) ──── systemd cubie-nas.service
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
               Jinja2        REST API      WebSocket
              templates     (JSON)       (live data)
                    │             │             │
                    └─────┬───────┘             │
                          │                     │
                     SQLite DB           psutil / lsblk
                  /var/lib/cubie-nas      system commands
```

- **Backend:** Python 3.9+ / FastAPI / SQLAlchemy / SQLite
- **Frontend:** Jinja2 templates + vanilla ES6 JavaScript (no build step, no npm)
- **CSS:** Single `style.css` (15 KB), system-ui font stack, CSS custom properties for dark/light theming
- **CDN:** Only xterm.js 5.3.0 from jsdelivr (for terminal)
- **Auth:** JWT tokens in httpOnly cookies + CSRF double-submit
- **Systemd:** Sandboxed with `ProtectSystem=strict`, `PrivateTmp=true`, capped at 300 MB RAM

---

## Project Structure

```
cubie-nas/
├── app/                    # FastAPI application
│   ├── main.py             # App entry, middleware, page routes
│   ├── config.py           # Settings from .env
│   ├── db.py               # SQLAlchemy engine + session
│   ├── models.py           # User, LoginAttempt models
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── security.py         # JWT, bcrypt, CSRF helpers
│   ├── deps.py             # Auth dependencies (get_current_user, require_admin)
│   ├── routers/            # API route modules
│   │   ├── auth.py         # Login/logout + brute-force lockout
│   │   ├── files.py        # File CRUD + upload/download
│   │   ├── storage.py      # Drive detection, mount, format, provision
│   │   ├── sharing.py      # SMB share management (smb.conf)
│   │   ├── services.py     # Samba/SSH/NFS/FTP control
│   │   ├── users.py        # App + system user management
│   │   ├── network.py      # Network config (DHCP/static)
│   │   ├── monitoring.py   # WebSocket live stats + Syncthing
│   │   ├── system.py       # Terminal WS, logs WS, device info
│   │   └── bonus.py        # Docker, rsync backup, plugins
│   └── services/           # Business logic layer
│       ├── file_ops.py     # Path validation + file operations
│       ├── monitor.py      # CPU/RAM/temp/network sampling
│       ├── storage.py      # lsblk parsing + disk usage
│       ├── network.py      # NetworkManager / interfaces.d config
│       ├── service_ctl.py  # systemctl wrapper
│       ├── system_cmd.py   # Command runner with timeout + retry
│       ├── user_ctl.py     # useradd / chpasswd wrapper
│       ├── usb_share.py    # USB/NVMe provision workflow
│       ├── syncthing.py    # Syncthing status check
│       ├── ssl.py          # Self-signed cert generation
│       └── system_info.py  # Hardware/OS info
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Shared layout (sidebar, nav, helpers)
│   ├── login.html          # Login page
│   ├── dashboard.html      # Dashboard with live cards
│   ├── files.html          # File manager
│   ├── sharing.html        # SMB share management
│   ├── users.html          # User management
│   ├── settings.html       # Device settings
│   ├── storage_page.html   # Advanced storage view
│   ├── services_page.html  # Advanced service control
│   ├── network_page.html   # Network configuration
│   ├── nas_page.html       # USB/NVMe provisioning
│   ├── terminal.html       # Browser terminal (xterm.js)
│   └── logs.html           # Live log viewer
├── static/
│   ├── css/style.css       # All styles (dark/light theme)
│   └── js/router.js        # Client-side page logic
├── scripts/
│   ├── install.sh          # One-command installer
│   ├── deploy-safe.sh      # Safe update deploy
│   └── generate-self-signed.sh
├── systemd/
│   └── cubie-nas.service   # Systemd unit file
├── tests/                  # 47 automated tests
├── kb/                     # Knowledge base (debugging reference)
├── TASKS.md                # Development task tracker
├── AUDIT.md                # Security audit log
└── requirements.txt        # Python dependencies
```

---

## Running Tests

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest tests/ -v
```

Current: **47 tests, all passing.**

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't access `https://<ip>:8443` | Check firewall: `sudo ufw status`. Ensure port 8443 is allowed. |
| Certificate warning in browser | Expected with self-signed cert. Click "Advanced" → "Proceed". |
| Service won't start | Check logs: `sudo journalctl -u cubie-nas -n 50 --no-pager` |
| "Refusing to start with insecure default JWT secret" | The `.env` file is missing or has `JWT_SECRET=change-me`. Re-run install or set a real secret. |
| Drives not showing up | Plug in the drive, wait 5 seconds, refresh the page. Check `lsblk` in terminal. |
| Samba share not accessible | Ensure Samba is running (Services page). Check if the share folder exists and has correct permissions. |
| High memory usage | Normal during log streaming (~225 MB). Idle stays under 100 MB. Max is capped at 300 MB. |

---

## License

MIT

