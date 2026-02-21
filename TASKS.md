# Cubie NAS --- Task Sequence

**Status legend:** ⬜ Not started · 🔄 In progress · ✅ Completed · ❌
Blocked

------------------------------------------------------------------------

## AUDIT PHASE (before any code changes)

### ✅ AUDIT --- Full Repo Audit

1.  Read every file in: `app/`, `templates/`, `static/`, `scripts/`,
    `systemd/`, `requirements.txt`, `.env.example`
2.  Map all existing routes, templates, and JS interactions
3.  Identify: broken imports, unused routes, missing error handling,
    memory-heavy patterns, missing security headers
4.  Document findings as `AUDIT.md` in the repo root before proceeding

**Completed 2026-02-20.** Found 18 issues (2 critical, 3 high, 9 medium,
3 low, 2 info). See `AUDIT.md` for details. Baseline: 12 page routes, 35
API endpoints, 1 WebSocket. Idle RAM: 38 MB (well within 300 MB budget).

------------------------------------------------------------------------

## ARCHITECTURAL DECISIONS (apply throughout all tasks)

**Frontend approach:** Convert from full Jinja2 page-reload model to a
hybrid SPA pattern: - Keep Jinja2 for initial page shell only (auth,
base layout, nav) - All data loading, updates, and actions use vanilla
JS `fetch()` against existing FastAPI JSON endpoints - No React, no Vue,
no npm build step --- plain ES6 modules only - Consumer-app feel (no
full page reloads) without build complexity or RAM overhead

**Device detection:** Use
`lsblk -J -o NAME,MOUNTPOINT,SIZE,TRAN,TYPE,LABEL,FSTYPE` as single
source of truth for all storage device detection. Parse once
server-side, cache result for max 10 seconds, expose via
`GET /api/storage/devices`.

**CSS approach:** All styles in `static/css/style.css` --- no Tailwind
(requires build step), no Bootstrap (too heavy). Use CSS custom
properties for theming. Target: style.css under 30KB.

**Fonts:** System-ui font stack only ---
`font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`.
No Google Fonts CDN calls.

**JS libraries (CDN with pinned versions only):** - xterm.js 5.3.0 for
terminal - No other JS framework dependencies

**Security headers (add to all responses via FastAPI middleware):**

    Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self' wss:
    X-Frame-Options: DENY
    X-Content-Type-Options: nosniff
    Referrer-Policy: strict-origin-when-cross-origin

------------------------------------------------------------------------

## PHASE 1 --- Foundation & Security Hardening

### ✅ TASK 1.1 --- Verify RAM budget & systemd hardening

> **Audit refs:** §3.12 (systemd hardening gaps), §3.16 (test deps in
> prod), §4 (baseline 38 MB idle) - \[x\] Check
> `systemd/cubie-nas.service` has `MemoryMax=300M` - \[x\] Add
> `MemoryHigh=250M` as soft warning threshold - \[x\] Add
> `OOMPolicy=continue` so the service survives brief spikes - \[x\]
> Reduce `LimitNOFILE` from current 65535 → `4096` (audit §3.12:
> excessive for NAS) - \[x\] Add explicit `--workers 1` to uvicorn
> ExecStart (audit §3.12: currently implicit default) - \[x\] Sync repo
> service file with production: add
> `--no-access-log --timeout-keep-alive 5` (audit §3.12: production has
> these but repo file does not) - \[x\] Move `pytest` and
> `pytest-asyncio` from `requirements.txt` to `requirements-dev.txt`
> (audit §3.16) - \[x\] Restart and confirm:
> `systemctl is-active cubie-nas` returns `active` - \[x\] Confirm after
> 2 mins idle: `systemctl show cubie-nas --property=MemoryCurrent` is
> under 250MB (`MemoryCurrent=84856832` ≈ 80.9 MB) - \[x\] Document
> baseline RAM in `AUDIT.md` (already measured: 38 MB idle) -
> **Commit:**
> `feat(task1.1): systemd hardening and RAM budget verification`

### ✅ TASK 1.2 --- Add global security middleware

> **Audit refs:** §3.3 (no security headers --- CRITICAL), §3.4 (no rate
> limiting --- HIGH), §3.2 (user_ctl bypasses system_cmd --- CRITICAL),
> §3.15 (CSRF opt-in not middleware) - \[x\] In `app/main.py` add
> middleware that injects security headers on every response: -
> `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self' wss:` -
> `X-Frame-Options: DENY` - `X-Content-Type-Options: nosniff` -
> `Referrer-Policy: strict-origin-when-cross-origin` - \[x\] Add global
> rate limiting middleware using simple in-memory token bucket (no new
> heavy deps) --- limit unauthenticated endpoints to 20 req/min per IP -
> \[x\] Fix `app/services/user_ctl.py` L11: `chpasswd` call bypasses
> `system_cmd.py` --- route through `system_cmd.run()` with proper
> timeout/escaping (audit §3.2 --- CRITICAL) - \[x\] Convert CSRF
> enforcement from per-endpoint `Depends(enforce_csrf)` to middleware
> for all POST/PUT/DELETE (audit §3.15 --- prevents forgetting on new
> endpoints) - \[x\] Restart and verify headers appear in browser
> DevTools Network tab (automated verification: middleware tests pass;
> service restart status `active`) - **Commit:**
> `feat(task1.2): global security headers and rate limiting middleware`

