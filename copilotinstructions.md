# Cubie NAS — AI Engineering Policy

**Enforcement level:** MANDATORY for all AI coding agents (Codex, Copilot, Claude, etc.)
**Scope:** All code changes to this repository.
**Violation of any rule in this document is a shipping-blocking defect.**

---

## 1. Project Philosophy

Cubie NAS is a reliability-first network-attached storage appliance.

### Design Principles

1. **Data safety over performance.** Every operation that touches user data, system config, or storage must be crash-safe. Never optimize away a safety check.
2. **Explicit over clever.** Prefer readable, predictable code. No metaprogramming, no magic mocking, no dynamic dispatch for system operations.
3. **Fail loud, recover clean.** Every failure must produce a user-readable error, log the cause, and leave the system in a known-good state.

### Data Durability Guarantees

- All config file writes (fstab, smb.conf, network interfaces) must survive power loss at any point during the write.
- Backup files must be durable before the original is modified.
- No operation may leave a half-written file on disk.

### Transactional Provisioning

Storage provisioning follows an invariant execution model:

```
validate → preflight → execute → verify → commit
```

Each step that modifies state must have a corresponding rollback step.
The `TransactionRunner` in `app/services/transaction.py` enforces this.

---

## 2. Storage Safety Rules

### 2.1 Atomic File Write Requirements

Every write to a system config file MUST use `_atomic_write_text()` from `app/services/usb_share.py` or an equivalent implementation that:

1. Creates a temp file in the **same directory** as the target (same filesystem guarantee).
2. Writes content, calls `flush()`, then `os.fsync(fd)`.
3. Calls `os.replace(tmp, target)` for atomic rename.
4. Opens the parent directory read-only and calls `os.fsync(dir_fd)` to persist the directory entry.
5. Cleans up the temp file on any exception.

**Violation:** Using `Path.write_text()`, `open(path, 'w').write()`, or `shutil.copy2()` for any file under `/etc/` or any config the system depends on.

### 2.2 Atomic File Copy Requirements

File copies for backup or restore MUST use `_atomic_copy_file()` which follows the same temp-file → fsync → replace → dir-fsync pattern.

**Violation:** Using `shutil.copy()`, `shutil.copy2()`, or `shutil.copyfile()` for any config backup or restore operation.

### 2.3 Rollback Guarantees

- `_backup_file()` must be called before any config modification.
- `_restore_file()` must be wired as the rollback action in the transaction step.
- Backup files use the `.cubie-nas.bak` suffix.
- Rollback must restore the exact prior content atomically.

### 2.4 OS Disk Protection

`_preflight_device()` MUST reject any device that resolves to the OS root disk. This check compares:
- `device == root_source` (the partition mounted at `/`)
- `device == os_disk` (the parent disk of the root partition)

**Never remove, weaken, or skip this check.**

### 2.5 Mount Validation

After every mount operation, `_verify_mount()` MUST confirm:
1. The target mountpoint is active (via `findmnt`).
2. The mounted device UUID matches the expected UUID.

Post-mount verification failure MUST trigger full rollback.

### 2.6 Mountpoint Containment

All provisioned mountpoints MUST resolve to a path under `/srv/nas`. Path traversal via `..`, symlinks, or non-canonical paths is rejected by `Path.resolve(strict=False)` comparison against the NAS root.

---

## 3. Command Execution Rules

### 3.1 Mandatory Abstraction

All system shell commands MUST go through `app/services/system_cmd.py`.
The `RealCommandRunner` class is the only authorized way to execute external processes.

**Violation:** `subprocess.run()`, `subprocess.Popen()`, `os.system()`, `os.popen()`, or `asyncio.create_subprocess_exec()` called from anywhere other than `system_cmd.py`.

### 3.2 CommandRunner Protocol

Every command invocation returns a `CommandResult` with:
- `success: bool`
- `stdout: str`
- `stderr: str`
- `exit_code: int`
- `execution_time: float`

Callers MUST check `exit_code` or `success` before proceeding.

### 3.3 Timeout Policy

- All commands are subject to `settings.command_timeout_sec` (default: 20s, max: 300s).
- Timeout produces `exit_code=124` and is retryable per `RetryPolicy`.
- No command may run without a timeout.

### 3.4 Testability

All service functions that run commands MUST accept a `runner: CommandRunner` parameter (or use dependency injection) so tests can substitute `MockCommandRunner`.

---

## 4. Configuration File Editing Rules

