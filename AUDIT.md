# Cubie NAS — Full Repo Audit

**Date:** 2026-02-20
**Auditor:** AI Agent (Claude Opus 4.6)
**Scope:** All files in `app/`, `templates/`, `static/`, `scripts/`, `systemd/`, `requirements.txt`, `.env.example`

---

## 1. Route Map

### Page Routes (app/main.py — Jinja2 rendered)

| Route | Template | Auth | Page key |
|-------|----------|------|----------|
| `GET /` | `login.html` | No | — |
| `GET /overview` | `overview.html` | `_require_login` | `overview` |
| `GET /dashboard` | redirect → `/overview` | cookie check only | `dashboard` |
| `GET /general` | `general.html` | `_require_login` | `general` |
| `GET /storage` | `storage_page.html` | `_require_login` | `storage` |
| `GET /files` | `file_manager_page.html` | `_require_login` | `files` |
| `GET /services` | `services_page.html` | `_require_login` | `services` |
| `GET /network` | `network_page.html` | `_require_login` | `network` |
| `GET /nas` | `nas_page.html` | `_require_login` | `nas` |
| `GET /users` | `users_page.html` | `_require_login` | `users` |
| `GET /logs` | `logs_page.html` | `_require_login` | `logs` |
| `GET /settings` | `settings_page.html` | `_require_login` | `settings` |
| `GET /healthz` | JSON `{ok: true}` | No | — |

### API Routes

| Method | Path | Auth | CSRF | Router |
|--------|------|------|------|--------|
| POST | `/api/auth/login` | No | No | auth |
| POST | `/api/auth/logout` | No | No | auth |
| GET | `/api/storage/drives` | User | — | storage |
| POST | `/api/storage/mount` | Admin | Yes | storage |
| POST | `/api/storage/unmount` | Admin | Yes | storage |
| POST | `/api/storage/format` | Admin | Yes | storage |
| POST | `/api/storage/usb/provision-smb` | Admin | Yes | storage |
| POST | `/api/storage/nvme/provision-smb` | Admin | Yes | storage |
| GET | `/api/files/list` | User | — | files |
| POST | `/api/files/upload` | User | Yes | files |
| GET | `/api/files/download` | User | — | files |
| POST | `/api/files/mkdir` | User | Yes | files |
| POST | `/api/files/rename` | User | Yes | files |
| POST | `/api/files/delete` | User | Yes | files |
| GET | `/api/monitor/snapshot` | User | — | monitoring |
| WS | `/api/monitor/ws` | Cookie | — | monitoring |
| GET | `/api/network/current` | User | — | network |
| POST | `/api/network/save` | Admin | Yes | network |
| GET | `/api/services/list` | User | — | services |
| POST | `/api/services/restart` | Admin | Yes | services |
| POST | `/api/services/enable` | Admin | Yes | services |
| POST | `/api/services/disable` | Admin | Yes | services |
| POST | `/api/services/start` | Admin | Yes | services |
| POST | `/api/services/stop` | Admin | Yes | services |
| GET | `/api/system/general-info` | User | — | system |
| POST | `/api/system/tls/generate` | Admin | Yes | system |
| GET | `/api/system/firewall/commands` | Admin | — | system |
| POST | `/api/system/firewall/apply` | Admin | Yes | system |
| GET | `/api/system/logs` | Admin | — | system |
| GET | `/api/users/app` | Admin | — | users |
| POST | `/api/users/app` | Admin | Yes | users |
| POST | `/api/users/app/password` | Admin | Yes | users |
| POST | `/api/users/system/create` | Admin | Yes | users |
| POST | `/api/users/system/password` | Admin | Yes | users |
| POST | `/api/users/permissions` | Admin | Yes | users |
| GET | `/api/users/sessions` | Admin | — | users |
| GET | `/api/bonus/docker/containers` | Admin | — | bonus |
| POST | `/api/bonus/docker/start` | Admin | Yes | bonus |
| POST | `/api/bonus/docker/stop` | Admin | Yes | bonus |
| POST | `/api/bonus/backup/run` | Admin | Yes | bonus |
| GET | `/api/bonus/plugins` | Admin | — | bonus |

**Total:** 12 page routes, 35 API endpoints, 1 WebSocket

---

## 2. Template → JS Interaction Map

