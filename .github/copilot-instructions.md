# Cubie NAS — Copilot Engineering Instructions

This project is a reliability-focused NAS management system for the Cubie A5E (ARM64).
Development happens via VS Code Remote SSH on the NAS/server itself.
Copilot must prioritize DATA SAFETY, SYSTEM STABILITY, and UI ↔ BACKEND SYNC over code optimization.

---

## 1. Identity & Context

- This repo manages a Linux-based NAS appliance (Debian/Ubuntu ARM64).
- The runtime environment is a single-board computer accessed exclusively via SSH.
- All system operations (disk, network, services) are executed on the same machine hosting the code.
- The `/kb` directory is the project's long-term memory and canonical knowledge base.
- `copilotinstructions.md` and `reliability_invariants.md` define engineering policy and system laws.

---

## 2. Source of Truth Policy

`/kb` is the canonical memory for this repository.

**Rules:**
1. Before proposing any fix, Copilot MUST search `/kb` for related entries.
2. If a KB entry exists for the issue, propose that fix first.
3. If KB conflicts with Copilot's assumptions, **KB wins**.
4. Never duplicate a fix that already has a KB entry — reference it instead.
5. After every successful fix, Copilot MUST create or update a KB entry (see §4).

---

## 3. Debugging Workflow Policy (MANDATORY)

For every debugging or fix request, Copilot MUST follow this exact sequence:

1. **Categorize** — Identify the likely category: `linux/`, `smb/`, `usb/`, `kernel/`, `uboot/`, `networking/`, `storage/`, `permissions/`, `services/`, `docker/`, `git/`, `troubleshooting/`, `opentap/`, `tools/`.
2. **Search KB** — Check `/kb/<category>/` and `/kb/INDEX.md` for existing entries.
3. **Propose from KB** — If a relevant entry exists, propose that fix first with a reference.
4. **Diagnose** — If no KB entry applies, run safe diagnostic commands only (`uname -a`, `lsblk`, `journalctl`, `dmesg`, `systemctl status`, `ip addr`, `findmnt`, etc.). Never run destructive commands without user confirmation.
5. **Analyze** — Explain findings clearly with exact log lines or output.
6. **Fix** — Apply the minimal, targeted fix.
7. **Verify** — Provide explicit verification commands with expected output.
8. **Summarize** — State root cause and fix in 2-3 lines.
9. **Write KB** — Create or update a KB entry (see §4). This step is **not optional**.

---

## 4. KB Writeback Policy (MANDATORY)

After every successful fix, Copilot MUST:

1. Create a KB entry file under the correct category folder in `/kb/`.
2. Use `/kb/TEMPLATE.md` as the template.
3. Include **only** the final working fix (no trial-and-error).
4. Include verification commands with expected output.
5. Include rollback instructions.
6. Include exact file paths changed.
7. Add the entry to `/kb/INDEX.md`.

**File naming:** `YYYY-MM-DD_short_snake_case_topic.md`
Example: `2026-02-15_usb3_port_not_detected.md`

If a KB entry already exists for the topic, **append a dated update section** instead of overwriting:

```markdown
---

### Update YYYY-MM-DD

- What changed and why.
```

**This policy is non-negotiable. Copilot must not skip KB writeback.**

---

## 5. Anti-Hallucination Rules

Copilot MUST:
- Never invent commands without explaining what they do.
- Never assume distro, kernel version, or architecture without checking (`uname -a`, `lsb_release -a`, `cat /etc/os-release`).
- Prefer diagnostic tools: `dmesg`, `journalctl`, `lsblk`, `findmnt`, `ip addr`, `systemctl status`.
- Never suggest irreversible changes without explicit user confirmation.
- Never fabricate file paths, package names, or config syntax.

---

## 6. Output Format Requirements

When responding to debugging or fix tasks, Copilot MUST:
- Provide all commands in fenced code blocks.
- Provide step-by-step numbered checklists.
- Always include a **Verification** block at the end with commands and expected output.
- When referencing KB entries, link with relative paths: `kb/storage/2026-02-15_topic.md`.

---

## 🚨 CRITICAL RULES (NEVER VIOLATE)

### ❌ Never modify or refactor:

- Disk wipe / partition logic
- fstab editing logic
- Samba config writing logic
- Mount / unmount command sequence
- System service control flows
- Authentication session logic
- CSRF protection
- Command execution abstraction

