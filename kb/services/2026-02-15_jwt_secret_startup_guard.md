## Title

Fail fast on insecure default JWT secret at application startup

## Date

2026-02-15

## Category

services

## Tags

jwt, security, startup, configuration, env, fail-fast

## Environment

- **Device/Board:** Cubie A5E (ARM64)
- **OS:** Debian/Ubuntu (Linux)
- **Kernel:** `uname -r`
- **Repo branch:** `main`
- **Service version:** `git rev-parse --short HEAD`

## Problem Statement

Application startup allowed `jwt_secret='change-me'` when `.env` was missing or incomplete, leaving token signing predictable.

## Symptoms

- Service starts successfully even when `JWT_SECRET` is not configured.
- JWT tokens are signed with a known default secret.

## Root Cause

`app/config.py` defines a fallback default (`change-me`) and `app/main.py` startup had no guard to reject this insecure configuration.

## Fix

1. Add a startup guard in `app/main.py` before any initialization side effects.
2. Raise `RuntimeError` when `settings.jwt_secret == 'change-me'`.
3. Add startup tests to verify reject/allow behavior.

## Commands

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/test_startup_jwt_secret.py
```

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

## Files Changed

| File | Change |
|------|--------|
| `/home/radxa/nas102/cubie-nas/app/main.py` | Added startup guard that rejects insecure default JWT secret |
| `/home/radxa/nas102/cubie-nas/tests/test_startup_jwt_secret.py` | Added tests for startup reject (default secret) and allow (non-default secret) |

## Verification

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/test_startup_jwt_secret.py
```

**Expected output:**
- `2 passed`

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

**Expected output:**
- All tests pass (current baseline includes `17 passed`).

## Rollback Steps

1. Revert `app/main.py` startup guard change.
2. Remove `tests/test_startup_jwt_secret.py`.
3. Re-run test suite to confirm baseline behavior restored.

## Risks / Gotchas

- Deployments that rely on implicit default secret will now fail to start until `JWT_SECRET` is set in `.env`.
- This is an intentional security break-glass behavior.

## References

- `app/config.py`
- `app/main.py`
- `tests/test_startup_jwt_secret.py`
- `kb/TEMPLATE.md`
