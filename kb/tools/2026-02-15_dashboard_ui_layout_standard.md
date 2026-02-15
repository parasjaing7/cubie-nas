## Title

Dashboard UI layout standard for Cubie NAS (OpenMediaVault/router style)

## Date

2026-02-15

## Category

tools

## Tags

dashboard, ui, css-grid, responsive, overflow, panels, admin-layout

## Environment

- **Device/Board:** Cubie A5E (ARM64)
- **OS:** Debian/Ubuntu Linux
- **Kernel:** `uname -r`
- **Repo branch:** `main`
- **Service version:** `git rev-parse --short HEAD`

## Problem Statement

Dashboard layout was inconsistent and misaligned due to mixed layout systems and duplicated UI scripts, causing uneven panel behavior and overflow risk.

## Symptoms

- Dashboard used a different shell and stylesheet than the rest of the app.
- Inconsistent panel spacing and card sizing.
- Potential script conflicts (theme/logout handlers registered in two scripts).
- Table/list areas expanded page height instead of using internal scroll.

## Root Cause

1. `/dashboard` used standalone `templates/dashboard.html` + `static/css/style.css` while other pages used `base.html` + `router.css`.
2. Main layout relied on auto-fit grid without strict panel constraints for admin-style alignment.
3. No unified panel scroll containers for table-heavy sections.
4. Duplicate theme/logout listeners in `app.js` and `router.js` when sharing shell.

## Fix

1. Move dashboard to base shell (`{% extends 'base.html' %}`) and set page context for active nav.
2. Use rigid CSS Grid dashboard with exactly 5 main panels.
3. Add fixed/sticky top header, consistent panel/card style, and table sticky headers.
4. Add internal scroll containers for Storage/File Manager/Services/User sessions.
5. Add global overflow-x guard and responsive breakpoints.
6. Remove duplicate theme/logout event bindings from dashboard script.

## Commands

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

```bash
cd /home/radxa/nas102/cubie-nas
python3 - <<'PY'
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
env.get_template('dashboard.html')
print('dashboard-template-ok')
PY
```