### 4.1 Files Governed by These Rules

| File | Editor Function |
|------|----------------|
| `/etc/fstab` | `_upsert_fstab()` |
| `/etc/samba/smb.conf` | `_upsert_samba_share()` |
| `/etc/network/interfaces.d/*` | `apply_network_config()` |

### 4.2 Mandatory Edit Sequence

For every config file edit:

1. **Backup** the original using `_backup_file()` (atomic copy).
2. **Write** the new content using `_atomic_write_text()`.
3. **Validate** the result (e.g., `testparm -s` for Samba).
4. **Rollback** on validation failure using `_restore_file()`.

### 4.3 Parent Directory Fsync

After every `os.replace()` call, the parent directory MUST be fsynced. This ensures the rename operation (directory entry update) is durable on ext4, XFS, and btrfs.

### 4.4 Temp File Placement

Temp files MUST be created in the same directory as the target file (via `tempfile.mkstemp(dir=...)`) to guarantee `os.replace()` is an atomic same-filesystem rename.

---

## 5. Deployment Rules

### 5.1 Environment Separation

| Path | Purpose | Writable at runtime |
|------|---------|-------------------|
| `/home/radxa/nas102/cubie-nas` | Development workspace | Yes (developer) |
| `/opt/cubie-nas` | Production runtime | Yes (service) |

The systemd service runs exclusively from `/opt/cubie-nas`.
Development changes have no effect until synced.

### 5.2 Deployment Command

```bash
sudo rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.env' \
  /home/radxa/nas102/cubie-nas/ /opt/cubie-nas/
sudo systemctl restart cubie-nas
```

### 5.3 Forbidden Rsync Patterns

**Never sync these to production:**
- `.env` — contains `JWT_SECRET` and runtime secrets.
- `.venv` — must be built in-place at `/opt/cubie-nas`.
- `.git` — development metadata.
- `__pycache__` — bytecode from wrong Python path.

### 5.4 Post-Deploy Verification

After every deployment:
1. `sudo systemctl status cubie-nas` — confirm service is active.
2. `curl -k https://localhost:8443/healthz` — confirm HTTP response.
3. `sudo journalctl -u cubie-nas --since '1 min ago'` — confirm no startup errors.
4. Run `pytest -q tests/` from the workspace to confirm tests still pass.

---

## 6. Security Rules

### 6.1 No Default Secrets in Production

`jwt_secret` in `app/config.py` defaults to `'change-me'`.
The production `.env` MUST override this. AI agents MUST NOT hardcode secrets or generate weak defaults.

### 6.2 Systemd Sandbox Compliance

The service runs under `ProtectSystem=strict` with explicit `ReadWritePaths`:

```
/opt/cubie-nas
/var/lib/cubie-nas
/srv/nas
/etc/samba
/etc/fstab
/etc/cubie-nas
/etc/network/interfaces.d
```

**Any new feature that writes to a path not in this list will fail at runtime.**
When adding a new writable path, update `systemd/cubie-nas.service` AND the test in `tests/test_systemd_service_security.py`.

### 6.3 Path Traversal Protection

- `FileOps.safe_path()` in `app/services/file_ops.py` resolves and validates all user-supplied paths.
- NAS file operations MUST NOT accept absolute paths from user input.
- Mountpoint provisioning validates containment under `/srv/nas` using `Path.resolve()`.

### 6.4 CSRF Protection

All mutation endpoints (POST, PUT, DELETE) MUST validate the `X-CSRF-Token` header.
AI agents MUST NOT remove or bypass CSRF middleware.

### 6.5 Authentication

- JWT tokens are signed with `settings.jwt_secret`.
- Cookie-based auth via `access_token` cookie.
- AI agents MUST NOT weaken token validation or add unauthenticated mutation endpoints.

---

## 7. Testing Requirements

### 7.1 Test Infrastructure

- Framework: `pytest` + `pytest-asyncio`
- Mock strategy: `MockCommandRunner` for all system command tests
- Path isolation: `MappedPath` fixture redirects `/srv/nas` and `/etc/` to `tmp_path`

### 7.2 Required Test Coverage

Every change to storage or config-editing code MUST include tests for:

1. **Happy path** — operation succeeds, state is correct.
2. **Failure + rollback** — operation fails mid-way, prior state is restored.
3. **Durability** — `os.fsync` is called for both file content and parent directory.
4. **Input validation** — bad inputs are rejected before any state change.

### 7.3 Provisioning Flow Tests