### ✅ TASK 1.3 --- Create shared base template

> **Audit refs:** §3.6 (dead app.js), §3.7 (dual CSS files), §3.8
> (WebSocket leak), §3.9 (login redirect wrong), §3.10 (orphan
> dashboard.html), §3.11 (missing page var), §3.17 (font stack
> mismatch) - \[x\] Create `templates/base.html` as master layout used
> by ALL other templates - \[x\] Base template includes: nav sidebar,
> top bar, content slot, toast notification container, global JS fetch
> helpers, WebSocket reconnect utility - \[x\] WebSocket reconnect
> utility: exponential backoff starting at 1s, max 30s, auto-reconnect
> on disconnect - \[x\] Nav sidebar structure: - Consumer section
> (always visible): Dashboard, Files, Sharing, Users, Settings -
> Advanced section (collapsed by default, toggle with chevron): Terminal
> ⚡, Logs ⚡, Storage ⚡, Services ⚡, Docker ⚡ - \[x\] Global toast
> system: `window.toast(message, type)` where type =
> success/error/warning/info --- non-blocking, auto-dismiss after 4s -
> \[x\] Global fetch wrapper: `window.api(path, options)` that handles
> auth errors (redirect to login on 401), shows toast on error, returns
> parsed JSON - \[x\] Update ALL existing templates to extend
> `base.html` - \[x\] Delete dead `static/js/app.js` --- superseded by
> `router.js`, not loaded anywhere (audit §3.6) - \[x\] Consolidate
> `static/css/style.css` and `static/css/router.css` into single
> `style.css` (audit §3.7 --- login page uses different CSS vars than
> rest of app) - \[x\] Fix WebSocket leak: `loadGeneralPage()` and
> `loadOverviewPage()` create new WS connections without cleanup;
> `ws.onclose` recursively calls `loadGeneralPage()` causing unbounded
> reconnects (audit §3.8) - \[x\] Fix `login.html` redirect from
> `/dashboard` → `/overview` (audit §3.9 --- avoids unnecessary 302
> redirect) - \[x\] Remove orphaned `templates/dashboard.html` (audit
> §3.10 --- duplicate of `users_page.html`, route already redirects
> away) - \[x\] Fix missing `{% set page %}` in `general.html`,
> `storage_page.html`, `network_page.html`, `nas_page.html` so sidebar
> active state works (audit §3.11) - \[x\] Update font stack to
> system-ui:
> `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`
> (audit §3.17 --- IBM Plex Sans not installed on ARM64) - \[x\] Restart
> and verify all pages still load - **Commit:**
> `feat(task1.3): shared base template with nav, toast, and fetch helpers`

### ✅ TASK 1.4 --- Add xterm.js Terminal Tab (Power User)

-   [x] Add route `GET /terminal` in `app/routers/system.py` serving
    `templates/terminal.html`
-   [x] Add WebSocket endpoint `/ws/terminal` in
    `app/routers/system.py`:
    -   Authenticate via cookie/token before accepting --- reject
        unauthenticated with 403
    -   Enforce ONE active terminal session per authenticated user
        (module-level dict, clean up on disconnect)
    -   Spawn bash PTY using `os.openpty()` +
        `asyncio.create_subprocess_exec` (stdlib only, no ptyprocess)
    -   Forward stdin/stdout between WebSocket and PTY
    -   On WebSocket close: kill PTY subprocess cleanly
-   [x] Template `templates/terminal.html`:
    -   Load xterm.js 5.3.0 from CDN:
        `https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css` and
        `xterm.min.js`
    -   Load xterm-addon-fit from same CDN for responsive sizing
    -   Connect to `/ws/terminal` on page load
    -   Show "Session limit reached" message if server rejects with 403
-   [x] Add "Terminal" to Advanced nav section
-   [x] Restart and verify terminal spawns, accepts input, cleans up on
    tab close
-   **Commit:**
    `feat(task1.4): xterm.js terminal tab with PTY over WebSocket`

### ✅ TASK 1.5 --- Add Unified Log Viewer Tab (Power User)