| Template | JS loader function | Data sources |
|----------|-------------------|--------------|
| `overview.html` | `loadOverviewPage()` | `/api/system/general-info`, `/api/storage/drives`, `/api/services/list`, `/api/network/current`, WS `/api/monitor/ws` |
| `general.html` | `loadGeneralPage()` | `/api/system/general-info`, WS `/api/monitor/ws` |
| `storage_page.html` | `loadStoragePage()` | `/api/storage/drives` |
| `file_manager_page.html` | `loadFiles()` | `/api/files/list` |
| `services_page.html` | `loadServices()` | `/api/services/list` |
| `users_page.html` | `loadSessions()` | `/api/users/sessions` |
| `logs_page.html` | `loadLogsPage()` | `/api/system/logs` |
| `settings_page.html` | `loadSettingsPage()` | `/healthz`, `/api/network/state` (NOT FOUND) |
| `network_page.html` | `loadNetworkPage()` | `/api/network/current`, `/api/network/state` (NOT FOUND) |
| `nas_page.html` | `loadNasPage()`, `loadUsbDevices()`, `loadNvmeDevices()` | `/api/services/list`, `/api/storage/drives` |
| `dashboard.html` | same as `users_page.html` | `/api/users/*` |
| `login.html` | inline script | `/api/auth/login` |

---

## 3. Findings

### 3.1 CRITICAL — Missing API Endpoints Referenced by JS

| Called by JS | Expected Endpoint | Status |
|---|---|---|
| `loadSettingsPage()` | `GET /api/network/state` | **DOES NOT EXIST** — silently fails, shows "Error" |
| `loadNetworkPage()` | `GET /api/network/state` | **DOES NOT EXIST** — network page features (WiFi/BT/Hotspot/Ethernet scan) are non-functional |

**Impact:** Settings page health check shows "Error" for monitoring stream. Network page scan features silently fail.

### 3.2 CRITICAL — Direct Subprocess Call Bypasses system_cmd.py

| File | Line | Call |
|------|------|------|
| `app/services/user_ctl.py` | L11 | `asyncio.create_subprocess_exec('chpasswd', ...)` |

**Violation of:** `copilotinstructions.md` §3.1 — "All system shell commands MUST go through `app/services/system_cmd.py`."
**Risk:** No timeout enforcement, no structured result, no retry policy. `chpasswd` receives raw stdin, which is unsafe if username/password contain special characters.

### 3.3 HIGH — No Security Headers on Any Response

No `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, or `Referrer-Policy` headers are set anywhere. The app is vulnerable to:
- Clickjacking (no `X-Frame-Options`)
- MIME-type confusion attacks (no `X-Content-Type-Options`)
- Data exfiltration via injected scripts (no CSP)

### 3.4 HIGH — No Rate Limiting on Unauthenticated Endpoints

`POST /api/auth/login` has per-user/IP lockout after 5 failed attempts, but there is no global rate limiting. An attacker can enumerate usernames or DOS the service by flooding any unauthenticated endpoint.

### 3.5 HIGH — No Global Exception Handler

`app/main.py` has no `@app.exception_handler(Exception)`. Unhandled Python exceptions will return raw tracebacks (FastAPI default behavior in dev mode) exposing internal paths, versions, and logic to the browser.

### 3.6 MEDIUM — Duplicate JS Files (Dead Code)

| File | Size | Status |
|------|------|--------|
| `static/js/app.js` | 8,010 bytes | **DEAD CODE** — not referenced by any template |
| `static/js/router.js` | 37,768 bytes | Active — loaded by `base.html` |

`app.js` is an older version of `router.js` with duplicate `cookie()`, `api()`, `loadFiles()`, `loadServices()` etc. It lacks 401 redirect handling and file type icons. It references DOM IDs (`cpu`, `ram`, `drives-table`) that don't exist in current templates.

**Risk:** Dead code bloat, confusion for future agents.

### 3.7 MEDIUM — Duplicate CSS Files

| File | Size | Status |
|------|------|--------|
| `static/css/style.css` | 2,018 bytes | Only used by `login.html` |
| `static/css/router.css` | 6,924 bytes | Used by `base.html` (all other pages) |

Login page uses `style.css` with different CSS variables (e.g., `--accent: #177f77`) than `router.css` (e.g., `--accent: #0f8a9d`). Visual inconsistency between login and dashboard.

### 3.8 MEDIUM — WebSocket Leak on Page Navigation

`loadGeneralPage()` and `loadOverviewPage()` create new WebSocket connections to `/api/monitor/ws` each time they're called. There is no tracking or cleanup of old connections. On `loadGeneralPage()`, the `ws.onclose` handler recursively calls `loadGeneralPage()` (creating another WebSocket), which means:
- Every WS disconnect spawns a new WS + new `loadGeneralPage()` call
- No deduplication — multiple overlapping connections possible
- Each connection creates a new `RateSampler` server-side (holding psutil state)

**Impact:** Slow memory leak on the server if pages are refreshed repeatedly or connections flap.

### 3.9 MEDIUM — login.html Redirects to `/dashboard` (Wrong Route)

