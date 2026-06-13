# Layer: Lint / Type Hints / Docstrings / Dead Code

**Owns:** #19, #20, #21 (payments) · #36, #37 (enrollments) · #51, #52, #53 (users) · #61, #63
(videos) · #70, #71 (courses) · #83, #84 (certificates) · #89, #90, #91 (core) · #92 (config).
**Phase 3** (hygiene) — batchable across all apps; low risk, do in one or few PRs.

## Rule (`.claude/rules/code-style.md`)
PEP8 + Black (88 chars), isort, no unused imports, type hints on all signatures, Google-style
docstrings, no commented-out/dead code, double quotes, logging not `print`.

## Batch 1 — auto-fixable (lint)
Every app has F401/F841 in its test modules plus black/isort drift. Run per app, then commit:
```bash
flake8 apps/ config/          # find
black apps/ config/           # fix formatting (#20,#61,#83,#89,#92)
isort apps/ config/           # fix import order
# then manually remove unused imports/vars flagged by F401/F841 (#19,#36,#51,#61,#70,#83,#89)
```
- #21: payments `models.py:109` 92-char f-string — wrap (E501 is ignored in `.flake8`, but the
  rule still applies; consider un-ignoring E501).
- #92: `config/urls.py` indentation/trailing whitespace — extend lint scope to `config/` in CI.

## Batch 2 — type hints & docstrings (manual)
Add return annotations + Google-style docstrings where missing:
- payments #22 (`services.py` `Any`/`object` → real types via `TYPE_CHECKING`).
- enrollments #37 · users #52 (also fix `urls.py:17` stale docstring; translate the pt-BR comment
  in `permissions.py:80`) · videos #63 (also add `Video.Meta.indexes`) · courses #71 (also admin
  docstrings + `list_select_related`) · certificates #84 · core #90.

## Batch 3 — dead code & small cleanups
- users #53: remove commented-out block in `signals.py:46-67`; defensive check for missing
  `id_token` in `_exchange_code`; `verbose_name` underscores.
- courses #72 (is_published noise in public list — coordinate with `03`).
- certificates #85: error envelope `{"error"}` → `{"detail"}`; redundant index; naive datetime
  (model parts in `02`).
- core #91: delete dead `default_app_config` (`__init__.py`); de-duplicate hardcoded `version`
  (source from settings/package metadata).

## Order / dependencies
- Run **after** the behavioral fixes per app (avoid churn/merge conflicts with Phases 0–2), or as
  the opening commit of each app's PR if you prefer a clean diff. Don't mix auto-format with logic
  changes in the same commit.

## Done criteria
- [ ] `flake8 apps/ config/` clean; `black --check` and `isort --check-only` pass repo-wide.
- [ ] All public signatures have type hints; public methods have Google-style docstrings.
- [ ] No commented-out code, no dead config, no duplicated version string.