-   [x] Add route `GET /logs` in `app/routers/system.py`
-   [x] Add WebSocket `/ws/logs` in `app/routers/system.py`:
    -   Authenticate before accepting
    -   Stream output of:
        `journalctl -f -u cubie-nas -u smbd -u nmbd -u nfs-kernel-server -u ssh -u vsftpd --output=short-iso --no-pager`
    -   CRITICAL: never buffer more than 500 lines in memory --- async
        line-by-line streaming, discard oldest when buffer full
    -   Send each line as JSON:
        `{"ts": "...", "unit": "smbd", "level": "INFO", "msg": "..."}`
-   [x] Template `templates/logs.html`:
    -   Auto-scrolling log window (pause scroll on hover, resume on
        click)
    -   Color coding: ERROR/CRIT = red, WARN = yellow, INFO = white,
        DEBUG = gray
    -   Client-side filter input: filters visible lines without
        re-fetching
    -   Unit filter pills: click to show/hide specific service logs
    -   "Clear display" button (clears client buffer only)
-   [x] Add "Logs" to Advanced nav section
-   [x] Restart and verify logs stream, filter works, memory stays
    stable after 5 mins
-   **Commit:**
    `feat(task1.5): unified log viewer with WebSocket streaming`

------------------------------------------------------------------------

## PHASE 2 --- Consumer-Grade Dashboard

### ✅ TASK 2.1 --- Redesign Dashboard

-   [x] Redesign `templates/dashboard.html` as single-view overview card
    grid
-   [x] All data via `fetch()` + WebSocket, no full page reloads
-   [x] Layout: CSS Grid, 2 columns desktop, 1 column mobile (responsive
    media query)
-   [x] Design tokens in CSS:
    -   `--color-bg: #0f1117`
    -   `--color-surface: #1a1d2e`
    -   `--color-accent: #4F8EF7`
    -   `--color-success: #22c55e`
    -   `--color-error: #ef4444`
    -   `--color-warning: #f59e0b`
    -   `--color-text: #e2e8f0`
    -   `--color-muted: #64748b`
    -   `--radius: 12px`
-   [x] **Card 1 --- System Health** (live via WebSocket `/ws/monitor`)
    -   CPU usage %: animated progress ring
    -   RAM usage %: animated progress bar showing used/total
    -   Temperature: color-coded (green \<60°C, yellow \<75°C, red
        ≥75°C)
    -   Uptime: human-readable (e.g., "3 days 4 hrs")
-   [x] **Card 2 --- Storage Overview** (fetch
    `GET /api/storage/devices`, refresh every 30s)
    -   One row per detected device: SD Card icon, USB icon, or NVMe
        icon
    -   Each row: device label, used/total, linear progress bar (red if
        \>90% full)
    -   Detection via lsblk --- SD=mmcblk, USB=TRAN=usb, NVMe=TRAN=nvme
-   [x] **Card 3 --- Network** (live via WebSocket `/ws/monitor`)
    -   Current IP address
    -   Upload speed (KB/s or MB/s auto-scaled)
    -   Download speed (KB/s or MB/s auto-scaled)
-   [x] **Card 4 --- Services** (fetch `GET /api/services/status`,
    refresh every 15s)
    -   Samba, SSH, NFS, FTP --- each row: service name, green/red
        status dot, toggle ON/OFF button
    -   Toggle calls existing service control endpoint, toast on
        success/error
-   [x] **Card 5 --- Active SMB Connections** (fetch
    `GET /api/sharing/connections`, refresh every 30s)
    -   Parse `smbstatus -j` server-side, expose via new endpoint
    -   Show: connected user, IP address, connected since
    -   "No active connections" graceful state
-   [x] Remove all raw JSON debug output
-   [x] Restart and verify all cards load, live data updates, toggles
    work
-   **Commit:**
    `feat(task2.1): consumer-grade dashboard with live cards`

------------------------------------------------------------------------

## PHASE 3 --- Consumer File Manager

### ✅ TASK 3.1 --- Device detection endpoint

-   [x] Add `GET /api/storage/devices` to `app/routers/storage.py`

-   [x] Run `lsblk -J -o NAME,MOUNTPOINT,SIZE,TRAN,TYPE,LABEL,FSTYPE` as
    subprocess

-   [x] Parse and return array:

    ``` json
    [
      {"id": "mmcblk0", "label": "System SD", "type": "sd", "mountpoint": "/", "total_gb": 32, "used_gb": 8, "free_gb": 24},
      {"id": "sda", "label": "USB Drive", "type": "usb", "mountpoint": "/media/usb0", "total_gb": 64, "used_gb": 20, "free_gb": 44},
      {"id": "nvme0n1", "label": "NVMe Storage", "type": "nvme", "mountpoint": "/mnt/nvme", "total_gb": 256, "used_gb": 100, "free_gb": 156}
    ]
    ```

