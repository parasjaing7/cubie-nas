# Cubie NAS — Task Sequence

**Status legend:** ⬜ Not started · 🔄 In progress · ✅ Completed · ❌ Blocked

---

## AUDIT PHASE (before any code changes)

### ⬜ AUDIT — Full Repo Audit
1. Read every file in: `app/`, `templates/`, `static/`, `scripts/`, `systemd/`, `requirements.txt`, `.env.example`
2. Map all existing routes, templates, and JS interactions
3. Identify: broken imports, unused routes, missing error handling, memory-heavy patterns, missing security headers
4. Document findings as `AUDIT.md` in the repo root before proceeding

---

## ARCHITECTURAL DECISIONS (apply throughout all tasks)

**Frontend approach:** Convert from full Jinja2 page-reload model to a hybrid SPA pattern:
- Keep Jinja2 for initial page shell only (auth, base layout, nav)
- All data loading, updates, and actions use vanilla JS `fetch()` against existing FastAPI JSON endpoints
- No React, no Vue, no npm build step — plain ES6 modules only
- Consumer-app feel (no full page reloads) without build complexity or RAM overhead

**Device detection:** Use `lsblk -J -o NAME,MOUNTPOINT,SIZE,TRAN,TYPE,LABEL,FSTYPE` as single source of truth for all storage device detection. Parse once server-side, cache result for max 10 seconds, expose via `GET /api/storage/devices`.

**CSS approach:** All styles in `static/css/style.css` — no Tailwind (requires build step), no Bootstrap (too heavy). Use CSS custom properties for theming. Target: style.css under 30KB.

**Fonts:** System-ui font stack only — `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`. No Google Fonts CDN calls.

**JS libraries (CDN with pinned versions only):**
- xterm.js 5.3.0 for terminal
- No other JS framework dependencies

**Security headers (add to all responses via FastAPI middleware):**
```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self' wss:
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

---

## PHASE 1 — Foundation & Security Hardening

### ⬜ TASK 1.1 — Verify RAM budget & systemd hardening
- [ ] Check `systemd/cubie-nas.service` has `MemoryMax=300M`
- [ ] Add `MemoryHigh=250M` as soft warning threshold
- [ ] Add `OOMPolicy=continue` so the service survives brief spikes
- [ ] Add `LimitNOFILE=4096` to cap file descriptors
- [ ] Confirm uvicorn is launched with `--workers 1` (single process, critical for RAM)
- [ ] Restart and confirm: `systemctl is-active cubie-nas` returns `active`
- [ ] Confirm after 2 mins idle: `systemctl show cubie-nas --property=MemoryCurrent` is under 250MB
- [ ] Document baseline RAM in `AUDIT.md`
- **Commit:** `feat(task1.1): systemd hardening and RAM budget verification`

### ⬜ TASK 1.2 — Add global security middleware
- [ ] In `app/main.py` add middleware that injects security headers on every response:
  - `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self' wss:`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] Add global rate limiting middleware using simple in-memory token bucket (no new heavy deps) — limit unauthenticated endpoints to 20 req/min per IP
- [ ] Restart and verify headers appear in browser DevTools Network tab
- **Commit:** `feat(task1.2): global security headers and rate limiting middleware`

### ⬜ TASK 1.3 — Create shared base template
- [ ] Create `templates/base.html` as master layout used by ALL other templates
- [ ] Base template includes: nav sidebar, top bar, content slot, toast notification container, global JS fetch helpers, WebSocket reconnect utility
- [ ] WebSocket reconnect utility: exponential backoff starting at 1s, max 30s, auto-reconnect on disconnect
- [ ] Nav sidebar structure:
  - Consumer section (always visible): Dashboard, Files, Sharing, Users, Settings
  - Advanced section (collapsed by default, toggle with chevron): Terminal ⚡, Logs ⚡, Storage ⚡, Services ⚡, Docker ⚡
- [ ] Global toast system: `window.toast(message, type)` where type = success/error/warning/info — non-blocking, auto-dismiss after 4s
- [ ] Global fetch wrapper: `window.api(path, options)` that handles auth errors (redirect to login on 401), shows toast on error, returns parsed JSON
- [ ] Update ALL existing templates to extend `base.html`
- [ ] Restart and verify all pages still load
- **Commit:** `feat(task1.3): shared base template with nav, toast, and fetch helpers`