The following scenarios MUST have test coverage:

| Scenario | Test File |
|----------|-----------|
| Successful provisioning | `test_usb_share.py` |
| Command failure → rollback | `test_usb_share.py` |
| Invalid device path | `test_usb_share.py` |
| Mount failure | `test_usb_share.py` |
| Config rollback on testparm failure | `test_usb_share_config_rollback.py` |
| OS disk rejection | `test_usb_share_safety.py` |
| Concurrency lock rejection | `test_usb_share_safety.py` |
| Atomic write durability | `test_usb_share_atomic_write.py` |
| Atomic backup/restore durability | `test_usb_share_atomic_write.py` |
| Systemd sandbox directives | `test_systemd_service_security.py` |

### 7.4 Test Execution

```bash
python3 -m pytest -q tests/
```

All tests MUST pass before deployment. No skipped tests without documented justification.

---

## 8. AI Editing Restrictions

### 8.1 Never Bypass the Provisioning Safety Layer

The provisioning flow in `_provision_block_share_impl()` contains these safety gates:

- Device path validation
- Share name sanitization
- Mountpoint containment check
- OS disk preflight rejection
- Concurrency lock
- Post-mount UUID verification
- Transaction-based rollback

**AI agents MUST NOT remove, reorder, or skip any of these gates.**

### 8.2 Never Modify Storage Flows Without Tests

Any change to functions in `app/services/usb_share.py` that affect:
- Partitioning, formatting, mounting, or unmounting
- fstab or smb.conf editing
- Backup or restore logic
- Transaction step ordering

MUST include corresponding test updates. Changes without tests will be rejected.

### 8.3 Never Introduce Direct Filesystem Writes

Config file writes MUST use `_atomic_write_text()` or `_atomic_copy_file()`.
AI agents MUST NOT introduce:
- `Path.write_text()`
- `open(f, 'w').write()`
- `shutil.copy2()`
- `shutil.copyfile()`

for any file that the system depends on at boot or runtime.

### 8.4 Never Refactor Destructive Operation Ordering

The sequence: `validate → preflight → execute → verify → commit` is load-bearing.
AI agents MUST NOT rearrange transaction steps, merge validation with execution, or remove post-execution verification.

### 8.5 Favor Explicit Over Abstract

- Do not extract helpers that obscure the safety flow.
- Do not introduce decorators for error handling in provisioning.
- Do not replace explicit rollback wiring with generic retry logic.

---

## 9. Review Workflow

### 9.1 Required Audit Before Merge

Every change to the following files requires explicit developer review:

| File | Review Reason |
|------|---------------|
| `app/services/usb_share.py` | Storage provisioning safety |
| `app/services/transaction.py` | Rollback correctness |
| `app/services/system_cmd.py` | Command execution abstraction |
| `app/services/network.py` | Network config writes |
| `app/config.py` | Security-sensitive settings |
| `app/security.py` | Authentication and token logic |
| `systemd/cubie-nas.service` | Sandbox and resource limits |

### 9.2 AI Agent Role Separation

| Role | Scope | Restrictions |
|------|-------|-------------|
| **Code generation** (Codex, Copilot) | Feature implementation, bug fixes | Must follow all rules in this document |
| **Architecture audit** (Opus-class) | Safety review, risk analysis | Read-only analysis; changes require developer approval |
| **Automated testing** (any agent) | Test creation and execution | Must not modify production code to make tests pass |

### 9.3 When Unsure

If an AI agent cannot determine whether a change is safe:
- **Stop and ask the developer.**
- Do not guess at system behavior.
- Do not assume a path is writable.
- Do not assume a command is idempotent.

---

## Agent Standing Instructions

- Stack: FastAPI + Jinja2 + vanilla JS, ARM64 Debian, 1GB RAM
- RAM budget: server must stay under 300MB (MemoryMax=300M in systemd)
- After every change: `sudo systemctl restart cubie-nas && sleep 5 && sudo systemctl is-active cubie-nas` — must return `active`
- No npm, no build steps, no new systemd services
- CDN JS only from cdn.jsdelivr.net with pinned versions
- All CSS in static/css/style.css, under 30KB
- Commit after each task: `feat(taskN.N): description`
- On failure: read `journalctl -u cubie-nas -n 50 --no-pager` and fix before continuing
- Full prompt reference: see TASKS.md

---

*This document is the authoritative engineering policy for AI-assisted development on Cubie NAS.
It supersedes informal instructions and must be updated when architecture changes.*