-   [x] Only return mounted devices (mountpoint not null/empty)

-   [x] Cache result for 10 seconds (simple time-based dict cache, no
    Redis)

-   [x] Validate all mountpoints are real paths

-   **Commit:** `feat(task3.1): device detection endpoint via lsblk`

### ✅ TASK 3.2 --- File manager security layer

> **Audit refs:** §3.13 (upload writes without fsync) - \[x\] In
> `app/services/file_ops.py` add
> `validate_path(requested_path, device_mountpoint)`: - Resolve real
> path using `os.path.realpath()` - Raise 403 if resolved path does not
> start with device mountpoint - Prevents all path traversal attacks -
> \[x\] Apply validation to ALL file operation endpoints (list, read,
> upload, rename, delete, mkdir, download) - \[x\] Add `os.fsync()`
> after upload writes in `app/routers/files.py` to prevent data
> corruption on power loss (audit §3.13) - \[x\] Add test in `tests/`
> verifying path traversal returns 403 - \[x\] Restart and run test -
> **Commit:**
> `feat(task3.2): file manager path traversal security layer`

### ✅ TASK 3.3 --- Redesign File Manager UI

-   [x] Completely replace `templates/files.html` and its JS
-   [x] **Landing view --- Storage Devices:**
    -   One card per device from `GET /api/storage/devices`
    -   Card: large icon (SD/USB/NVMe inline SVG), device label, size
        bar, "Browse →" button
    -   Undetected devices: greyed-out card with "Not connected"
-   [x] **Browse view:**
    -   Breadcrumb bar showing path relative to device root (clickable
        crumbs)
    -   Toggle Grid view / List view (preference in localStorage)
    -   Grid: folders first (folder icon + name), then files (type
        icon + name + size)
    -   List: columns --- Name, Size, Date Modified, Type
    -   File type icons (inline SVG): folder, image, video, audio,
        document, archive, code, unknown
    -   Right-click context menu (long-press mobile): Rename, Delete,
        Download, Copy Path
    -   Multi-select: checkbox in list, long-click in grid --- bulk
        Delete and bulk Download (zip)
    -   Upload zone: dashed drop zone, click or drag
    -   New Folder button in toolbar
    -   Back button to device landing
-   [x] All file operations use existing backend endpoints, toast on
    success/error
-   [x] Restart and verify: device cards, browsing, upload, rename,
    delete, path traversal test passes
-   **Commit:**
    `feat(task3.3): consumer file manager with device cards and browse view`

------------------------------------------------------------------------

## PHASE 4 --- Consumer Supporting Tabs

### ✅ TASK 4.1 --- Simplified Sharing Tab

-   [x] New `templates/sharing.html`, new route `GET /sharing`
-   [x] Data from `GET /api/sharing/list` (add endpoint --- reads
    smb.conf shares)
-   [x] One card per share: share name, path (truncated), access level
    badge, active connection count
-   [x] "Add Share" slide-in panel with 3 fields:
    -   Share Name (text)
    -   Folder (button opens file manager device picker)
    -   Access: radio --- "Everyone on network" / "Specific users"
        (shows user multi-select)
-   [x] On submit: write smb.conf via `testparm` validation, then
    `smbcontrol smbd reload-config`
-   [x] "Remove" button: confirm then remove share and reload Samba
-   [x] Move raw smb.conf editor to Advanced \> Services only
-   [x] Restart and verify share create/delete
-   **Commit:** `feat(task4.1): simplified sharing tab with add/remove`

### ✅ TASK 4.2 --- Simplified Users Tab

> **Audit refs:** §3.14 (no user delete endpoint) - \[x\] New
> `templates/users.html` (replace existing if present) - \[x\] User
> cards grid: avatar circle with initials, username, role badge
> (Admin/User), Edit/Delete buttons - \[x\] "Add User" slide-in: Name,
> Password, Confirm Password, Role dropdown - \[x\] "Edit": change
> password and role only - \[x\] Add `DELETE /api/users/app/{username}`
> endpoint --- currently no way to remove users via API (audit §3.14) -
> \[x\] Delete: confirmation dialog "This will remove access for
> \[username\]" - \[x\] Hide Linux UID/GID/shell/home --- move to
> Advanced \> Services if needed - \[x\] Restart and verify add, edit,
> delete - **Commit:**
> `feat(task4.2): simplified users tab with card layout`

### ✅ TASK 4.3 --- Settings Tab