```bash
cd /home/radxa/nas102/cubie-nas
JWT_SECRET=dev-local-secret python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

```bash
curl -sS -i --cookie "access_token=fake" http://127.0.0.1:8899/dashboard | head -n 40
```

## Files Changed

| File | Change |
|------|--------|
| `/home/radxa/nas102/cubie-nas/templates/dashboard.html` | Converted to base-layout dashboard with 5 rigid panels and panel scroll wrappers |
| `/home/radxa/nas102/cubie-nas/static/css/router.css` | Added rigid dashboard grid, sticky topbar, overflow controls, sticky table headers, consistent spacing/controls |
| `/home/radxa/nas102/cubie-nas/static/js/app.js` | Removed duplicate theme/logout listeners and guarded drop-zone binding |
| `/home/radxa/nas102/cubie-nas/app/main.py` | Passed `page='dashboard'` for nav state and shell consistency |

## Verification

```bash
python3 -m pytest -q tests/
```

**Expected output:**
- All tests pass (current baseline: `22 passed`).

```bash
python3 - <<'PY'
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
env.get_template('dashboard.html')
print('dashboard-template-ok')
PY
```

**Expected output:**
- `dashboard-template-ok`

```bash
curl -sS -i --cookie "access_token=fake" http://127.0.0.1:8899/dashboard | head -n 20
```

**Expected output:**
- `HTTP/1.1 200 OK`
- HTML includes `body data-page="dashboard"` and links `/static/css/router.css`.

## Rollback Steps

1. Revert `templates/dashboard.html` to standalone layout.
2. Revert dashboard-specific CSS block from `static/css/router.css`.
3. Restore removed `theme-toggle`/`logout-btn` listeners in `static/js/app.js`.
4. Revert dashboard route context change in `app/main.py`.
5. Re-run test suite and route checks.

## Risks / Gotchas

- Dashboard now depends on base shell (`router.css` + `router.js`) by design.
- Table action columns may still require horizontal scroll in very narrow widths; wrappers intentionally keep page overflow off.
- Keep panel count/structure stable to preserve rigid admin-layout behavior.

## Standard Rigid Layout Rules (for future contributors)

### Chosen layout approach

- **Primary:** CSS Grid for dashboard panel placement.
- **Secondary:** Flex only inside controls rows and panel internals.

### CSS rules checklist

- Use a single app shell (`base.html`) for all authenticated pages.
- No standalone dashboard stylesheet for authenticated views.
- `html, body` must enforce `overflow-x: hidden`.
- Dashboard panel containers must use fixed internal scroll regions for tables/lists.
- Keep consistent card radius, border, shadow, and padding across panels.
- Keep button minimum height and typography consistent.
- Use sticky table headers inside scroll containers.

### Responsive breakpoints used

- `>1580px`: 5-column dashboard row.
- `<=1580px`: 3-column wrap.
- `<=1220px`: 2-column wrap.
- `<=860px`: 1-column stack (tablet/small laptop fallback).

### Common pitfalls

- Mixing multiple layout shells for authenticated pages.
- Auto-fit grids without min/max constraints causing uneven panel widths.
- Missing `min-width: 0` in grid/flex children.
- Global page scrolling from large tables instead of panel scroll.
- Duplicate JS handlers for shared controls (theme/logout).

## References

- `templates/base.html`
- `templates/dashboard.html`
- `static/css/router.css`
- `static/js/app.js`
- `kb/TEMPLATE.md`

---

### Update 2026-02-15

- Split dashboard features into dedicated navigation pages to match router-admin IA:
	- `dashboard` now contains only **User Management**.
	- Added `/files` page for **File Manager**.
	- Added `/services` page for **Services**.
	- Storage remains under `/storage` as connected drives panel.
- Updated sidebar navigation in `templates/base.html` to include File Manager and Services tabs.
- Moved File Manager/Services/User action handlers into `static/js/router.js` and initialized by `data-page` to avoid cross-page script coupling.

---

### Update 2026-02-15

- Expanded module-oriented IA with explicit pages and nav entries for:
	- `/users` (app/system user management + active sessions)
	- `/logs` (service log reader for `cubie-nas`)
	- `/settings` (UI + service health snapshot)
- Changed `/dashboard` from a legacy page endpoint to redirect into `/overview`, avoiding duplicate landing semantics.
- Added backend API endpoint `GET /api/system/logs` (admin-only, bounded lines range) to safely expose recent `journalctl` entries for UI consumption.
- Updated frontend page bootstrap in `static/js/router.js`:
	- `users` page now initializes session loader.
	- Added `loadLogsPage()` with bounded line selector and error fallback.
	- Added `loadSettingsPage()` to show current theme and backend/network-health checks.

- Files touched in this update:
	- `/home/radxa/nas102/cubie-nas/app/main.py`
	- `/home/radxa/nas102/cubie-nas/app/routers/system.py`
	- `/home/radxa/nas102/cubie-nas/templates/base.html`
	- `/home/radxa/nas102/cubie-nas/templates/users_page.html`
	- `/home/radxa/nas102/cubie-nas/templates/logs_page.html`
	- `/home/radxa/nas102/cubie-nas/templates/settings_page.html`
	- `/home/radxa/nas102/cubie-nas/static/js/router.js`

- Verification commands used:
	- `PYTHONPATH=. pytest -q` → expected `22 passed`
	- `PYTHONPATH=. python -m compileall app templates static/js` → expected successful listing without syntax errors

---

### Update 2026-02-15

- Fixed blank data on **General Info** and **Storage** pages after session/token churn.

- Root cause:
	- page routes only checked for cookie presence, not token validity
	- stale/invalid cookie allowed page HTML render, but API calls returned `401`, so panels appeared empty

- Final fix:
	1. Hardened route gate in `app/main.py` `_require_login()` to validate JWT and active user before rendering page.
	2. Added frontend `401` handling in `static/js/router.js` `api()` to redirect to `/` on expired/invalid session.
	3. Added explicit error/status handling for `loadGeneralPage()` and `loadStoragePage()` so failures show clear feedback instead of silent blanks.
	4. Added mass-market UX polish for storage:
		- summary cards (total/mounted/USB/NVMe)
		- quick filter (all/mounted/USB/NVMe)
		- search by name/device
	5. Added General page snapshot header with refresh timestamp.

- Files changed in this update:
	- `/home/radxa/nas102/cubie-nas/app/main.py`
	- `/home/radxa/nas102/cubie-nas/static/js/router.js`
	- `/home/radxa/nas102/cubie-nas/templates/general.html`
	- `/home/radxa/nas102/cubie-nas/templates/storage_page.html`

- Verification used:
	- `PYTHONPATH=. pytest -q` → `22 passed`
	- `PYTHONPATH=. python -m compileall app static/js templates` → no compile errors
	- Runtime API checks:
		- valid login: `/api/system/general-info` = `200`, `/api/storage/drives` = `200`
		- stale token on pages: `/general` = `307`, `/storage` = `307` (redirect to login)
