# Command: Audit Remediation Status & Next Slice

Show progress on the 2026-06 audit remediation and recommend the next issue to tackle, respecting
the layer/phase sequencing. Read-only — it reports and recommends, it does not edit or close.

**Usage:** `/audit-status` · `/audit-status <theme|app|phase>` (e.g. `/audit-status privilege-pii`)

## Dependencies

- Tracking: GitHub milestone **"Blocking Remediation"** (#1) + labels `severity:*`, `theme:*`,
  `app:*`.
- Sequencing: the Phase 0→3 order and layer→issues map in
  [.claude/context/audit/remediation/00-plan.md](.claude/context/audit/remediation/00-plan.md).
- Overview: [.claude/context/audit/2026-06-audit-executive-summary.md](.claude/context/audit/2026-06-audit-executive-summary.md).

## What it does

1. **Pull state** from GitHub (open/closed by severity, theme, app):
   ```bash
   gh issue list --repo Brunotlps/wss-backend-v0 --state all \
     --label severity:blocking --json number,title,state,labels --limit 100
   gh api repos/Brunotlps/wss-backend-v0/milestones/1 \
     -q '"\(.title): \(.open_issues) open / \(.closed_issues) closed"'
   ```
   Repeat per `theme:*` (protected-media, access-control, privilege-pii,
   transactional-integrity, certificate-trust) and per `severity:*`.
2. **Render progress**: a table of Blocking by theme (closed/total) and overall Major/Minor counts.
3. **Recommend the next slice** using `00-plan.md`:
   - Honor phase order — never recommend a Phase-1 item whose Phase-0 dependency
     (#41 permission baseline, global throttling, protected media) is still open.
   - Prefer the cross-cutting "do once, resolve many" fixes first.
   - Group by owning layer playbook so a single PR can close sibling issues.
4. **Hand off**: name the exact issue(s) and the `/fix-issue <n>` to run next, with the owning
   playbook and any blockers.

## Output

```
## Audit Remediation — status

Milestone "Blocking Remediation": <c>/16 closed
Blocking by theme:
  protected-media        <c>/2   access-control        <c>/2
  privilege-pii          <c>/4   transactional-integrity <c>/4
  certificate-trust      <c>/4
Major: <c>/37 closed · Minor: <c>/28 closed

Phase status: Phase 0 <…>  → current focus: <phase>

▶ Recommended next: #<n> <title>  [<NN-playbook.md>]
   Blocked by: <none | #x must close first>
   Run: /fix-issue <n>
   (sibling issues closeable in the same PR: #a, #b)
```

Rules: read-only (no edits, no closing issues). Always check Phase-0 blockers before recommending.
If everything in the current phase is closed, advance to the next phase per `00-plan.md`.