> **Audit refs:** §3.1 (missing /api/network/state --- CRITICAL), §3.18
> (network page missing DOM elements) - \[x\] New
> `templates/settings.html`, new route `GET /settings` - \[x\] **Device
> Info:** hostname (editable → `hostnamectl set-hostname`), OS version +
> kernel (read-only from uname) - \[x\] **Network:** current IP and MAC
> address (read-only from `ip` command) - \[x\] **Time:** timezone
> dropdown (`timedatectl set-timezone`), current time display - \[x\]
> **Security:** "Change Admin Password" form (current + new + confirm) -
> \[x\] **About:** app version (from VERSION file or constant), uptime,
> link to Logs tab - \[x\] Add missing `GET /api/network/state` endpoint
> or fix JS references --- `loadSettingsPage()` and `loadNetworkPage()`
> both call this non-existent endpoint causing silent failures (audit
> §3.1 --- CRITICAL) - \[x\] Fix `network_page.html` DOM element
> references: `eth-chip`, `eth-scan-body`, `wifi-chip`, `bt-chip`,
> `hotspot-chip` etc. are referenced in JS but don't exist in template
> (audit §3.18) - \[x\] Restart and verify all read correctly, editable
> ones save - **Commit:**
> `feat(task4.3): settings tab with device info, network, time, security`

------------------------------------------------------------------------

## PHASE 5 --- Polish & Stability

### ✅ TASK 5.1 --- Loading states and error handling

> **Audit refs:** §3.5 (no global exception handler --- HIGH) - \[x\]
> Skeleton loading placeholders on all dashboard cards during fetch (CSS
> animation, no JS lib) - \[x\] Add global
> `@app.exception_handler(Exception)` in `main.py` --- currently
> unhandled exceptions return raw tracebacks exposing internal paths and
> logic (audit §3.5 --- HIGH) - \[x\] All API errors return
> user-friendly messages --- no raw tracebacks reach browser - \[x\] All
> form submissions: disable button + spinner during request, re-enable
> on completion - \[x\] All destructive actions: require explicit
> confirmation dialog - \[x\] Restart and verify - **Commit:**
> `feat(task5.1): loading states, error handling, confirmation dialogs`

### ✅ TASK 5.2 --- Syncthing status card (future-ready, non-breaking)

-   [x] Add "Backup" card to dashboard checking Syncthing on port 8384
-   [x] If running: show sync status from
    `http://localhost:8384/rest/system/status` --- device ID truncated,
    folders syncing, last sync time
-   [x] If not running: greyed card "Syncthing not installed --- enables
    automatic phone backup" with "Learn More" link
-   [x] Display-only --- no Syncthing install/config from this UI
-   [x] Restart and verify card shows correct state
-   **Commit:** `feat(task5.2): syncthing backup status card`

### ✅ TASK 5.3 --- Final memory audit

-   [x] Measure RAM: idle, dashboard open 10 mins, file manager large
    folder, terminal open, logs streaming
-   [x] For each: `systemctl show cubie-nas --property=MemoryCurrent`
-   [x] If \>250MB: use `tracemalloc` snapshot to identify top
    allocations, fix
-   [x] No large objects in module-level variables
-   [x] WebSocket handlers yield control, don't accumulate data
-   [x] Confirm: idle \<150MB, worst-case \<250MB
-   [x] Document measurements in `README.md` under "Performance" section
-   **Commit:** `feat(task5.3): memory audit and optimization`

### ✅ TASK 5.4 --- Final security audit

