# Slice: Core version de-dup + dead default_app_config (#91)

**Data:** 2026-07-03
**Branch:** `refactor/core-version-dedup-91` (a partir de `main`) → **PR #196 (squash → `main`, commit `1e061aa`)**
**Layer:** `08-lint-style.md` · **Phase 3 (hardening & hygiene)** · 1º slice do **passo de lógica** (após a fila no-deploy encerrada)
**Status:** mergeado em `main`, validado por CI. **Sem deploy** (refactor comportamento-preservador, no-op de runtime, sem migração).

## Contexto

Primeiro item de lógica da Phase 3 (após os 8 apps no-deploy do `08-lint-style`). Slice pequeno e
autocontido, feito TDD (RED→GREEN) por conter lógica de fato.

## Fix (#91)

**Item 1 — dead `default_app_config`:** `apps/core/__init__.py` tinha
`default_app_config = "apps.core.CoreConfig"` — no-op desde Django 4.1 (o app config é declarado em
`apps.py:CoreConfig` e auto-descoberto). Linha removida → arquivo vazio.

**Item 2 — de-dup do `version`:** `"1.0.0"` estava hardcoded em dois lugares que driftariam:
`core/views.health_check` (payload) e `SPECTACULAR_SETTINGS["VERSION"]` (settings/base.py). Introduzida a
constante única **`APP_VERSION = "1.0.0"`** em `settings/base.py`; `SPECTACULAR_SETTINGS["VERSION"]` e o
health view (`settings.APP_VERSION`) agora referenciam a mesma fonte.

**Contrato preservado:** o payload de health continua `{status, message, version}` com version `"1.0.0"`
(agora de fonte única) → o shape-lock do #86 continua passando. Os `RELEASE_VERSION` do Sentry em
dev/prod são env-driven e outra preocupação — intocados.

## TDD

- **RED:** novo `test_health_version_is_sourced_from_settings` em `core/tests/test_views.py` assere que
  o payload version E `SPECTACULAR_SETTINGS["VERSION"]` são iguais a `settings.APP_VERSION`. Antes da
  mudança, `settings.APP_VERSION` não existia → `AttributeError` (RED confirmado).
- **GREEN:** após introduzir `APP_VERSION` e apontar os dois consumidores para ele → passa. Trava a
  invariante de fonte única (não é tautológico — cruza dois consumidores independentes).

## Verificação

- `flake8 apps/core/ config/` limpo · `black --check` · `isort --check-only` limpos.
- `django.setup()` resolve `core` → `CoreConfig` com `__init__.py` vazio (remoção do `default_app_config`
  é no-op); nenhum código importa símbolo de `apps.core.__init__`.
- `pytest apps/core/`: **24 passed** (era 23 + o novo). Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE**, 0 findings. Confirmou contrato de health inalterado,
  app loading intacto, RED→GREEN genuíno, herança de `APP_VERSION` em dev/prod, sem drift.
- **CI (PR #196):** verde.

## Arquivos tocados

- `apps/core/__init__.py` (esvaziado) · `apps/core/views.py` · `apps/core/tests/test_views.py` ·
  `config/settings/base.py`.

## Done-criteria (#91)
- [x] `default_app_config` morto removido do core
- [x] `version` de fonte única (`APP_VERSION`), sem duplicação health ↔ OpenAPI
- [x] Contrato de health preservado; travado por teste

## Notas

- Sem deploy: settings/health = no-op de runtime (mesmo valor, fonte única) → entra no próximo deploy de
  código.
- **Follow-up #195 aberto:** o mesmo `default_app_config` morto existe em enrollments/videos/courses/
  payments/users `__init__.py` — varrer os 5 de uma vez (fora do escopo core do #91).
- **RESTA na Phase 3:** users **#53** (defensive `id_token` em `_exchange_code`, N+1 no `UserViewSet`,
  signal comentado — no-deploy, teste RED) · videos **#63** (type hints + `Meta.indexes` = **migração +
  deploy**) · certificates **#85** (envelope de erro = **contrato de frontend**) · **#190** (help_text
  migração metadata-only, agrupar com #63) · **#195** (dead config dos 5 apps).
- Follow-ups abertos: #195, #190, #183, #180, #155/#136/#122/#38/#151.
