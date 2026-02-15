## Title

Preserve file permissions in atomic backup/restore copy path

## Date

2026-02-15

## Category

storage

## Tags

atomic-copy, permissions, backup, restore, fstab, samba

## Environment

- **Device/Board:** Cubie A5E (ARM64)
- **OS:** Debian/Ubuntu Linux
- **Kernel:** `uname -r`
- **Repo branch:** `main`
- **Service version:** `git rev-parse --short HEAD`

## Problem Statement

`_atomic_copy_file()` wrote backup/restore targets with tempfile default mode, causing permission drift from source files.

## Symptoms

- Restored files could end up mode `0600` instead of original mode (for example expected `0644`).
- Behavioral difference from prior `shutil.copy2()` semantics for mode preservation.

## Root Cause

The atomic copy logic copied file bytes only and never applied source mode bits to the target temp file before `os.replace()`.

## Fix

1. Read source mode with `stat.S_IMODE(source.stat().st_mode)`.
2. Apply mode to temp destination fd via `os.fchmod(dst.fileno(), source_mode)` before fsync/replace.
3. Add tests for backup and restore permission preservation.

## Commands

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/test_usb_share_atomic_write.py
```

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

## Files Changed

| File | Change |
|------|--------|
| `/home/radxa/nas102/cubie-nas/app/services/usb_share.py` | `_atomic_copy_file()` now preserves source file mode bits using `os.fchmod` |
| `/home/radxa/nas102/cubie-nas/tests/test_usb_share_atomic_write.py` | Added regression tests for backup/restore permission preservation |

## Verification

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/test_usb_share_atomic_write.py
```

**Expected output:**
- `6 passed`

```bash
cd /home/radxa/nas102/cubie-nas
python3 -m pytest -q tests/
```

**Expected output:**
- All tests pass (current baseline: `22 passed`).

## Rollback Steps

1. Revert `_atomic_copy_file()` permission preservation change in `usb_share.py`.
2. Remove the two permission tests from `tests/test_usb_share_atomic_write.py`.
3. Re-run full test suite.

## Risks / Gotchas

- Mode bits are preserved; ownership is unchanged from process effective user (same as current runtime expectations).
- Extended attributes and timestamps are still not copied (same as current atomic copy design).

## References

- `app/services/usb_share.py`
- `tests/test_usb_share_atomic_write.py`
- `kb/TEMPLATE.md`