### ⬜ TASK 1.4 — Add xterm.js Terminal Tab (Power User)
- [ ] Add route `GET /terminal` in `app/routers/system.py` serving `templates/terminal.html`
- [ ] Add WebSocket endpoint `/ws/terminal` in `app/routers/system.py`:
  - Authenticate via cookie/token before accepting — reject unauthenticated with 403
  - Enforce ONE active terminal session per authenticated user (module-level dict, clean up on disconnect)
  - Spawn bash PTY using `os.openpty()` + `asyncio.create_subprocess_exec` (stdlib only, no ptyprocess)
  - Forward stdin/stdout between WebSocket and PTY
  - On WebSocket close: kill PTY subprocess cleanly
- [ ] Template `templates/terminal.html`:
  - Load xterm.js 5.3.0 from CDN: `https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css` and `xterm.min.js`
  - Load xterm-addon-fit from same CDN for responsive sizing
  - Connect to `/ws/terminal` on page load
  - Show "Session limit reached" message if server rejects with 403
- [ ] Add "Terminal" to Advanced nav section
- [ ] Restart and verify terminal spawns, accepts input, cleans up on tab close
- **Commit:** `feat(task1.4): xterm.js terminal tab with PTY over WebSocket`

### ⬜ TASK 1.5 — Add Unified Log Viewer Tab (Power User)
- [ ] Add route `GET /logs` in `app/routers/system.py`
- [ ] Add WebSocket `/ws/logs` in `app/routers/system.py`:
  - Authenticate before accepting
  - Stream output of: `journalctl -f -u cubie-nas -u smbd -u nmbd -u nfs-kernel-server -u ssh -u vsftpd --output=short-iso --no-pager`
  - CRITICAL: never buffer more than 500 lines in memory — async line-by-line streaming, discard oldest when buffer full
  - Send each line as JSON: `{"ts": "...", "unit": "smbd", "level": "INFO", "msg": "..."}`
- [ ] Template `templates/logs.html`:
  - Auto-scrolling log window (pause scroll on hover, resume on click)
  - Color coding: ERROR/CRIT = red, WARN = yellow, INFO = white, DEBUG = gray
  - Client-side filter input: filters visible lines without re-fetching
  - Unit filter pills: click to show/hide specific service logs
  - "Clear display" button (clears client buffer only)
- [ ] Add "Logs" to Advanced nav section
- [ ] Restart and verify logs stream, filter works, memory stays stable after 5 mins
- **Commit:** `feat(task1.5): unified log viewer with WebSocket streaming`

---

## PHASE 2 — Consumer-Grade Dashboard

### ⬜ TASK 2.1 — Redesign Dashboard
- [ ] Redesign `templates/dashboard.html` as single-view overview card grid
- [ ] All data via `fetch()` + WebSocket, no full page reloads
- [ ] Layout: CSS Grid, 2 columns desktop, 1 column mobile (responsive media query)
- [ ] Design tokens in CSS:
  - `--color-bg: #0f1117`
  - `--color-surface: #1a1d2e`
  - `--color-accent: #4F8EF7`
  - `--color-success: #22c55e`
  - `--color-error: #ef4444`
  - `--color-warning: #f59e0b`
  - `--color-text: #e2e8f0`
  - `--color-muted: #64748b`
  - `--radius: 12px`
- [ ] **Card 1 — System Health** (live via WebSocket `/ws/monitor`)
  - CPU usage %: animated progress ring
  - RAM usage %: animated progress bar showing used/total
  - Temperature: color-coded (green <60°C, yellow <75°C, red ≥75°C)
  - Uptime: human-readable (e.g., "3 days 4 hrs")
- [ ] **Card 2 — Storage Overview** (fetch `GET /api/storage/devices`, refresh every 30s)
  - One row per detected device: SD Card icon, USB icon, or NVMe icon
  - Each row: device label, used/total, linear progress bar (red if >90% full)
  - Detection via lsblk — SD=mmcblk, USB=TRAN=usb, NVMe=TRAN=nvme
- [ ] **Card 3 — Network** (live via WebSocket `/ws/monitor`)
  - Current IP address
  - Upload speed (KB/s or MB/s auto-scaled)
  - Download speed (KB/s or MB/s auto-scaled)
- [ ] **Card 4 — Services** (fetch `GET /api/services/status`, refresh every 15s)
  - Samba, SSH, NFS, FTP — each row: service name, green/red status dot, toggle ON/OFF button
  - Toggle calls existing service control endpoint, toast on success/error
- [ ] **Card 5 — Active SMB Connections** (fetch `GET /api/sharing/connections`, refresh every 30s)
  - Parse `smbstatus -j` server-side, expose via new endpoint
  - Show: connected user, IP address, connected since
  - "No active connections" graceful state
