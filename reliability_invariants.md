# Cubie NAS — Reliability Invariants

**Status:** ENFORCED
**Scope:** All runtime operations that modify system state.
**These invariants are non-negotiable. Code that violates them is defective.**

---

## Invariant 1: Config Edits Must Be Atomic and Durable

**Statement:**
Every write to a configuration file that the system depends on at boot or runtime must be atomic (all-or-nothing) and durable (survives immediate power loss).

**Implementation requirements:**
1. Write to a temporary file in the same directory as the target.
2. `fsync` the file descriptor after writing.
3. `os.replace()` the temp file onto the target (atomic rename).
4. `fsync` the parent directory file descriptor (persists the directory entry).
5. Remove the temp file on any failure path.

**Governed files:**
- `/etc/fstab`
- `/etc/samba/smb.conf`
- `/etc/network/interfaces.d/*`
- `/etc/cubie-nas/*`

**Authoritative implementation:** `_atomic_write_text()` in `app/services/usb_share.py`

**Violation examples:**
- `Path.write_text(content)` on any governed file.
- `open(path, 'w').write(content)` without fsync and atomic rename.
- `shutil.copy2()` for backup or restore of governed files.

---

## Invariant 2: Provisioning Must Be Transactional

**Statement:**
Storage provisioning operations must execute as an ordered sequence of steps, where each state-modifying step has a registered rollback action. If any step fails, all previously completed steps must be rolled back in reverse order.

**Execution model:**
```
validate → preflight → mount → verify → chown → fstab → smb → testparm → enable → restart
```

Each step is a `TransactionStep` with:
- `action()` — performs the operation, returns `(ok, message)`.
- `rollback()` — reverses the operation if a later step fails.

**Authoritative implementation:** `TransactionRunner` in `app/services/transaction.py`

**Invariant guarantees:**
- A failed provisioning leaves the system in the same state as before the attempt.
- fstab and smb.conf are restored from atomic backups on rollback.
- The mount is undone (`umount`) on rollback.
- No partial provisioning state persists.

**Violation examples:**
- Adding a transaction step without a rollback action when it modifies state.
- Modifying fstab before mounting (wrong step order).
- Skipping `testparm` validation after smb.conf update.

---

## Invariant 3: No Destructive Operation Without Confirmation and Backup

**Statement:**
No operation that destroys, overwrites, or irreversibly modifies existing data may execute without:
1. Explicit user confirmation (for destructive storage operations).
2. A durable backup of the prior state (for config modifications).

### 3a: Storage Destruction

Wipe-and-repartition requires exact text confirmation:
```
WIPE /dev/<device> (<model> <size>)
```

The confirmation string is constructed server-side and must match exactly. No fuzzy matching. No auto-confirmation.

### 3b: Config Backup

Before modifying `/etc/fstab` or `/etc/samba/smb.conf`:
1. `_backup_file()` creates a `.cubie-nas.bak` copy using `_atomic_copy_file()`.
2. The backup is durable (fsynced) before the original is modified.
3. On rollback, `_restore_file()` atomically copies the backup back.

**Violation examples:**
- Formatting a device without wipe confirmation text match.
- Modifying fstab without calling `_backup_file()` first.
- Deleting backup files before the transaction completes.

---

## Invariant 4: OS Disk Must Never Be Provisioned

**Statement:**
The device hosting the operating system root filesystem must never be formatted, partitioned, wiped, or mounted as a NAS share.

**Detection method:**
1. `findmnt -nr -o SOURCE /` identifies the root source device.
2. `lsblk -no PKNAME <root_source>` identifies the parent disk.
3. The target device is compared against both the root partition and root disk.

**Rejection condition:**
```python
if device == root_src or device == os_disk:
    return False, 'Selected device is the OS disk'
```

**Authoritative implementation:** `_preflight_device()` in `app/services/usb_share.py`

**This check must never be removed, weakened, or made optional.**

---

## Invariant 5: Mountpoints Must Be Contained

**Statement:**
All NAS share mountpoints must resolve to a path strictly under `/srv/nas`. No path traversal, symlink escape, or non-canonical path may bypass this containment.

**Validation method:**
```python
target_mount_resolved = Path(target_mount).resolve(strict=False)
nas_root = Path('/srv/nas').resolve(strict=False)
if nas_root not in [target_mount_resolved, *target_mount_resolved.parents]:
    return False, 'Mountpoint must be under /srv/nas'
```

**Violation examples:**
- Accepting `../../etc` as a mountpoint component.
- Allowing symlinks that resolve outside `/srv/nas`.
- Skipping `Path.resolve()` before containment check.

---

## Invariant 6: Post-Operation Verification

**Statement:**
After every mount operation, the system must verify that:
1. The target mountpoint is active (confirmed via `findmnt`).
2. The mounted device UUID matches the expected UUID.

Verification failure triggers full transaction rollback.

**Authoritative implementation:** `_verify_mount()` in `app/services/usb_share.py`

**This verification must occur before config commits (fstab/smb.conf writes).**

---

## Invariant 7: Command Execution Isolation

**Statement:**
All system command execution must go through `app/services/system_cmd.py`. No other module may directly invoke `subprocess`, `os.system()`, `os.popen()`, or `asyncio.create_subprocess_exec()`.

**Guarantees provided by the abstraction:**
- Enforced timeout on every command.
- Structured `CommandResult` return type.
- Retry support with configurable policy.
- Testability via `MockCommandRunner` substitution.

---

## Invariant 8: Concurrency Protection

**Statement:**
Only one storage provisioning operation may execute at a time. Concurrent provisioning requests must be rejected immediately with a clear error message.

**Implementation:** `asyncio.Lock` (`_PROVISION_LOCK`) with pre-acquisition check:
```python
if _PROVISION_LOCK.locked():
    return False, 'Another provisioning operation is already in progress'
async with _PROVISION_LOCK:
    ...
```

**Limitation:** This lock is process-local. It does not protect against concurrent provisioning across multiple Uvicorn workers. The systemd service must run a single worker.

---

## Invariant 9: Sandbox Boundary Enforcement

**Statement:**
The application process must not have write access to any filesystem path outside the explicitly declared `ReadWritePaths` in the systemd unit.

**Declared writable paths:**
```
/opt/cubie-nas
/var/lib/cubie-nas
/srv/nas
/etc/samba
/etc/fstab
/etc/cubie-nas
/etc/network/interfaces.d
```

All other paths (including `/home`, `/root`, `/usr`, `/var`, `/tmp` outside `PrivateTmp`) are read-only or inaccessible.

**When adding a new writable path:**
1. Update `ReadWritePaths=` in `systemd/cubie-nas.service`.
2. Update the expected paths in `tests/test_systemd_service_security.py`.
3. Document the reason in the commit message.

---

## Enforcement

These invariants are enforced by:

| Layer | Mechanism |
|-------|-----------|
| Code | Safety checks in `usb_share.py` and `file_ops.py` |
| Tests | `tests/test_usb_share_safety.py`, `tests/test_systemd_service_security.py` |
| Runtime | systemd `ProtectSystem=strict` sandbox |
| Process | AI engineering policy in `copilotinstructions.md` |
| Review | Developer audit requirement for safety-critical files |

**No invariant may be weakened without explicit written approval from the project maintainer.**

---

*This document defines system laws. It is referenced by copilotinstructions.md and DEVELOPMENT_WORKFLOW.md.
Update this document when architecture changes invalidate or extend these invariants.*
