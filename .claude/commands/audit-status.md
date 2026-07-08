# Command: Audit Remediation Status & Next Slice

> **Status (2026-07-08): the 2026-06 audit remediation is fully closed** — all 81 findings
> resolved, plus the follow-ups they surfaced (#220, #223, #237). Zero open issues in the repo.
> This command still works (it always pulls fresh counts from GitHub, never hardcodes them), so
> it's safe to run if a *new* audit cycle starts later — it'll just report 0/0 until new
> `severity:*`-labeled issues exist. The historical run is archived at
> `.claude/context/tasks/archive/audit-2026-06/`.

Show progress on the 2026-06 audit remediation and recommend the next issue to tackle, respecting
the layer/phase sequencing. Read-only — it reports and recommends, it does not edit or close.

**Usage:** `/audit-status` · `/audit-status <theme|app|phase>` (e.g. `/audit-status privilege-pii`)

## Dependencies

- Tracking: GitHub milestone **"Blocking Remediation"** (#1) + labels `severity:*`, `theme:*`,
  `app:*`.
- Sequencing: the Phase 0→3 order and layer→issues map in
  [.claude/context/tasks/archive/audit-2026-06/remediation/00-plan.md](.claude/context/tasks/archive/audit-2026-06/remediation/00-plan.md).
- Overview: [.claude/context/tasks/archive/audit-2026-06/2026-06-audit-executive-summary.md](.claude/context/tasks/archive/audit-2026-06/2026-06-audit-executive-summary.md).

## What it does

1. **Pull state** from GitHub (open/closed by severity, theme, app).
   ⚠️ **Always pass `--limit 200` to every `gh issue list`.** `gh` defaults to **30** and
   silently truncates — any bucket with >30 issues (e.g. Major = 37) gets undercounted.
   ```bash
   gh api repos/Brunotlps/wss-backend-v0/milestones/1 \
     -q '"\(.title): \(.open_issues) open / \(.closed_issues) closed"'

   # Severity totals (note --limit 200; --state all for the denominator):
   for s in blocking major minor; do
     printf "severity:%-9s " "$s"
     gh issue list --repo Brunotlps/wss-backend-v0 --label "severity:$s" \
       --state all --limit 200 --json number -q 'length'
   done

   # Blocking by theme (closed vs open):
   for t in protected-media access-control privilege-pii transactional-integrity \
            certificate-trust; do
     c=$(gh issue list --repo Brunotlps/wss-backend-v0 --label "theme:$t" \
           --state closed --limit 200 --json number -q 'length')
     o=$(gh issue list --repo Brunotlps/wss-backend-v0 --label "theme:$t" \
           --state open   --limit 200 --json number -q 'length')
     echo "theme:$t closed=$c open=$o"
   done
   ```
   Reference totals as of 2026-07-04 (all `severity:*` issues are labeled; grows over time as
   follow-up findings get filed): **Blocking 18 · Major 42 · Minor 36** (original 81 findings +
   follow-ups). Don't hardcode these — always pull fresh counts with the commands above.
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
