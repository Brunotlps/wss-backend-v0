# Slice: Config lint hygiene + extend CI lint scope (#92)

**Data:** 2026-06-30
**Branch:** `style/config-lint-ci-scope-92` (a partir de `main`) → **PR #175 (squash → `main`)**
**Layer:** `08-lint-style.md` (Batch 1) · **Phase 3 (hardening & hygiene)** · 1º slice de `08-lint-style`
**Status:** mergeado em `main` (commit `ac17b9d`), **validado por CI**. Sem deploy (formatação; sem runtime).

## Contexto

Início do `08-lint-style`. `apps/` já vinha limpo (mantido ao longo de `07-tests`); o gap de Batch 1 estava
todo em **`config/`**, que o CI **não lintava** (rodava só `apps/`). `config/urls.py` tinha indentação
2-espaços + trailing whitespace (o #92 nominal); outros 8 arquivos config tinham drift de black/isort +
whitespace/newlines.

Mudança de **formatação + config de CI** — **sem mudança de runtime** (só formatação + ordem de import).
Não é test-only, mas não altera comportamento → **sem deploy** (production.py reformatado entra no próximo
deploy de código naturalmente).

## Fix

- `black` + `isort` em `config/` — `config/urls.py` (indent 2→4, ordem de imports) + 8 arquivos
  (whitespace, newlines finais, normalização de aspas, agrupamento de imports). Nenhum valor/chave/
  condição/argumento alterado (verificado no review).
- `backend/.flake8`: per-file-ignores `config/settings/*.py:F403,F405,E402` — padrão Django (compose via
  `from .base import *` = F403/F405; `import socket` mid-file do debug toolbar em development.py = E402),
  com comentário. Escopo restrito a settings → não mascara nada em `apps/` nem em outros arquivos config.
- `.github/workflows/ci.yml`: lint job agora roda `flake8/black/isort` em `apps/ config/` (era só `apps/`).

## Verificação

- **RED (baseline):** CI lintava só `apps/`; `config/` sujo (urls.py 2-espaços/trailing ws; black
  reformataria 9 arquivos; isort 4; flake8 W291/W292/W293/E302 + F403/F405/E402 de settings).
- **GREEN:** flake8/black/isort **limpos em `apps/` + `config/`** (replicando a invocação do CI a partir
  de `backend/`); `manage.py check` OK (só warning pré-existente `staticfiles.W004`); todos os módulos
  config `py_compile` OK; sem migration drift; sanity test verde. O CI do próprio PR #175 exercitou o novo
  escopo (`apps/ config/`) e passou.
- **code-reviewer (diff final):** **APPROVE**, 0 Blocking / 0 Major. Escaneou todos os arquivos: auto-format
  é puro (aspas, wrapping, reindent, agrupamento de imports, blank lines PEP8) — nenhuma edição de lógica.
  Reorder de imports em production.py/development.py (sentry integrations acima de `from .base import *`)
  verificado **inerte** (integrations não dependem de base; usados só no `sentry_sdk.init` no fim; `base`
  precede todo override). Ignore E402 confirmado fazendo trabalho real só em development.py:57. CI
  `working-directory: backend` → `config/` resolve para `backend/config/` e o glob casa. "Ship it."
- **CI (PR #175):** verde.

## Arquivos tocados

- `backend/config/*.py` + `backend/config/settings/*.py` (formatação), `backend/.flake8` (ignores),
  `.github/workflows/ci.yml` (escopo de lint).

## Done-criteria (`08-lint-style` Batch 1)
- [x] `flake8 apps/ config/` limpo; `black --check`/`isort --check-only` passam em apps/ + config/
- [x] escopo de lint do CI estendido a `config/`
- [x] star-import/E402 de settings tratados via per-file-ignore (sem mascarar erro real)

## Notas

- Sem deploy: formatação; production.py reformatado sem mudança de comportamento.
- **`08-lint-style` restante = Batch 2 (type hints + docstrings) e Batch 3 (dead code) por app:**
  payments #19/#20/#21/#22 · enrollments #36/#37 · users #51/#52/#53 · videos #61/#63 · courses #70/#71 ·
  certificates #83/#84 · core #89/#90/#91. Fazer 1 app por PR, sem misturar auto-format com lógica no
  mesmo commit. Depois: videos **#60** (Minor, serializer docstring vs validation) encerra a Phase 3.
- Atenção a itens com implicação além de estilo (tratar com cuidado quando chegarem): certificates #85
  (envelope de erro `{"error"}`→`{"detail"}` = contrato de frontend), core #91 (de-dup de `version`).
