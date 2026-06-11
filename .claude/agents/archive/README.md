# Archived agent docs

These files are **not** Claude Code sub-agents. They lack the required
YAML frontmatter (`name`, `description`, `tools`, `model`), so Claude Code
never discovered or loaded them as agents — they were prose playbooks.

Their content also duplicates the active slash commands:

- `pep8-auditor.md` → superseded by `.claude/commands/review-pep8.md`
- `test-generator.md` → superseded by `.claude/commands/create-tests.md`

They are kept here for reference only. For automated code review use the
`code-reviewer` sub-agent in `.claude/agents/code-reviewer.md`.
