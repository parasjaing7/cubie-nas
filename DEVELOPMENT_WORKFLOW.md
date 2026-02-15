# Development Workflow

This document describes the standard development workflow for Cubie NAS.

## Prerequisites

- Linux host with systemd
- Python 3.10+
- Node.js not required

## Repo Layout

- app/ - FastAPI backend and services
- templates/ - Jinja templates
- static/ - CSS and JS assets
- systemd/ - service unit file
- scripts/ - helper scripts

## Local Development

1. Create a virtual environment and install dependencies:
   - `python3 -m venv .venv`
   - `. .venv/bin/activate`
   - `pip install -r requirements.txt`

2. Start the server (dev):
   - `uvicorn app.main:app --host 0.0.0.0 --port 8443 --proxy-headers`

3. Access UI:
   - `https://<device-ip>:8443`

## Production Service (systemd)

- Status: `sudo systemctl status cubie-nas`
- Restart: `sudo systemctl restart cubie-nas`
- Logs: `sudo journalctl -u cubie-nas -f`

## Deployment to /opt

The systemd service runs from `/opt/cubie-nas`.

Sync workspace to /opt and restart:

```
sudo rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude '.git' --exclude 'node_modules' --exclude '.env' /home/radxa/nas102/cubie-nas/ /opt/cubie-nas/
sudo systemctl restart cubie-nas
```

Note: `.env` is excluded to avoid overwriting secrets.

## UI Change Checklist

After any UI change:

1. Sync to `/opt` and restart.
2. Hard refresh browser.
3. Verify:
   - data rendering
   - navigation
   - responsive layout
   - WebSocket updates

## Storage Operations Guidelines

Storage operations must follow the safety rules in .github/copilot-instructions.md.

- Use service-layer functions only (app/services/*).
- All system commands go through system_cmd.py.
- Preserve the destructive flow order: validate → plan → execute → verify → commit.
- Require explicit user confirmation before any destructive action.
- Always support rollback for config changes (fstab, smb.conf).
- Log operation start, command execution, results, failures, and rollback attempts.

## UI Testing Process

For any UI change, do the following:

1. Sync to /opt and restart the service.
2. Hard refresh the browser (Ctrl+Shift+R).
3. Validate rendering for:
   - General Info
   - Storage
   - Network Settings
   - NAS Management
   - Dashboard (User Management)
4. Validate WebSocket updates on the dashboard and General Info.
5. Check responsive layout on mobile and tablet widths.
6. Verify navigation links and CSRF-protected actions.

## Release Checklist

- Sync code to /opt with .env preserved.
- Restart service and verify systemd health.
- Run pytest and resolve any failures.
- Verify login, logout, and CSRF-protected endpoints.
- Validate storage and NAS flows without data loss.
- Confirm UI renders correctly across all pages.
- Confirm WebSocket monitoring updates.
- Backup /opt/cubie-nas/.env and database before release.

## Reliability Checklist

- Destructive operations require explicit user confirmation.
- Transactions or rollback paths exist for config changes.
- All commands enforce timeouts and propagate errors.
- Service actions log start, command, result, and rollback.
- No direct subprocess usage outside system_cmd.py.
- UI and backend data bindings remain in sync.

## Testing

- Run tests: `pytest -q`
- Prioritize:
  - storage destructive flows
  - config rollback
  - auth and CSRF
  - file upload safety
  - network config validation
  - command execution error handling

## Safety Notes

- Do not change destructive operation order.
- All system operations must use `system_cmd.py`.
- Never perform destructive actions without explicit user confirmation.
