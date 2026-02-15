# Cubie NAS v1 -- Full Reconstruction Specification

## 1. Project Purpose

Cubie NAS is a lightweight web-based NAS management appliance designed
for low-cost ARM64 SBC devices such as Radxa Cubie A5E. It provides
storage provisioning, service control, user management, file management,
monitoring, and system orchestration through a web UI.

Primary Goal: Provide consumer-friendly, low-RAM (\<2GB) local NAS
appliance.

------------------------------------------------------------------------

## 2. Target Hardware & OS

### Hardware Targets

-   ARM64 SBC
-   NVMe storage supported
-   USB storage supported
-   1--2GB RAM
-   Gigabit LAN preferred

### Tested Device

-   Radxa Cubie A5E

### Operating System

-   Debian / Ubuntu ARM64

------------------------------------------------------------------------

## 3. High Level Architecture

Browser UI ↓ FastAPI Web Server ↓ Router Layer (API Endpoints) ↓ Service
Layer (Business Logic) ↓ System Command Layer ↓ Linux OS + Storage +
Services

------------------------------------------------------------------------

## 4. Technology Stack

### Backend

-   FastAPI
-   SQLAlchemy
-   SQLite
-   Uvicorn
-   JWT authentication
-   WebSockets (live monitoring)

### Frontend

-   Jinja templates
-   Vanilla JS
-   CSS

### System Integration

-   systemd service
-   Samba
-   NFS
-   SSH
-   FTP (vsftpd)
-   Docker (optional integration)
-   rsync backup
-   smartmontools
-   Linux CLI utilities

------------------------------------------------------------------------

## 5. Core Functional Modules

### Authentication System

Files: - routers/auth.py - security.py

Features: - JWT login/logout - Cookie storage - CSRF protection - Brute
force lockout - Role based access

------------------------------------------------------------------------

### User Management

Files: - routers/users.py - services/user_ctl.py

Capabilities: - Create app users - Create Linux users - Change
passwords - Folder permission control

------------------------------------------------------------------------

### Storage Provisioning

Files: - routers/storage.py - services/storage.py

Capabilities: - Disk discovery - SMART status - Partition formatting -
Mount/unmount drives - fstab persistence

------------------------------------------------------------------------

### SMB / NAS Share Publishing

Features: - Create Samba shares - Modify smb.conf - Restart Samba
service

------------------------------------------------------------------------

### File Manager

Files: - routers/files.py - services/file_ops.py

Features: - Directory browsing - Upload / Download - Rename / Delete -
Folder creation

------------------------------------------------------------------------

### Monitoring System

Files: - routers/monitoring.py - services/monitor.py

Metrics: - CPU usage - RAM usage - Temperature - Network throughput -
Disk IO - Uptime

------------------------------------------------------------------------

### Service Controller

Files: - routers/services.py - services/service_ctl.py

Supported: - Samba - NFS - SSH - FTP

------------------------------------------------------------------------

### System Operations

Files: - routers/system.py

Functions: - Hostname - Network config - Firewall config - System info -
Reboot/shutdown

------------------------------------------------------------------------

## 6. Command Execution Layer

File: - services/system_cmd.py

Responsibilities: - Executes shell commands - Async execution - Returns
stdout/stderr

------------------------------------------------------------------------

## 7. Database Design

File: - models.py

Uses SQLite to store: - Users - Roles - Sessions - Config metadata

------------------------------------------------------------------------

## 8. Configuration System

Files: - config.py - .env

Includes: - JWT secret - TLS config - Database path - Service paths

------------------------------------------------------------------------

## 9. Frontend UI Structure

Templates: - dashboard.html - login.html

Static: - CSS / JS

------------------------------------------------------------------------

## 10. Installation & Provisioning

Script: - scripts/install.sh

Performs: - Dependency install - Virtual environment creation - TLS
certificate generation - systemd service installation

------------------------------------------------------------------------

## 11. Runtime Service

systemd Unit: - systemd/cubie-nas.service

------------------------------------------------------------------------

## 12. Security Design

Includes: - HTTPS self signed certificate - CSRF protection - JWT
cookies - Role based access - Firewall integration

------------------------------------------------------------------------

## 13. Performance Design

Optimized for: - 1GB--2GB RAM devices - SQLite minimal overhead - Single
Uvicorn process

------------------------------------------------------------------------

## 14. Plugin Architecture

Directory: - plugins/

Supports external feature modules.

------------------------------------------------------------------------

## 15. External Dependencies

-   samba
-   nfs-kernel-server
-   openssh-server
-   vsftpd
-   smartmontools
-   rsync
-   docker (optional)

------------------------------------------------------------------------

## 16. Deployment Flow

1.  Install OS
2.  Run install.sh
3.  Start systemd service
4.  Login via browser
5.  Provision storage
6.  Enable NAS services

------------------------------------------------------------------------

## 17. MVP Definition

-   Authentication
-   Storage mount + SMB publish
-   File manager
-   Monitoring dashboard
-   Service toggles

------------------------------------------------------------------------

End of Cubie NAS v1 Specification

------------------------------------------------------------------------

# Cubie NAS v2 -- Changes and Current Architecture

## 1. Current UI Architecture

- Multi-page UI now served via base template with sidebar navigation.
- Pages: general, storage, network, nas, and legacy dashboard.
- Legacy dashboard remains for user management, security helpers, and bonus tools.
- Sidebar includes a User Management link pointing to /dashboard.

Templates:

- templates/base.html
- templates/general.html
- templates/storage_page.html
- templates/network_page.html
- templates/nas_page.html
- templates/dashboard.html (legacy)

Static:

- static/css/router.css (multi-page UI)
- static/js/router.js (multi-page UI logic)
- static/css/style.css (legacy dashboard)
- static/js/app.js (legacy dashboard logic)

## 2. Command Execution Abstraction

- system_cmd.py now exposes CommandResult, RetryPolicy, CommandRunner, RealCommandRunner, MockCommandRunner.
- run_cmd remains for backward compatibility but new code uses the runner.
- All system operations go through system_cmd.py.

## 3. Reliability and Safety Enhancements

- Added transaction runner with rollback support in app/services/transaction.py.
- USB/NVMe provisioning uses transactional steps for mount and config updates.
- Config backups and rollback paths added for fstab and smb.conf operations.
- Preflight device validation added for USB/NVMe provisioning.
- Wipe confirmation requires explicit confirmation text; destructive order preserved.

## 4. UI and UX Updates

- Sidebar navigation and base template now used for all multi-page views.
- NAS management retains provisioning status and step list.
- User management available via /dashboard and sidebar link.

## 5. Tests Added

- tests/test_usb_share.py covers success, rollback, invalid device, mount failure.
- tests/test_usb_share_config_rollback.py validates rollback on Samba config failure.
- requirements.txt includes pytest and pytest-asyncio.

## 6. Developer Workflow and Instructions

- .github/copilot-instructions.md added with safety and reliability rules.
- DEVELOPMENT_WORKFLOW.md added with deployment, UI testing, release, and reliability checklists.

## 7. Deployment Notes

- systemd service runs from /opt/cubie-nas.
- Sync to /opt preserves .env and requires service restart.
- UI changes must be synced and restarted for live testing.

## 8. Known Operational Behaviors

- Regenerating .env JWT secret invalidates existing login sessions.
- User Management remains in legacy dashboard; multi-page UI does not duplicate it.

------------------------------------------------------------------------

End of Cubie NAS v2 Summary
