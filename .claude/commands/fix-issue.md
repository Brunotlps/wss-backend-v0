# Command: Fix Audit Issue (TDD, layer-aware)

Resolve a single GitHub issue from the 2026-06 audit, driven by the layer remediation playbooks.
Use for any `#12`–`#92` finding. One issue (or one tight layer-slice) per run.

**Usage:** `/fix-issue <issue-number>` (e.g. `/fix-issue 41`)

## Dependencies (read, don't restate)

- The owning playbook in [.claude/context/audit/remediation/](.claude/context/audit/remediation/)
  — find it via the layer→issues map in `00-plan.md`.
- The canonical patterns in [.claude/rules/](.claude/rules/) cited by that playbook.
- Project shape in `CLAUDE.md` / `.claude/context/`. Apps live in `backend/apps/<app>/`.

## Workflow

### 1. Load context
- `gh issue view <n>` — read the problem, files, recommendation, and labels
  (`app:*`, `severity:*`, `theme:*`).
- Open the owning layer playbook (`00-plan.md` map) and the rules it cites.
- Confirm phase/order: if `00-plan.md` lists a Phase-0 dependency that is still open
  (e.g. #41 permission baseline, global throttling, protected media), surface it before editing —
  don't fix on top of an unfixed foundation.

### 2. RED — failing test first (TDD, required)
- Write the regression / deny-test that encodes the issue's done-criteria. For security findings
  this is a *deny* test (e.g. anonymous access → 401/403; `is_instructor` ignored on POST).
- Run it; confirm it **fails** for the documented reason. Mock externals (Stripe, Celery `.delay`)
  per `testing.md`.

### 3. GREEN — minimal fix per the playbook
- Apply the canonical pattern from the owning playbook. Stay in the layer; if the fix needs a
  second layer (cross-layer issue, `†` in the map), note it and keep changes minimal.
- No over-engineering, no drive-by refactors outside the issue's scope.

### 4. Verify
```bash
cd backend
pytest apps/<app>/ -q
flake8 apps/<app>/ && black --check apps/<app>/ && isort --check apps/<app>/
```
- All new + existing tests pass; coverage stays ≥80% (≥90% on payments / enrollments /
  permissions / certificates critical paths).
- Walk the playbook's **Done criteria** checklist and confirm each item.

### 5. Review gate
- Run the `code-reviewer` sub-agent on the diff (`git diff main -- backend/apps/<app>/`) and
  address any Blocking finding before proceeding.

### 6. STOP for approval
- Summarize: what changed, the RED→GREEN evidence, linter/test results, done-criteria checklist,
  and the proposed conventional commit message (`fix(<app>): … (closes #<n>)`).
- **Do not commit or push.** Wait for explicit approval (project rule: ask before committing;
  never push). On approval, branch if on `main`, commit, and reference the issue.

## Output

```
## Fix — #<n> <title>  [app:<app> · severity:<sev> · theme:<theme>]

Layer playbook: <NN-file.md>   Phase: <0–3>   Blocked by: <none | #x>

RED:  <test path::name> — failed as expected (<reason>)
FIX:  <files touched, 1-line each>
GREEN: pytest <x passed> · flake8 ok · black/isort ok · coverage <%>
Done-criteria: [x] … [x] … [ ] (note any deferred)

Proposed commit: fix(<app>): <summary> (closes #<n>)
Awaiting approval to commit.
```

Rules: TDD always (RED before GREEN). One issue per run. Cite `file:line`. Stay in scope. Never
auto-commit. If the issue is a doc/product decision rather than code (e.g. a recorded decision),
say so and propose the doc/playbook update instead of forcing a code change.
