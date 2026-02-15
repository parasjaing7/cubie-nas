## Title

Safe rsync deploy for /opt/cubie-nas (preserve .env and .venv)

## Date

2026-02-15

## Category

git

## Tags

deploy, rsync, systemd, EnvironmentFile, venv, uvicorn

## Environment

- **Device/Board:** Cubie A5E (ARM64)
- **OS:** Debian/Ubuntu Linux
- **Kernel:** `uname -r`
- **Repo branch:** `main`
- **Service version:** `git rev-parse --short HEAD`

## Problem Statement

Service failed after deploy sync because runtime-only files under `/opt/cubie-nas` were deleted.

## Symptoms

- `systemctl` showed repeated auto-restart with `Result: resources`.
- Journal showed:

```text
cubie-nas.service: Failed to load environment files: No such file or directory
cubie-nas.service: Failed to locate executable /opt/cubie-nas/.venv/bin/uvicorn
```

## Root Cause

Deploy used `rsync -a --delete` without excluding runtime artifacts. This removed `/opt/cubie-nas/.env` (required by `EnvironmentFile=`) and `/opt/cubie-nas/.venv` (required by `ExecStart`).

## Fix

1. Restore `/opt/cubie-nas/.env` from `.env.example` and set a strong `JWT_SECRET`.
2. Recreate `/opt/cubie-nas/.venv` and reinstall dependencies.
3. Use safe deploy command with excludes for `.env` and `.venv/`.
4. Restart service and verify active status.

## Commands

```bash
sudo cp /opt/cubie-nas/.env.example /opt/cubie-nas/.env
sudo sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" /opt/cubie-nas/.env
sudo chmod 640 /opt/cubie-nas/.env
```

```bash
sudo python3 -m venv /opt/cubie-nas/.venv
sudo /opt/cubie-nas/.venv/bin/pip install -r /opt/cubie-nas/requirements.txt
```

```bash
cd /home/radxa/nas102/cubie-nas
sudo rsync -a --delete --exclude '.git' --exclude '.env' --exclude '.venv/' --exclude '__pycache__/' ./ /opt/cubie-nas/
sudo systemctl restart cubie-nas
```

## Files Changed

| File | Change |
|------|--------|
| `/home/radxa/nas102/cubie-nas/kb/git/2026-02-15_safe_rsync_deploy_preserve_env_and_venv.md` | Added deploy incident and final working recovery steps |
| `/home/radxa/nas102/cubie-nas/kb/INDEX.md` | Indexed this KB entry |

## Verification

```bash
systemctl is-active cubie-nas
```

**Expected output:**
```text
active
```

```bash
for p in /overview /users /logs /settings; do curl -s -o /dev/null -w "%{http_code}\n" --cookie "access_token=fake" http://127.0.0.1:8443$p; done
```

**Expected output:**
```text
200
200
200
200
```

## Rollback Steps

1. Restore previous `/opt/cubie-nas/.env` from backup if available.
2. Restore previous runtime venv snapshot if your deployment process keeps one.
3. Revert to previous code sync state and restart `cubie-nas`.

## Risks / Gotchas

- Regenerated `JWT_SECRET` invalidates existing sessions.
- `rsync --delete` is dangerous on runtime directories unless excludes are explicit.
- Do not store production `.env` in repository source.

## References

- `kb/TEMPLATE.md`
- `/etc/systemd/system/cubie-nas.service`

---

### Update 2026-02-15

- Added a reusable safe deploy script to enforce this mitigation by default:
	- `/home/radxa/nas102/cubie-nas/scripts/deploy-safe.sh`
- Script behavior:
	- hard-fails if destination `.env`, `.venv`, or `.venv/bin/uvicorn` is missing
	- runs `rsync -a --delete` with enforced excludes for `.env`, `.venv/`, and `__pycache__/`
	- restarts `cubie-nas` and verifies `systemctl is-active` is `active`
	- supports `--dry-run`, `--skip-restart`, and custom `--src/--dest/--service`

- Verification used:
	- `bash -n scripts/deploy-safe.sh`
	- `scripts/deploy-safe.sh --dry-run`
	- `scripts/deploy-safe.sh`

---

### Update 2026-02-15

- Added `Makefile` shortcuts to standardize invocation:
	- `make deploy-safe`
	- `make deploy-safe-dry`
- This reduces operator error by avoiding ad-hoc command typing while still routing through the same guarded deploy script.

- Verification used:
	- `make deploy-safe-dry`
	- `make deploy-safe`
