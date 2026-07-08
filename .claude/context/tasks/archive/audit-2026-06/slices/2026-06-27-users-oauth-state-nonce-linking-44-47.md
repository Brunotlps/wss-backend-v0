# Slice: OAuth state/nonce single-use + audit-log linking (#44, #47)

**Data:** 2026-06-27
**Branch:** `fix/users-oauth-state-nonce-linking-44-47` (a partir de `main`) → **PR (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · slice OAuth (parte 1 de 2) da camada services/signals/tasks
**Status:** mergeado, **deployado e validado em prod 2026-06-27**.

## Contexto

Camada `06`, serviço OAuth do Google (`apps/users/services/google_oauth.py`). Dois findings de
segurança coesos, **sem impacto no frontend** (sem Redis, sem novo endpoint). O terceiro OAuth
(**#43**, JWT no fragment da URL) foi **deliberadamente separado** numa slice própria seguinte — ver
"Notas".

## Bugs + Fix

- **#44 (Major, security) — state/nonce replayáveis.** `_validate_state` comparava mas **nunca
  removia** `google_oauth_state` da sessão, e `handle_callback` lia o nonce com `.get` (não `.pop`).
  Enquanto a sessão vivia, um callback capturado podia ser **reusado**. Fix: `_validate_state` dá
  `pop` no state **após** a validação bem-sucedida (o guard de mismatch/missing roda antes → o
  `ValueError` continua intacto, e o state **sobrevive** a uma validação que falha); `handle_callback`
  consome o nonce com `request.session.pop("google_oauth_nonce", "")`. Ambos viram single-use.
- **#47 (Major, security hardening) — linking silencioso.** No passo 2 (`User` existente com mesmo
  email → cria `SocialAccount`), o link a uma conta local **com senha usável** acontecia sem rastro.
  Fix: se `user.has_usable_password()` → `logger.warning` de segurança (audit trail: sub + email)
  **antes** de criar o link. **Loga, não bloqueia**; o gate `email_verified` (mitiga takeover
  clássico) fica. Confirmação extra = **deferral deliberado** (decisão de produto registrada).

Sem logger `security` dedicado em `config/` (fora de escopo da camada apps/): o `logger` do módulo
propaga pro root (console+file `RotatingFileHandler`), suficiente pro audit trail.

## Verificação

- **RED:** 3 testes novos falharam pelo motivo documentado (state/nonce não removidos da sessão;
  sem WARNING no link com senha usável). 1 guard (link passwordless não avisa) já passava.
- **GREEN:** `pytest apps/users/`: **111 passed**. flake8/black/isort limpos (apps/users). Migration
  drift: nenhum (sem mudança de model). Coverage: `google_oauth.py` **90%** (faltantes pré-existentes
  — log de usuário existente, branch de erro do `_exchange_code`, contador do `_unique_username`).
- **code-reviewer (diff final):** **APPROVE**, 0 Blocking / 0 Major. Confirmou: (1) sem caminho onde
  state/nonce sobrevivem a um callback bem-sucedido, e o pop não quebra o `ValueError` de
  mismatch/missing (guard antes do pop); (2) `has_usable_password()` é o predicado certo e o link
  ainda ocorre (loga, não bloqueia); (3) ordem do pop do nonce vs `_validate_id_token` correta (nonce
  capturado no local antes de remover da sessão); (4) qualidade dos testes (caplog no logger nomeado,
  `UserFactory.build()` sem DB no teste de sessão). Nit: email (PII) no WARNING é o audit trail
  exigido pelo #47 — justificado, sem mudança.
- **Prod (2026-06-27):** smoke rollback-safe (`transaction.atomic()` + `raise`, chamadas do Google
  mockadas, `RequestFactory` + sessão dict, dados via factories,
  `docker compose exec -T backend python manage.py shell <`):
  - #44 `_validate_state` consome o state; mismatch ainda levanta `ValueError`; state **sobrevive** a
    falha de validação ✅
  - #44 `handle_callback` consome state **e** nonce (single-use) ✅
  - #47 link com senha usável → `WARNING` de segurança (linha confirmada no log de prod); link
    **prossegue** (`SocialAccount` criado, não bloqueado) ✅
  - #47 link passwordless (OAuth-only) **não** avisa ✅
  - **`ALL PASS`** (8/8), `rows persisted after rollback: 0` (nada persistido).

## Testes adicionados

- `tests/test_google_oauth_service.py`: `TestHandleCallbackSessionInvalidation`
  (`test_validate_state_pops_state_after_success`,
  `test_handle_callback_invalidates_state_and_nonce`) · `TestAccountLinkingSecurity`
  (`test_linking_to_account_with_usable_password_logs_warning`,
  `test_linking_to_passwordless_account_does_not_warn`).

## Done-criteria (`06`)
- [x] OAuth state/nonce single-use (#44)
- [x] Gate `email_verified` mantido + audit-log no link a conta com senha usável (#47)
- [x] validado em prod (2026-06-27)
- [ ] JWT fora da URL → **#43, slice dedicada seguinte**

## Notas

- Deploy só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- **#43 separado de propósito:** tirar o JWT do fragment exige código single-use (Redis, TTL curto) +
  `POST /api/auth/google/exchange/` + **mudança de contrato do frontend** (o Vue hoje parseia o
  fragment). Fork de design a decidir na slice: exchange devolve o par **(a) no corpo** (mínimo, casa
  com o storage atual) **vs (b) refresh em cookie httpOnly + access no corpo** (mais seguro vs XSS,
  exige cookie/CSRF/CORS-credentials). Inclinação atual: **(a)**, deixando (b) como evolução à parte.
- Fecha a camada `06` depois do #43. Em seguida: **Phase 3** (07-tests: #17/#82/#34/#35/#50/#86 +
  08-lint-style batch + videos #60).
- Follow-up de infra aberto nesta sessão: **#151** (healthcheck do Docker pega 301 por
  `SECURE_SSL_REDIRECT`, nunca chega na view).
