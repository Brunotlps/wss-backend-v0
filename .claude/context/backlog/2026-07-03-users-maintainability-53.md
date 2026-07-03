# Slice: Users maintainability — no-deploy scope (#53)

**Data:** 2026-07-03
**Branch:** `fix/users-maintainability-53` (a partir de `main`) → **PR #201 (squash → `main`, commit `a4d5fa6`)**
**Layer:** `08-lint-style.md` · **Phase 3 (hardening & hygiene)** · último item **no-deploy** da Phase 3
**Status:** mergeado em `main`, validado por CI. **Sem deploy** (fix defensivo é no-op de schema; entra no próximo deploy de código).

## Contexto

Último no-deploy da Phase 3. #53 tinha 5 sub-itens de naturezas diferentes; feito TDD nos que têm
comportamento. Um item (verbose_name) exige migração → carvado.

## Fix (#53, escopo no-deploy)

- **Item 3 — defensive `id_token` (única mudança de comportamento, TDD):** `_exchange_code`
  (`services/google_oauth.py`) retornava `response.json()` sem checar `id_token`. Se o Google devolve 200
  com payload de erro estruturado (sem `id_token`), o `handle_callback` batia `KeyError` em
  `tokens["id_token"]` → vazava como 500. Agora `_exchange_code` levanta o `ValueError` documentado se
  `id_token` ausente. **RED→GREEN:** novo `test_exchange_code_missing_id_token_raises_value_error` (mock
  `http_requests.post` → ok=True, json `{"error": ...}`) espera `ValueError match "id_token"` (antes: não
  levantava → RED).
- **Item 2 — N+1 no `UserViewSet` (já resolvido):** `get_queryset` já fazia
  `select_related("profile")` (o retrieve aninha `ProfileSerializer` via `UserDetailSerializer`; list usa
  o serializer mínimo, sem profile). Travado por `test_retrieve_does_not_issue_separate_profile_query`
  (`CaptureQueriesContext`; assere ausência de `SELECT ... FROM "users_profile"` standalone). Reviewer
  confirmou empiricamente em cópia scratch que o teste falha se o `select_related` for removido → lock
  meaningful, não no-op.
- **Item 1 — dead code:** removido o bloco comentado `save_user_profile` em `signals.py` + a referência
  stale a ele no docstring do módulo. `create_user_profile` (única via de criação de Profile) intacto.
- **Item 5 — docstring:** documentado no `User` que `created_at` (TimeStampedModel) sobrepõe
  `AbstractUser.date_joined`, mantido de propósito pelo contrato compartilhado do TimeStampedModel
  (`updated_at` não tem equivalente no AbstractUser).

## Fork: item 4 (verbose_name) → #200

**Item 4** (`verbose_name` `"email_address"`/`"phone_number"` em `User.email`/`User.phone` → "email
address"/"phone number") **NÃO** entrou: `verbose_name` é parte do `deconstruct()` do field → gera
`AlterField` (users, metadata-only) + deploy. Carvado para **follow-up #200** (agrupar na próxima janela de
migração com #190/#63).

## Verificação

- `flake8/black/isort apps/users/` limpos · nenhuma linha > 88.
- `makemigrations --check`: **No changes detected** (verbose_names intocados de propósito).
- `pytest apps/users/`: **146 passed** (144 + 2 novos). Suíte completa do projeto: verde (rodada no #195).
- **code-reviewer (diff final):** **APPROVE**, 0 findings. Verificou o guard defensivo completo, RED→GREEN
  genuíno, lock do item 2 meaningful (scratch), dead-code sem perda de comportamento, sem drift. Nit: a
  heurística de query do teste é acoplada ao dialeto SQL (aceitável — sqlite test + Postgres prod batem).
- **CI (PR #201):** verde.

## Arquivos tocados

- `apps/users/services/google_oauth.py` · `apps/users/signals.py` · `apps/users/models.py` ·
  `apps/users/tests/test_google_oauth_service.py` · `apps/users/tests/test_views.py`.

## Done-criteria (#53, escopo no-deploy)
- [x] Item 1 (dead code) removido
- [x] Item 2 (N+1) travado por regressão meaningful
- [x] Item 3 (defensive id_token) com TDD
- [x] Item 5 (docstring created_at/date_joined)
- [~] Item 4 (verbose_name) → **#200** (migração + deploy)

## Notas

- **✅ TODO O ESCOPO NO-DEPLOY DA PHASE 3 ENCERRADO.** Restam apenas itens **de deploy/coordenação**:
  - **videos #63** — type hints + `Video.Meta.indexes` (**migração + deploy**).
  - **#190** — help_text `TimeStampedModel` (migração metadata-only cross-app).
  - **#200** — verbose_name `User.email`/`phone` (migração metadata-only, users).
  - **certificates #85** — envelope de erro `{"error"}`→`{"detail"}` (**contrato de frontend**, coordenar
    com wss-frontend).
  - Sugestão: **agrupar #63 + #190 + #200 numa única janela de deploy com migração** (todos `AlterField`/
    índice, metadata-ish); tratar #85 à parte com o front.
- Follow-ups abertos: #200, #190, #183, #180, #155/#136/#122/#38/#151.
