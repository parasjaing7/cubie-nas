# Cubie NAS — Copilot Engineering Instructions

This project is a reliability-focused NAS management system.
Copilot must prioritize DATA SAFETY, SYSTEM STABILITY, and UI ↔ BACKEND SYNC over code optimization.

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
