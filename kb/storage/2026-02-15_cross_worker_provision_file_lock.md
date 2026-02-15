## Title

Add filesystem advisory lock to prevent cross-worker concurrent provisioning

## Date

2026-02-15

## Category

storage

## Tags

provisioning, concurrency, flock, uvicorn, lock, safety

## Environment

- **Device/Board:** Cubie A5E (ARM64)
- **OS:** Debian/Ubuntu Linux
- **Kernel:** `uname -r`
- **Repo branch:** `main`
- **Service version:** `git rev-parse --short HEAD`

## Problem Statement

`_PROVISION_LOCK` was process-local (`asyncio.Lock`) and did not prevent concurrent provisioning across multiple worker processes.

## Symptoms

- In multi-worker deployments, two provisioning requests could execute concurrently.
- Existing lock protection only blocked parallel requests inside one process.

## Root Cause

`asyncio.Lock` does not coordinate between OS processes. No filesystem-level advisory lock existed.

## Fix

1. Keep existing `_PROVISION_LOCK` for in-process serialization.
2. Add non-blocking filesystem advisory lock (`fcntl.flock`) around provisioning execution.
3. Return the existing in-progress error when advisory lock cannot be acquired.
4. Release advisory lock in `finally` to guarantee cleanup.

## Commands

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/test_usb_share_safety.py
```

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

## Files Changed

| File | Change |
|------|--------|
| `/home/radxa/nas102/cubie-nas/app/services/usb_share.py` | Added advisory file-lock acquire/release helpers and wrapped `provision_block_share()` execution with cross-process lock |
| `/home/radxa/nas102/cubie-nas/tests/test_usb_share_safety.py` | Added lock exclusivity, lock-acquire failure, and release-on-exit tests |

## Verification

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/test_usb_share_safety.py
```

**Expected output:**
- `5 passed`

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

**Expected output:**
- All tests pass (current baseline: `20 passed`).

## Rollback Steps

1. Remove advisory lock helpers from `usb_share.py`.
2. Restore `provision_block_share()` to only use `_PROVISION_LOCK`.
3. Remove advisory lock tests from `tests/test_usb_share_safety.py`.
4. Re-run full tests.

## Risks / Gotchas

- Advisory locks require both processes to cooperate using `flock`; non-cooperating external tools are not blocked.
- In non-root or restricted environments, primary lock path may be unwritable; fallback lock path is used.

## References

- `app/services/usb_share.py`
- `tests/test_usb_share_safety.py`
- `kb/TEMPLATE.md`