`login.html` inline JS redirects to `/dashboard` on success, which 302-redirects to `/overview`. Should go directly to `/overview`. Minor perf issue (extra redirect) but also confusion.

### 3.10 MEDIUM — dashboard.html Is Misnamed

`templates/dashboard.html` extends `base.html` with `page = 'dashboard'` but its content is "User Management (Admin)" — identical to `users_page.html`. This template appears to be orphaned/legacy. The `/dashboard` route in `main.py` redirects to `/overview`.

### 3.11 MEDIUM — Missing `page` Variable in Some Templates

| Template | Has `{% set page %}` | Sidebar highlights correctly |
|----------|---------------------|---------------------------|
| `general.html` | No | No — no sidebar item highlighted |
| `storage_page.html` | No | No — no sidebar item highlighted |
| `network_page.html` | No | No — no sidebar item highlighted |
| `nas_page.html` | No | No — no sidebar item highlighted |

These templates don't set `page` via `{% set page %}` or receive it from the route handler. The `page` variable is passed from `main.py` in some but not all routes. This causes the sidebar active state to break.

### 3.12 MEDIUM — systemd Service Missing Hardening Settings

| Setting | Current | Recommended |
|---------|---------|-------------|
| `MemoryHigh` | Not set | `250M` (soft warning) |
| `OOMPolicy` | Not set | `continue` |
| `LimitNOFILE` | `65535` | `4096` (excessive; NAS doesn't need 65K FDs) |
| `--workers` | Not set | `1` (explicit single-worker for RAM budget) |
| `--no-access-log` | Not set in service file | Recommended (reduces I/O) |
| `--timeout-keep-alive` | Not set in service file | `5` (prevent connection hoarding) |

**Note:** The running service appears to have `--no-access-log --timeout-keep-alive 5` in its ExecStart, but the repo `systemd/cubie-nas.service` does NOT have these flags. The production service has been manually modified.

### 3.13 LOW — Upload Writes Without fsync

`app/routers/files.py` `upload()` writes uploaded files with `target.open('wb')` and plain writes without calling `os.fsync()`. While this is user data (not system config), power loss during upload could result in a corrupted/truncated file with no indication of failure.

### 3.14 LOW — No User Delete Endpoint

The users router (`app/routers/users.py`) has Create and Change Password but no Delete User endpoint. Users can only be created, never removed through the API.

### 3.15 LOW — CSRF Not Enforced as Middleware

CSRF enforcement (`enforce_csrf()`) is applied per-endpoint via `dependencies=[Depends(enforce_csrf)]` on mutation routes. This is opt-in — any new POST/PUT/DELETE endpoint that forgets to add this dependency will be unprotected. Should be middleware.

### 3.16 LOW — requirements.txt Includes Test Dependencies

`pytest` and `pytest-asyncio` are in `requirements.txt`. These are dev-only dependencies that get installed in production. Should be in a separate `requirements-dev.txt`.

### 3.17 INFO — Font Stack Mismatch

Both CSS files use `font-family: "IBM Plex Sans", "Noto Sans", sans-serif`. The TASKS.md architectural decision specifies system-ui stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`. IBM Plex Sans is likely not installed on the ARM64 device, falling back to whatever sans-serif is available.

### 3.18 INFO — `network_page.html` References Missing DOM Elements

The JS `loadNetworkPage()` function references these DOM IDs that do NOT exist in `network_page.html`:
- `eth-chip`, `eth-scan-body` (Ethernet scan section)
- `wifi-chip` (WiFi section)
- `bt-chip` (Bluetooth section)
- `hotspot-chip`, `hotspot-ssid`, `hotspot-password` (Hotspot section)

These are silently ignored (null checks), but indicate planned features that have template but no backend support.

---

## 4. Memory & Performance Baseline

| Metric | Value |
|--------|-------|
| Idle RAM (service only) | **38 MB** (MemoryCurrent=39899136) |
| MemoryMax | 300 MB |
| MemoryHigh | Not set |
| Workers | 1 (implicit—uvicorn default) |
| `static/` size | 72 KB |
| `router.js` size | 37.8 KB |
| `router.css` size | 6.9 KB |
| `style.css` size | 2.0 KB |
| `app.js` size | 8.0 KB (unused) |

**Assessment:** Service is well within RAM budget at 38 MB idle. Significant headroom for new features.

---

## 5. File Inventory

### Active Files

| Path | Purpose | Lines |
|------|---------|-------|
| `app/main.py` | FastAPI app, page routes, startup | ~190 |
| `app/config.py` | Pydantic settings | ~28 |
| `app/db.py` | SQLAlchemy engine + session | ~22 |
| `app/deps.py` | Auth deps, CSRF | ~55 |
| `app/models.py` | User, LoginAttempt models | ~35 |
| `app/schemas.py` | Pydantic request/response schemas | ~101 |
| `app/security.py` | JWT, password hashing, CSRF token | ~38 |
| `app/routers/auth.py` | Login/logout | ~67 |
| `app/routers/bonus.py` | Docker, backup, plugins | ~65 |
| `app/routers/files.py` | File CRUD | ~92 |
| `app/routers/monitoring.py` | Monitor snapshot + WebSocket | ~49 |
| `app/routers/network.py` | Network config | ~30 |
| `app/routers/services.py` | Systemd service control | ~59 |
| `app/routers/storage.py` | Drive listing, mount, format, provision | ~88 |
| `app/routers/system.py` | General info, TLS, firewall, logs | ~68 |
| `app/routers/users.py` | User management | ~83 |
| `app/services/file_ops.py` | File operations with path traversal protection | ~52 |
| `app/services/monitor.py` | psutil metrics + rate sampling | ~65 |
| `app/services/network.py` | Network config (nmcli or interfaces.d) | ~130 |
| `app/services/service_ctl.py` | Systemd service actions | ~33 |
| `app/services/ssl.py` | Self-signed cert generation | ~31 |
| `app/services/storage.py` | lsblk parsing, SMART | ~65 |
| `app/services/system_cmd.py` | Command runner abstraction | ~106 |
| `app/services/system_info.py` | System info (CPU, model, hostname) | ~40 |
| `app/services/transaction.py` | Transaction runner with rollback | ~40 |
| `app/services/usb_share.py` | USB/NVMe provisioning (core safety flow) | ~430 |
| `app/services/user_ctl.py` | Linux user management | ~45 |

### Dead/Legacy Files

| Path | Reason |
|------|--------|
| `static/js/app.js` | Superseded by `router.js`, not loaded by any template |
| `templates/dashboard.html` | Duplicate of `users_page.html`, route redirects away |
| `templates/partials/` | Empty directory |

---

## 6. Architectural Decisions (for future sessions)

### Frontend Approach
Convert from full Jinja2 page-reload model to hybrid SPA:
- Jinja2 for initial page shell only (auth, base layout, nav)
- All data loading via vanilla JS `fetch()` against FastAPI JSON endpoints
- No React, no Vue, no npm — plain ES6 modules only
- Consumer-app feel without build complexity or RAM overhead

### Device Detection
Use `lsblk -J -o NAME,MOUNTPOINT,SIZE,TRAN,TYPE,LABEL,FSTYPE` as single source of truth. Parse server-side, cache 10 seconds, expose via `GET /api/storage/devices`.

### CSS Approach
All styles in `static/css/style.css` — no Tailwind, no Bootstrap. CSS custom properties for theming. Target under 30KB.

### Fonts
System-ui font stack: `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`. No Google Fonts.

### JS Libraries (CDN, pinned)
- xterm.js 5.3.0 for terminal
- No other framework dependencies
- CDN: cdn.jsdelivr.net only

### Security Headers (middleware)
```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self' wss:
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 7. Priority Remediation List

| # | Severity | Finding | Task |
|---|----------|---------|------|
| 1 | CRITICAL | No security headers | TASK 1.2 |
| 2 | CRITICAL | `user_ctl.py` bypasses `system_cmd.py` | TASK 1.2 |
| 3 | HIGH | No global rate limiting | TASK 1.2 |
| 4 | HIGH | No global exception handler | TASK 5.1 |
| 5 | HIGH | Missing `/api/network/state` endpoint | TASK 4.3 |
| 6 | MEDIUM | Dead `app.js` file | Delete during TASK 1.3 |
| 7 | MEDIUM | WebSocket leak (no cleanup) | TASK 1.3 |
| 8 | MEDIUM | Login redirects to wrong route | TASK 1.3 |
| 9 | MEDIUM | Duplicate/orphan `dashboard.html` | TASK 1.3 |
| 10 | MEDIUM | Missing `page` variable in templates | TASK 1.3 |
| 11 | MEDIUM | systemd hardening gaps | TASK 1.1 |
| 12 | MEDIUM | Dual CSS files | TASK 1.3 |
| 13 | LOW | Upload no fsync | TASK 3.2 |
| 14 | LOW | No user delete endpoint | TASK 4.2 |
| 15 | LOW | CSRF is opt-in not middleware | TASK 1.2 |
| 16 | LOW | Test deps in prod requirements | TASK 1.1 |
| 17 | INFO | Font stack mismatch | TASK 1.3 |
| 18 | INFO | Network page references missing DOM | TASK 4.3 |
