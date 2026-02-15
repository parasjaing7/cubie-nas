# Knowledge Base Index

> Auto-maintained index of all KB entries. Update this file whenever a KB entry is created or archived.

## How to Use

1. Search by category folder or scan the table below.
2. Use tags and filenames to find relevant entries.
3. If no entry exists for your issue, solve it and create one using `kb/TEMPLATE.md`.

## Categories

| Folder | Scope |
|--------|-------|
| `linux/` | OS-level issues: systemd, packages, boot, logs, cron |
| `smb/` | Samba configuration, shares, testparm, permissions |
| `usb/` | USB detection, hotplug, mount, power, device nodes |
| `kernel/` | Kernel panics, modules, dmesg, device tree, drivers |
| `uboot/` | U-Boot config, boot sequence, env vars, serial console |
| `networking/` | IP config, DNS, firewall, interfaces, nmcli, routing |
| `storage/` | Disks, partitions, filesystems, fstab, SMART, mount/unmount |
| `permissions/` | File ownership, ACLs, chmod, chown, NAS user mapping |
| `services/` | systemd units, service lifecycle, cubie-nas service |
| `docker/` | Container lifecycle, images, networking, volumes |
| `git/` | Git workflows, merge conflicts, deploy sync |
| `troubleshooting/` | Cross-cutting issues that span multiple categories |
| `opentap/` | OpenTAP integration, test automation |
| `tools/` | CLI utilities, scripts, dev tooling |

## Entry Index

<!-- Add entries below as they are created. Format: -->
<!-- | Date | Category | File | Title | Tags | -->

| Date | Category | File | Title | Tags |
|------|----------|------|-------|------|
| 2026-02-15 | tools | `kb/tools/2026-02-15_dashboard_ui_layout_standard.md` | Dashboard UI layout standard for Cubie NAS (OpenMediaVault/router style) | dashboard, css-grid, responsive, overflow |
| 2026-02-15 | storage | `kb/storage/2026-02-15_atomic_copy_preserve_permissions.md` | Preserve file permissions in atomic backup/restore copy path | atomic-copy, permissions, backup, restore |
| 2026-02-15 | storage | `kb/storage/2026-02-15_cross_worker_provision_file_lock.md` | Add filesystem advisory lock to prevent cross-worker concurrent provisioning | provisioning, concurrency, flock |
| 2026-02-15 | services | `kb/services/2026-02-15_jwt_secret_startup_guard.md` | Fail fast on insecure default JWT secret at application startup | jwt, security, startup, env |

---

> Keep this index sorted by date (newest first). Remove entries only when archiving, never delete knowledge.
