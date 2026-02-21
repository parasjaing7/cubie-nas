# Development Log

## 2026-02-21T06:20:52+00:00

### Progress
- Completed Task 5.1: global exception fallback, dashboard skeleton loading states, form busy states, and destructive-action confirmations.
- Completed Task 5.2: Syncthing backup status integration (`/api/monitor/syncthing/status`) and dashboard Backup card.
- Completed Task 5.3: final memory audit across required scenarios; documented measurements in `README.md`.
- Fixed persistent blank dashboard/tab issue by adding app-ready script initialization gating and updating CSP compatibility for current frontend patterns.
- Added clean session reset behavior (`/logout`) and improved root redirect behavior to avoid stale-cookie auto-redirect confusion.
- Refined System Health visuals: CPU/RAM pie redesign, temperature thermometer style, and typography consistency for readings.

### Issues
- Browser UI showed persistent skeleton/loading state despite successful login.
- Runtime `/opt/cubie-nas` occasionally lagged in accepting connections immediately after restart, causing brief `Connection refused` checks.
- Frontend helper init race: inline page scripts could execute before base helper functions were ready.
- CSP policy blocked inline scripts at one stage, preventing data-fetch/render execution on content-heavy pages.

### Lessons Learned
- Keep runtime (`/opt`) and workspace (`/home/...`) synced before diagnosing frontend/backend mismatch symptoms.
- For template-heavy apps with inline scripts, use a deterministic app-ready hook to avoid load-order races.
- Validate CSP against real app execution paths (inline script usage and `ws://`/`wss://` requirements) before tightening policy.
- When troubleshooting UI blank states, verify exact dependency chain quickly: auth cookie -> API responses -> WS handshake -> browser script execution order.

### Summary
- Current state is stable: service restarts cleanly, health checks pass, dashboard data dependencies are reachable, and latest UI updates are deployed.

## 2026-02-21T08:58:02+00:00

### Latest Issues
- Dashboard showed `Overview load failed: Maximum call stack size exceeded` after a few seconds, and Storage/Services cards fell back to empty states (`No mounted devices detected`, `No services`).
- After the recursion fix, a follow-up UI error appeared: `Overview load failed: Cannot set properties of null (setting 'textContent')`.
- Some clients continued to run stale frontend assets due to browser caching, making behavior inconsistent across refreshes.

### Fixes Applied
- Fixed router API recursion by preserving the base API function and delegating safely:
	- Added `window.__baseApi = window.api` in `templates/base.html`.
	- Updated `static/js/router.js` to call `window.__baseApi` first instead of dynamically resolving to self.
- Forced frontend cache invalidation by bumping asset versions in `templates/base.html`:
	- `style.css?v=20260221b`
	- `router.js?v=20260221b`
- Prevented legacy overview loader from running on the new dashboard template:
	- Guarded `loadOverviewPage()` call in `static/js/router.js` behind `document.getElementById('ov-services-body')` presence check.
- Deployed to runtime (`/opt/cubie-nas`) with `scripts/deploy-safe.sh`, restarted `cubie-nas`, and verified health/API polling stability.

### Lessons Learned
- In browser JS, function hoisting can invalidate naive “capture once” assumptions; preserve critical global handlers explicitly (for example `window.__baseApi`) before other scripts run.
- Mixed legacy and new page bootstraps should use element-presence guards to avoid null DOM writes when templates evolve.
- When user symptoms differ from server-side API checks, treat frontend cache/versioning as a first-class suspect and ship explicit cache-busting.
- End-to-end verification should include repeated polling rounds, not only single endpoint checks, because several regressions surfaced after initial successful render.

### Summary
- Runtime is now stable for dashboard use: cards stay populated, APIs remain `200` under repeated polling, and both recursion and null-element overview errors are resolved in deployed code.
