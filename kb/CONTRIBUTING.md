# Contributing to the Knowledge Base

## When to Create a KB Entry

- You solved a non-trivial bug or configuration issue.
- You discovered a gotcha, workaround, or environment-specific behavior.
- You fixed a regression or a recurring problem.
- A debugging session took more than 15 minutes.

## When to Update an Existing Entry

- The fix changed (new method, different command, updated path).
- The environment changed (new kernel, new OS version, new dependency).
- Additional risks or gotchas were discovered.

When updating: **append a dated update section** at the bottom of the entry. Do not overwrite the original fix.

```markdown
---

### Update YYYY-MM-DD

- What changed and why.
```

## How to Create an Entry

1. Copy `kb/TEMPLATE.md` to the correct category folder.
2. Name it: `YYYY-MM-DD_short_snake_case_topic.md`
3. Fill in every section. Leave none blank — write "N/A" if truly not applicable.
4. Add the entry to `kb/INDEX.md`.

## Quality Rules

| Rule | Reason |
|------|--------|
| No raw chat logs | Noise, not knowledge |
| No speculation | Only validated fixes |
| No partial fixes | Entry must describe the complete working solution |
| No duplicate entries | Search INDEX.md first; update existing if relevant |
| Include verification | Every fix must have a "how to confirm it worked" block |
| Include rollback | Every fix must have an undo path |
| Use exact paths | Absolute paths, exact commands, no placeholders unless parameterized |

## Naming Convention

```
YYYY-MM-DD_short_snake_case_topic.md
```

Examples:
- `2026-02-15_usb3_port_not_detected.md`
- `2026-02-15_smb_share_permission_denied.md`
- `2026-02-15_fstab_atomic_write_fsync.md`

## What Does NOT Belong in KB

- Opinion or design discussion.
- Incomplete investigations.
- Temporary workarounds without a real fix.
- Copilot/LLM chat transcripts.
- Code review comments.

## Maintenance

- Review KB entries quarterly. Archive stale entries by moving to `kb/_archived/`.
- Remove entries from `kb/INDEX.md` when archiving.
- Never delete knowledge — archive it.
