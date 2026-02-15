# KB Template

> Copy this file to the appropriate category folder.
> Filename format: `YYYY-MM-DD_short_snake_case_topic.md`

---

## Title

<!-- One-line summary of the issue and fix -->

## Date

<!-- YYYY-MM-DD -->

## Category

<!-- Folder name: linux | smb | usb | kernel | uboot | networking | storage | permissions | services | docker | git | troubleshooting | opentap | tools -->

## Tags

<!-- Comma-separated keywords for search: e.g., mount, ext4, fstab, power-loss -->

## Environment

- **Device/Board:** <!-- e.g., Cubie A5E (RK3588S) -->
- **OS:** <!-- e.g., Debian 12 bookworm ARM64 -->
- **Kernel:** <!-- output of uname -r -->
- **Repo branch:** <!-- e.g., main -->
- **Service version:** <!-- git rev-parse --short HEAD -->

## Problem Statement

<!-- 1-2 lines. What broke or what was the goal. -->

## Symptoms

<!-- Observable behavior: error messages, log lines, UI state. Copy-paste exact output. -->

```
<paste exact error or log output here>
```

## Root Cause

<!-- 1-3 lines. Why it happened. Be specific: file, line, config, kernel behavior. -->

## Fix

<!-- Final working steps ONLY. No trial-and-error. No speculation. -->

1. Step one
2. Step two

## Commands

<!-- Copy-paste ready. Each command in its own code block. -->

```bash
# command 1
```

```bash
# command 2
```

## Files Changed

<!-- Absolute paths + one-line description of change -->

| File | Change |
|------|--------|
| `/path/to/file` | Description of change |

## Verification

<!-- Commands to confirm the fix worked. Include expected output. -->

```bash
# verification command
```

**Expected output:**
```
<expected output here>
```

## Rollback Steps

<!-- How to undo this fix if it causes problems. -->

1. Step one

## Risks / Gotchas

<!-- Edge cases, known limitations, things that could break later. -->

- Risk one

## References

<!-- Links, man pages, internal file references, related KB entries. -->

- [reference](url)

---

> **Quality rules:** No raw logs. No speculation. No chat transcripts. Only validated, working fixes.