- [ ] Remove all raw JSON debug output
- [ ] Restart and verify all cards load, live data updates, toggles work
- **Commit:** `feat(task2.1): consumer-grade dashboard with live cards`

---

## PHASE 3 — Consumer File Manager

### ⬜ TASK 3.1 — Device detection endpoint
- [ ] Add `GET /api/storage/devices` to `app/routers/storage.py`
- [ ] Run `lsblk -J -o NAME,MOUNTPOINT,SIZE,TRAN,TYPE,LABEL,FSTYPE` as subprocess
- [ ] Parse and return array:
  ```json
  [
    {"id": "mmcblk0", "label": "System SD", "type": "sd", "mountpoint": "/", "total_gb": 32, "used_gb": 8, "free_gb": 24},
    {"id": "sda", "label": "USB Drive", "type": "usb", "mountpoint": "/media/usb0", "total_gb": 64, "used_gb": 20, "free_gb": 44},
    {"id": "nvme0n1", "label": "NVMe Storage", "type": "nvme", "mountpoint": "/mnt/nvme", "total_gb": 256, "used_gb": 100, "free_gb": 156}
  ]
  ```
- [ ] Only return mounted devices (mountpoint not null/empty)
- [ ] Cache result for 10 seconds (simple time-based dict cache, no Redis)
- [ ] Validate all mountpoints are real paths
- **Commit:** `feat(task3.1): device detection endpoint via lsblk`

### ⬜ TASK 3.2 — File manager security layer
- [ ] In `app/services/file_ops.py` add `validate_path(requested_path, device_mountpoint)`:
  - Resolve real path using `os.path.realpath()`
  - Raise 403 if resolved path does not start with device mountpoint
  - Prevents all path traversal attacks
- [ ] Apply validation to ALL file operation endpoints (list, read, upload, rename, delete, mkdir, download)
- [ ] Add test in `tests/` verifying path traversal returns 403
- [ ] Restart and run test
- **Commit:** `feat(task3.2): file manager path traversal security layer`

### ⬜ TASK 3.3 — Redesign File Manager UI
- [ ] Completely replace `templates/files.html` and its JS
- [ ] **Landing view — Storage Devices:**
  - One card per device from `GET /api/storage/devices`
  - Card: large icon (SD/USB/NVMe inline SVG), device label, size bar, "Browse →" button
  - Undetected devices: greyed-out card with "Not connected"
- [ ] **Browse view:**
  - Breadcrumb bar showing path relative to device root (clickable crumbs)
  - Toggle Grid view / List view (preference in localStorage)
  - Grid: folders first (folder icon + name), then files (type icon + name + size)
  - List: columns — Name, Size, Date Modified, Type
  - File type icons (inline SVG): folder, image, video, audio, document, archive, code, unknown
  - Right-click context menu (long-press mobile): Rename, Delete, Download, Copy Path
  - Multi-select: checkbox in list, long-click in grid — bulk Delete and bulk Download (zip)
  - Upload zone: dashed drop zone, click or drag
  - New Folder button in toolbar
  - Back button to device landing
- [ ] All file operations use existing backend endpoints, toast on success/error
- [ ] Restart and verify: device cards, browsing, upload, rename, delete, path traversal test passes
- **Commit:** `feat(task3.3): consumer file manager with device cards and browse view`

---

## PHASE 4 — Consumer Supporting Tabs

### ⬜ TASK 4.1 — Simplified Sharing Tab
- [ ] New `templates/sharing.html`, new route `GET /sharing`
- [ ] Data from `GET /api/sharing/list` (add endpoint — reads smb.conf shares)
- [ ] One card per share: share name, path (truncated), access level badge, active connection count
- [ ] "Add Share" slide-in panel with 3 fields:
  - Share Name (text)
  - Folder (button opens file manager device picker)
  - Access: radio — "Everyone on network" / "Specific users" (shows user multi-select)
- [ ] On submit: write smb.conf via `testparm` validation, then `smbcontrol smbd reload-config`
- [ ] "Remove" button: confirm then remove share and reload Samba
- [ ] Move raw smb.conf editor to Advanced > Services only
- [ ] Restart and verify share create/delete
- **Commit:** `feat(task4.1): simplified sharing tab with add/remove`

