# Slice: Remove dead default_app_config from 5 apps (#195)

**Data:** 2026-07-03
**Branch:** `refactor/remove-dead-default-app-config-195` (a partir de `main`) → **PR #198 (squash → `main`, commit `b29bfda`)**
**Layer:** Phase 3 (hardening & hygiene) · follow-up de dead-code descoberto no core #91
**Status:** mergeado em `main`, validado por CI. **Sem deploy** (dead-code removal, no-op de runtime, sem migração).

## Contexto

Follow-up aberto durante o core #91 (PR #196): o mesmo `default_app_config` morto (no-op desde Django 4.1)
existia em mais 5 apps além do core. Slice de limpeza cross-app.

## Fix (#195)

Removida a linha `default_app_config = "..."` de:
- `apps/courses/__init__.py` · `apps/enrollments/__init__.py` · `apps/payments/__init__.py` ·
  `apps/videos/__init__.py` → arquivos vazios (padrão do core #91).
- `apps/users/__init__.py` → removida a linha **e a docstring órfã** acima dela (só descrevia o mecanismo
  morto; era factualmente errada após a remoção — o load é via `INSTALLED_APPS` + `apps.py`, e os signals
  registram em `UsersConfig.ready()`). Arquivo vazio.

Cada app já declara seu `AppConfig` em `apps.py` e é carregado por `INSTALLED_APPS = ["apps.<app>", ...]`
(auto-detecção do Django 5.2). `default_app_config` nunca foi o caminho de load no 5.2.

## Verificação

- `flake8/black/isort apps/` limpos.
- Import smoke: os 6 apps resolvem o Config correto (`django.setup()` roda todos os `ready()` → signals
  registram).
- **Suíte completa: 571 passed, 98.35% cobertura** (rede de segurança para signals/ready() dos 5 apps,
  incluindo a cadeia enrollment→certificate). Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE**, 0 findings. Confirmou app loading + signal registration
  intactos, nenhum importer dos `__init__.py`, e — detalhe — **4 das 5 linhas apontavam para caminhos
  inexistentes** (ex.: `"apps.courses.CoursesConfig"` sem `.apps`) → eram duplamente mortas.
- **CI (PR #198):** verde.

## Arquivos tocados

- `apps/{courses,enrollments,payments,videos,users}/__init__.py` (todos esvaziados).

## Done-criteria (#195)
- [x] `default_app_config` morto removido dos 5 apps
- [x] Suíte verde; apps carregam e registram signals normalmente

## Notas

- Sem deploy: no-op de runtime.
- Junto com o core #91, **toda a dívida de `default_app_config` está zerada** (6 apps).
- **RESTA na Phase 3:** users **#53** (defensive `id_token`, N+1, signal comentado — **no-deploy, teste
  RED**) · videos **#63** (type hints + `Meta.indexes` = **migração + deploy**) · certificates **#85**
  (envelope de erro = **contrato de frontend**, coordenar) · **#190** (help_text `TimeStampedModel` =
  migração metadata-only, agrupar com #63).
- Follow-ups abertos: #190, #183, #180, #155/#136/#122/#38/#151.