Unless explicitly requested by developer.

---

### ❌ Never auto replace system shell commands

All system operations MUST go through:

system_cmd.py

Do not introduce direct subprocess calls elsewhere.

---

### ❌ Never change destructive operation order

Storage provisioning must always follow:



validate → plan → execute → verify → commit


Rollback must remain possible.

Never perform automatic destructive action without explicit user confirmation.

---

## 🧠 ARCHITECTURE OVERVIEW

Presentation Layer:
- Jinja templates
- Static assets
- main.py route rendering

API Layer:
- FastAPI routers
- auth
- storage
- files
- monitoring
- services
- network
- system

Domain Services:
- services/*
- All system logic lives here

Persistence:
- SQLAlchemy models
- SQLite database

---

## 🎨 UI DEVELOPMENT RULES

### Layout Safety

Copilot MUST NOT:

- Change base template block structure
- Remove container wrapper hierarchy
- Rename DOM IDs used by JavaScript
- Merge sidebar + content containers

---

### UI Change Workflow (MANDATORY)

When modifying UI:

1. Modify only CSS or styling first
2. Preserve HTML structure
3. Maintain template inheritance
4. Verify dynamic data selectors remain valid

---

### After ANY UI Change

Developer must:

- Restart backend server
- Hard refresh browser
- Validate:
  - data rendering
  - navigation
  - responsive layout
  - WebSocket updates

---

## 🔄 Sync Rules

UI changes must remain compatible with:

- API response schemas
- Template variable names
- JavaScript selectors
- WebSocket payload structure

Copilot must never rename fields without updating ALL layers.

---

## 🧪 TESTING PRIORITY

Copilot should suggest tests for:

1. Storage destructive flows
2. Config rollback scenarios
3. Authentication & CSRF
4. File upload safety
5. Network config validation
6. Command execution error handling

---

## 🧱 Command Execution Standards

All command execution must:

- Support timeout
- Return structured result
- Support retry if safe
- Log command output
- Provide clear error propagation

---

## 🧾 Config File Editing Rules

When editing system configs:

- Always create backup first
- Write using temp file
- Validate before replace
- Support rollback

---

## 🔐 Security Rules

Copilot must enforce:

- No default credentials
- No hardcoded secrets
- CSRF protection on all mutation endpoints
- Token validation must check active user state

---

## ⚠️ Reliability Requirements

Operations must support:

- atomic execution
- rollback capability
- concurrency lock
- operation journaling
- post-execution verification

---

## 🧹 Refactoring Rules

Copilot may refactor ONLY IF:

- No behavior change
- No command sequence change
- No API contract change
- No UI selector change

---

## 🧪 Before Suggesting Improvements

Copilot must ask:

- Does this affect system reliability?
- Does this affect destructive operations?
- Does this affect UI data binding?

---

## 🧰 Logging Standards

All service operations must log:

- operation start
- command executed
- result
- failure reason
- rollback attempt

---

## 🧯 Recovery Expectations

Every destructive workflow must support:

- safe abort
- state cleanup
- user-readable error
- restore previous config

---

## 💡 Copilot Behavior Preference

Favor:

- explicit logic over abstraction
- predictable flows over clever optimization
- safety checks over performance gains
- readability over compact code

---

## 🛑 When Unsure

Copilot should stop and ask developer instead of guessing.

---

## Continuous Learning Loop

The `/kb` directory is Copilot's long-term memory. Treat it as a RAG (Retrieval-Augmented Generation) store.

**Before every answer:**
- Search `/kb` for related entries by category and keywords.
- If a matching entry exists, use it as the primary source of truth.
- If the entry is outdated, apply the fix and then update the entry.

**After every successful fix:**
- Write a new KB entry using `/kb/TEMPLATE.md`.
- Place it in the correct category folder under `/kb/`.
- Add it to `/kb/INDEX.md`.
- If an entry already exists, append a dated update section.

**When the user reports a mistake:**
- Record the corrected method into KB immediately.
- Mark the old approach as superseded in the existing entry.

**Goal:** Over time, this repository becomes a self-improving knowledge base. Every resolved issue makes the next fix faster and more reliable. Copilot must never repeat a mistake that has been recorded in KB.