> **Audit refs:** §3.2 (user_ctl subprocess bypass), §3.15 (CSRF
> opt-in) - \[x\] All WebSocket endpoints reject unauthenticated
> connections - \[x\] Path traversal test still passes - \[x\] Security
> headers present on all responses - \[x\] Rate limiting active (test 25
> rapid unauthenticated requests) - \[x\] Terminal enforces 1 session
> per user - \[x\] `grep -r "exec(" app/ scripts/` --- audit every
> instance for injection risk - \[x\] Verify `user_ctl.py` `chpasswd`
> call now routes through `system_cmd.py` (originally fixed in TASK 1.2,
> verify it wasn't regressed) - \[x\] Verify CSRF enforcement is
> middleware-based, not opt-in per-endpoint (originally fixed in TASK
> 1.2) - \[x\] Verify no dead code remains (`app.js`, orphan templates,
> unused CSS) - \[x\] Document findings in `AUDIT.md` - **Commit:**
> `feat(task5.4): final security audit`

------------------------------------------------------------------------

## PHASE 6 --- Production Hardening

### ⬜ TASK 6.1 --- Force password change on first login

> Default `admin12345` ships with production seed --- must not remain in
> use. - \[ \] Add `must_change_password: bool` column to `User` model
> (default `True` for seed admin, `False` for API-created users) - \[ \]
> Create `templates/force_password_change.html` --- minimal form: new
> password + confirm, no nav/sidebar - \[ \] In `_require_login()`
> (app/main.py): if `user.must_change_password is True`, redirect to
> `/change-password` instead of requested page - \[ \] Add route
> `GET /change-password` serving the template (auth-gated, skip
> `must_change_password` check to avoid redirect loop) - \[ \] Add route
> `POST /api/users/me/force-password` --- validates new password ≥ 8
> chars, hashes it, sets `must_change_password = False`, commits - \[ \]
> Exempt `/api/users/me/force-password` and `/change-password` from the
> redirect guard - \[ \] Update seed admin creation in `lifespan()` to
> set `must_change_password=True` - \[ \] Add test: verify seed admin is
> redirected to change-password page on first login - \[ \] Restart and
> verify: login as admin → forced to change → after change, normal
> access - **Commit:**
> `feat(task6.1): force password change on first login`

### ⬜ TASK 6.2 --- Auto-TLS with self-signed certificate

> Service listens on plain HTTP (port 8443). Consumer product must
> default to HTTPS. - \[ \] In `lifespan()`: check if
> `settings.tls_cert_file` and `settings.tls_key_file` exist - \[ \] If
> missing: call `ensure_self_signed()` from `app/services/ssl.py` to
> auto-generate self-signed cert+key - \[ \] Update
> `systemd/cubie-nas.service` ExecStart to include `--ssl-keyfile` and
> `--ssl-certfile` flags pointing to config paths - \[ \] Update CSP
> header `connect-src` to include `wss:` (already present) --- verify no
> `ws:` only references remain in JS - \[ \] Add `.env.example` entry
> documenting TLS cert/key paths - \[ \] Restart and verify:
> `curl -kI https://localhost:8443/healthz` returns 200 with security
> headers - \[ \] Verify WebSocket connections still work over
> `wss://` - **Commit:**
> `feat(task6.2): auto-TLS with self-signed certificate`

### ⬜ TASK 6.3 --- Session invalidation on password change

> Existing JWT tokens remain valid after password change until natural
> expiry. - \[ \] Add `token_revision: int` column to `User` model
> (default `0`) - \[ \] Include `token_revision` (as `rev`) claim in JWT
> payload when creating token in `create_access_token()` - \[ \] In
> `decode_token()` or `get_current_user()`: compare JWT `rev` claim
> against `user.token_revision` in DB --- reject if mismatch - \[ \]
> Increment `user.token_revision` in all password-change endpoints:
> `change_app_password`, `change_my_password`, `force-password` - \[ \]
> Add test: change password → old token returns 401 - \[ \] Restart and
> verify: login, change password, old session redirects to login -
> **Commit:** `feat(task6.3): session invalidation on password change`

### ⬜ TASK 6.4 --- Upload file size limit

> `/api/files/upload` has no size limit --- risk of disk exhaustion
> attack. - \[ \] Add `max_upload_size_mb: int = 2048` to `Settings` in
> `app/config.py` (2 GB default, configurable via `.env`) - \[ \] In
> `app/routers/files.py` upload endpoint: check `Content-Length` header
> before reading --- reject with 413 if exceeds limit - \[ \] As
> fallback: track bytes read in the chunk loop --- abort and delete
> partial file if cumulative size exceeds limit - \[ \] Return clear
> error message: `"File exceeds maximum upload size of {limit} MB"` - \[
> \] Add test: upload larger than limit returns 413 - \[ \] Restart and
> verify: small upload succeeds, oversized upload rejected - **Commit:**
> `feat(task6.4): upload file size limit`

### ⬜ TASK 6.5 --- Structured JSON logging

> Currently uses Python `logging.exception()` --- not suitable for
> production log aggregation. - \[ \] Add `python-json-logger` to
> `requirements.txt` - \[ \] In `app/main.py` or a new
> `app/logging_config.py`: configure root logger with
> `pythonjsonlogger.jsonlogger.JsonFormatter` - \[ \] Log format:
> `{"timestamp", "level", "logger", "message", "request_id", "path", "method"}` -
> \[ \] Add a `request_id` (UUID4) to each request via middleware,
> include in all log entries for that request - \[ \] Ensure
> `unhandled_exception_handler` logs with structured format including
> traceback - \[ \] Keep `journalctl` readability: one JSON object per
> line - \[ \] Restart and verify:
> `journalctl -u cubie-nas -n 10 --no-pager` shows JSON lines -
> **Commit:** `feat(task6.5): structured JSON logging with request IDs`

### ⬜ TASK 6.6 --- WebSocket token expiry check

> Dashboard WebSocket connections continue indefinitely after JWT
> expiry. - \[ \] In `_monitor_ws_impl()` (app/routers/monitoring.py):
> add periodic token re-validation every 60 seconds - \[ \] Extract the
> cookie token once at connection start, then re-decode it each check
> cycle --- if `decode_token()` raises `ValueError` (expired), send
> close frame with code 4401 and message "Session expired" - \[ \] In
> `/ws/terminal` and `/ws/logs` handlers: add same periodic check (every
> 60s) - \[ \] Frontend: in `createReconnectingWebSocket()` --- if close
> code is 4401, redirect to login instead of auto-reconnecting - \[ \]
> Add test: mock an expired token mid-session → verify WS closes with
> 4401 - \[ \] Restart and verify: WS stays open during valid session,
> closes after token expiry - **Commit:**
> `feat(task6.6): WebSocket token expiry check`

### ⬜ TASK 6.7 --- SQLite database backup timer

> SQLite DB at `/var/lib/cubie-nas/cubie_nas.db` has no automated
> backup. - \[ \] Add `GET /api/system/backup-db` endpoint (admin only):
> runs
> `sqlite3 /var/lib/cubie-nas/cubie_nas.db ".backup /var/lib/cubie-nas/cubie_nas.db.bak"`
> via `RealCommandRunner` - \[ \] Add in-process background task
> (asyncio): run DB backup every 24 hours, log result - \[ \] Keep only
> latest backup (`.bak` file) --- no accumulation - \[ \] Start the
> background task in `lifespan()` startup, cancel it on shutdown - \[ \]
> Add "Last DB Backup" timestamp to Settings page About section - \[ \]
> Restart and verify: manual backup via API works, background task logs
> first run - **Commit:** `feat(task6.7): SQLite database backup timer`

### ⬜ TASK 6.8 --- Deep health endpoint

> `/healthz` only returns `{"ok": true}` --- insufficient for production
> monitoring. - \[ \] Rename existing `/healthz` to keep it as a
> lightweight liveness probe (no change) - \[ \] Add
> `GET /api/system/health` (auth-gated) returning deep check:
>
> ``` json
> {
> "ok": true,
> "checks": {
> "database": {"ok": true, "latency_ms": 2},
> "disk_root": {"ok": true, "free_gb": 12.4, "warning": false},
> "disk_nas": {"ok": true, "free_gb": 44.1, "warning": false},
> "memory": {"ok": true, "used_mb": 85, "limit_mb": 300, "warning": false}
> },
> "uptime_seconds": 86400,
> "version": "1.0.0"
> }
> ```
>
> -   [ ] Database check: execute `SELECT 1` with 2-second timeout
> -   [ ] Disk checks: warn if any mountpoint has \<10% free space
> -   [ ] Memory check: read `MemoryCurrent` from systemd cgroup, warn
>     if \>80% of `MemoryMax`
> -   [ ] Top-level `ok` is `false` if any check fails
> -   [ ] Display health status on Settings page About section
> -   [ ] Restart and verify: endpoint returns all checks, Settings page
>     shows status
> -   **Commit:**
>     `feat(task6.8): deep health endpoint with DB, disk, and memory checks`

### ⬜ TASK 6.9 --- Remove orphan General page

> `/general` route exists with full `loadGeneralPage()` in router.js but
> is not linked from sidebar nav. - \[ \] Remove route `GET /general`
> from `app/main.py` - \[ \] Delete `templates/general.html` - \[ \]
> Remove `loadGeneralPage()` function and its `generalWsController`
> variable from `static/js/router.js` - \[ \] Remove the
> `if (page === 'general')` dispatch block at bottom of router.js - \[
> \] Verify no other template or JS references `/general` - \[ \]
> Restart and verify: all pages load, no 500 errors in logs -
> **Commit:** `feat(task6.9): remove orphan general page`

### ⬜ TASK 6.10 --- Docker feature gating

> `/api/bonus/docker/*` endpoints return errors if Docker isn't
> installed. UI should handle this gracefully. - \[ \] Add
> `GET /api/bonus/docker/available` endpoint: returns
> `{"available": true/false}` based on `which docker` exit code (cache
> result for 60s) - \[ \] In dashboard or NAS page: check Docker
> availability before rendering Docker-related UI elements - \[ \] If
> Docker not available: show disabled card or hide Docker section
> entirely, with message "Docker not installed" - \[ \] Existing Docker
> endpoints: return 404 with `"Docker is not installed on this system"`
> instead of raw command errors when Docker binary is missing - \[ \]
> Restart and verify: without Docker → graceful UI; with Docker →
> containers list works - **Commit:**
> `feat(task6.10): Docker feature gating`

------------------------------------------------------------------------

## RULES FOR AGENT (non-negotiable)

-   After EVERY task:
    `sudo systemctl restart cubie-nas && sleep 5 && sudo systemctl is-active cubie-nas`
    --- must return `active`. On failure: read
    `journalctl -u cubie-nas -n 50 --no-pager`, fix, restart again.
-   Never delete or rename an existing working route without adding its
    replacement first
-   Keep all new dependencies minimal --- prefer Python stdlib over new
    packages. Before adding any package: justify in comment and add to
    `requirements.txt`
-   No npm, no webpack, no build step --- runs directly on ARM64 Debian
-   All CSS in `static/css/style.css` --- keep under 30KB total
-   CDN JS libraries: pinned versions only, from `cdn.jsdelivr.net` only
    (matches CSP header)
-   Commit after each task: `feat(taskN.N): short description`
-   If any task would exceed 300MB RAM: stop, flag it, propose lighter
    alternative
-   Do not add new systemd services --- all new functionality inside
    existing cubie-nas process
-   Test each UI change via SSH tunnel:
    `ssh -L 8443:localhost:8443 radxa@<device-ip>` then open
    `https://localhost:8443`

# PHASE 7 --- Commercial Product Readiness

These tasks are required to move Cubie NAS from hardened hobby project
to commercial-grade product.

------------------------------------------------------------------------

## ⬜ TASK 7.1 --- Role-Based Permission Matrix (Granular RBAC)

-   Add Permission model (read, write, share, manage_users,
    manage_services, terminal_access, logs_access)
-   Add Role table with many-to-many permissions
-   Replace admin checks with permission-based dependency checks
-   Allow custom roles via UI
-   Migrate existing Admin role to full permissions
-   Add DB migration script
-   Add test coverage for permission enforcement

------------------------------------------------------------------------

## ⬜ TASK 7.2 --- Immutable Audit Trail

-   Create AuditLog table:
    -   id
    -   timestamp
    -   user_id
    -   action_type
    -   resource
    -   metadata (JSON)
    -   success/failure
-   Log all sensitive actions:
    -   File delete/rename
    -   Share create/remove
    -   Service start/stop
    -   User create/delete
    -   Password change
    -   Login success/failure
-   Add GET /api/system/audit (Admin only)
-   Add CSV export
-   Prevent deletion of audit logs
-   Add pagination

------------------------------------------------------------------------

## ⬜ TASK 7.3 --- Automatic Update System

-   Add version check endpoint
-   Fetch remote manifest
-   Compare semantic version with local VERSION
-   Show "Update Available" banner
-   (Optional) Signed OTA updates with rollback on failure

------------------------------------------------------------------------

## ⬜ TASK 7.4 --- Full Configuration Backup & Restore

-   Add "Export Configuration" feature
-   Include:
    -   SQLite DB
    -   smb.conf
    -   TLS cert/key
    -   .env config
-   Bundle as encrypted archive
-   Add restore endpoint (Admin only)
-   Validate integrity before applying

------------------------------------------------------------------------

## ⬜ TASK 7.5 --- Advanced Brute-Force Protection

-   Exponential backoff on failed logins
-   Optional TOTP 2FA support
-   Temporary IP block after repeated failures
-   Log all login attempts to AuditLog

------------------------------------------------------------------------

## ⬜ TASK 7.6 --- Per-User Storage Quotas

-   Add quota field to user model
-   Enforce quota during uploads
-   Add UI usage bar
-   Reject upload when quota exceeded

------------------------------------------------------------------------

## ⬜ TASK 7.7 --- Future Cluster-Ready Architecture

-   Introduce node_id concept
-   Abstract storage backend layer
-   Prepare DB schema for multi-node expansion
-   Mark experimental

------------------------------------------------------------------------

## ⬜ TASK 7.8 --- Hardened Terminal Controls

-   Add toggle to disable terminal globally
-   Add permission: terminal_access
-   Optional restricted shell mode (rbash)
-   Add idle auto-timeout
-   Log terminal sessions in AuditLog

------------------------------------------------------------------------

## ⬜ TASK 7.9 --- Licensing & Activation System

-   Add license status endpoint
-   Offline signed license validation
-   Grace period handling
-   UI warning on expiration
-   Feature-tier gating (Basic / Pro)

------------------------------------------------------------------------

## ⬜ TASK 7.10 --- Production Deployment Mode

-   Add APP_MODE=production flag
-   Enforce HTTPS-only
-   Enforce strong password policy (min 12 chars)
-   Disable debug endpoints
-   Refuse startup if default admin password still active

------------------------------------------------------------------------

## ⬜ TASK 7.11 --- Formal Security Review Checklist

-   Static analysis (bandit)
-   Dependency scan (pip-audit)
-   Manual penetration test checklist
-   OWASP ZAP scan
-   Harden CSP further
-   Validate all command execution surfaces
-   Create SECURITY.md documentation

------------------------------------------------------------------------

## ⬜ TASK 7.12 --- Load & Stress Testing

-   Simulate 20 concurrent users
-   Simulate large parallel uploads
-   Simulate WebSocket churn
-   Measure RAM, CPU, latency
-   Validate MemoryMax compliance
-   Document findings

------------------------------------------------------------------------
