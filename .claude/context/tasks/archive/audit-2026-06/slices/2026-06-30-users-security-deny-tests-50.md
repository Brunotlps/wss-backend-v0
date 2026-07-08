# Slice: Users security deny-tests (#50)

**Data:** 2026-06-30
**Branch:** `test/users-security-deny-tests-50` (a partir de `main`) → **PR #163 (squash → `main`)**
**Layer:** `07-tests.md` · **Phase 3 (hardening & hygiene)** · 2º slice da camada de testes (após #82)
**Status:** mergeado em `main` (commit `44dee21`), **validado por CI**. Sem deploy (test-only).

## Contexto

2º slice da Phase 3 / `07-tests`. O #50 pedia deny-tests para mass-assignment de `is_instructor`,
PII anônima, `_exchange_code` com HTTP mockado, `audience` errado e os branches de deny de
`permissions.py`. **Descoberta ao inspecionar:** os deny-tests no nível serializer (#39/#40) e os de
PII anônima negada na view (#41) **já existiam** — entraram junto com os fixes nas Phases 1/2. Logo,
este slice é **travamento de cobertura** do que estava genuinamente descoberto, confirmado pelos gaps
`permissions.py` 79% (linhas 57, 70-73) e `google_oauth.py` 92% (91, 181-194, 330-331).

Mudança **test-only** — nenhum runtime alterado → **sem deploy e sem smoke de prod**; CI é a validação.

## Lacunas cobertas

- **`permissions.IsOwnerOrReadOnly`** (novo `test_permissions.py`) — allow **e** deny em cada branch:
  - `has_permission`: anônimo → deny; autenticado → allow.
  - `has_object_permission`: SAFE (owner/staff allow, terceiro **deny** = linha 57), DELETE
    (staff allow, owner não-staff deny), write/PATCH (owner allow, terceiro deny).
  - `_is_owner`: User (self), Profile (`.user`), Course (`.instructor`, 70-71) e objeto sem atributo
    de ownership → `return False` (73, safe default).
  - Setup via `APIRequestFactory` + `request.user` manual (`view=None` é fiel — a classe nunca lê
    `view`).
- **`services.google_oauth`** (`test_google_oauth_service.py`):
  - `_exchange_code` (181-194) com `http_requests.post` mockado — sucesso assere URL alvo
    (`_GOOGLE_TOKEN_URL`) + `data["code"]` + `data["grant_type"]`; resposta não-OK → `ValueError`.
  - `audience`: assere que passamos `settings.GOOGLE_OAUTH_CLIENT_ID` como 3º arg de
    `verify_oauth2_token` e que o erro de aud propaga (testa nossa chamada, não o mock).
  - `handle_callback` branch `created=True` (91) + log "New user created".
  - `_unique_username` colisão (330-331): `dupname` ocupado → novo usuário vira `dupname1`.
- **register no nível HTTP** (`test_views.py`) — `test_register_ignores_is_instructor_flag`:
  `POST /api/auth/register/` com `is_instructor=True` → 201, usuário criado com `is_instructor=False`
  (complemento HTTP do teste serializer-level #39).

## Verificação

- **RED (baseline):** `permissions.py` **79%** (sem `test_permissions.py`); `google_oauth.py` **92%**
  (`_exchange_code` 181-194 descoberto, sem teste de audience explícito, branches created/colisão
  descobertos).
- **GREEN:** `pytest apps/users/`: **144 passed**. `permissions.py` **100%**, `google_oauth.py`
  **100%**; app users **99%**. flake8/black/isort limpos. Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE WITH NITS**, 0 Blocking / 0 Major. 2 "should fix"
  aplicados antes do commit: o teste de audience passou a asserir a chamada (`client_id` como
  audiência) em vez do match da string do próprio mock; o de `_exchange_code` passou a asserir a URL
  alvo `_GOOGLE_TOKEN_URL`.
- **CI (PR #163):** verde.

## Testes adicionados

- `tests/test_permissions.py` (novo): `TestIsOwnerOrReadOnlyHasPermission`,
  `TestIsOwnerOrReadOnlyHasObjectPermission`, `TestIsOwnerResolution`.
- `tests/test_google_oauth_service.py`: `TestExchangeCodeHttp` +
  `test_handle_callback_returns_new_user_and_logs`,
  `test_validates_against_our_client_id_and_propagates_aud_error`,
  `test_new_user_username_collision_appends_counter`.
- `tests/test_views.py`: `test_register_ignores_is_instructor_flag`.

## Done-criteria (`07-tests`)
- [x] `apps.users` permissions ≥90% (100%)
- [x] `is_instructor` rejeitado em register (serializer **e** HTTP) e PATCH; PII anônima negada
      (já coberto nas Phases 1/2, verificado)
- [x] `_exchange_code` com `requests.post` mockado; audience errado coberto; branches de permission
      allow+deny
- [x] Nenhum teste afirma comportamento inseguro como esperado
- [x] `pytest` verde sem depender de linhas só-de-import

## Notas

- Sem deploy: test-only, nenhum runtime alterado.
- `views.py` segue em 88% (branches de erro/redirect das views OAuth) — fora do escopo do #50
  (issue lista `permissions.py` e `google_oauth.py`); candidato a um slice futuro se necessário.
- Próximo em 07-tests (ordem por risco): **#17** (assinatura de webhook Stripe — patch em
  `stripe.Webhook.construct_event`, um nível abaixo do `verify_webhook_signature` sempre mockado;
  asserir raw body + `Stripe-Signature` + `STRIPE_WEBHOOK_SECRET`), depois **#34/#35** (enrollments),
  **#86** (core), **#26/#72** (menores). Depois `08-lint-style` (batch) + videos #60.