### ⬜ TASK 4.2 — Simplified Users Tab
- [ ] New `templates/users.html` (replace existing if present)
- [ ] User cards grid: avatar circle with initials, username, role badge (Admin/User), Edit/Delete buttons
- [ ] "Add User" slide-in: Name, Password, Confirm Password, Role dropdown
- [ ] "Edit": change password and role only
- [ ] Delete: confirmation dialog "This will remove access for [username]"
- [ ] Hide Linux UID/GID/shell/home — move to Advanced > Services if needed
- [ ] Restart and verify add, edit, delete
- **Commit:** `feat(task4.2): simplified users tab with card layout`

### ⬜ TASK 4.3 — Settings Tab
- [ ] New `templates/settings.html`, new route `GET /settings`
- [ ] **Device Info:** hostname (editable → `hostnamectl set-hostname`), OS version + kernel (read-only from uname)
- [ ] **Network:** current IP and MAC address (read-only from `ip` command)
- [ ] **Time:** timezone dropdown (`timedatectl set-timezone`), current time display
- [ ] **Security:** "Change Admin Password" form (current + new + confirm)
- [ ] **About:** app version (from VERSION file or constant), uptime, link to Logs tab
- [ ] Restart and verify all read correctly, editable ones save
- **Commit:** `feat(task4.3): settings tab with device info, network, time, security`

---

## PHASE 5 — Polish & Stability

### ⬜ TASK 5.1 — Loading states and error handling
- [ ] Skeleton loading placeholders on all dashboard cards during fetch (CSS animation, no JS lib)
- [ ] All API errors return user-friendly messages — no raw tracebacks reach browser (exception handler in `main.py`)
- [ ] All form submissions: disable button + spinner during request, re-enable on completion
- [ ] All destructive actions: require explicit confirmation dialog
- [ ] Restart and verify
- **Commit:** `feat(task5.1): loading states, error handling, confirmation dialogs`

### ⬜ TASK 5.2 — Syncthing status card (future-ready, non-breaking)
- [ ] Add "Backup" card to dashboard checking Syncthing on port 8384
- [ ] If running: show sync status from `http://localhost:8384/rest/system/status` — device ID truncated, folders syncing, last sync time
- [ ] If not running: greyed card "Syncthing not installed — enables automatic phone backup" with "Learn More" link
- [ ] Display-only — no Syncthing install/config from this UI
- [ ] Restart and verify card shows correct state
- **Commit:** `feat(task5.2): syncthing backup status card`

### ⬜ TASK 5.3 — Final memory audit
- [ ] Measure RAM: idle, dashboard open 10 mins, file manager large folder, terminal open, logs streaming
- [ ] For each: `systemctl show cubie-nas --property=MemoryCurrent`
- [ ] If >250MB: use `tracemalloc` snapshot to identify top allocations, fix
- [ ] No large objects in module-level variables
- [ ] WebSocket handlers yield control, don't accumulate data
- [ ] Confirm: idle <150MB, worst-case <250MB
- [ ] Document measurements in `README.md` under "Performance" section
- **Commit:** `feat(task5.3): memory audit and optimization`

### ⬜ TASK 5.4 — Final security audit
- [ ] All WebSocket endpoints reject unauthenticated connections
- [ ] Path traversal test still passes
- [ ] Security headers present on all responses
- [ ] Rate limiting active (test 25 rapid unauthenticated requests)
- [ ] Terminal enforces 1 session per user
- [ ] `grep -r "exec(" app/ scripts/` — audit every instance for injection risk
- [ ] Document findings in `AUDIT.md`
- **Commit:** `feat(task5.4): final security audit`

---

## RULES FOR AGENT (non-negotiable)

- After EVERY task: `sudo systemctl restart cubie-nas && sleep 5 && sudo systemctl is-active cubie-nas` — must return `active`. On failure: read `journalctl -u cubie-nas -n 50 --no-pager`, fix, restart again.
- Never delete or rename an existing working route without adding its replacement first
- Keep all new dependencies minimal — prefer Python stdlib over new packages. Before adding any package: justify in comment and add to `requirements.txt`
- No npm, no webpack, no build step — runs directly on ARM64 Debian
- All CSS in `static/css/style.css` — keep under 30KB total
- CDN JS libraries: pinned versions only, from `cdn.jsdelivr.net` only (matches CSP header)
- Commit after each task: `feat(taskN.N): short description`
- If any task would exceed 300MB RAM: stop, flag it, propose lighter alternative
- Do not add new systemd services — all new functionality inside existing cubie-nas process
- Test each UI change via SSH tunnel: `ssh -L 8443:localhost:8443 radxa@<device-ip>` then open `https://localhost:8443`
