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
