# Slice: payment lifecycle PENDING→SUCCEEDED/FAILED (16a of #16)

**Data:** 2026-06-26
**Branch:** `feat/payments-lifecycle-pending-failed-16a` (a partir de `main`) → **PR (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · 2ª slice do bloco services/signals/tasks
**Status:** mergeado, **deployado e validado em prod 2026-06-26**. **#16 permanece ABERTO** (refund → 16b).

## Contexto

#16 (audit trail só registrava sucessos; `PENDING`/`FAILED`/`REFUNDED` inalcançáveis) decidido como
**Opção A — ciclo de vida com transições** e **dividido** para isolar risco em código de dinheiro
prod-live:

- **16a (esta slice):** lifecycle `pending → succeeded | failed`.
- **16b (próxima):** refund (`charge.refunded` → REFUNDED), que **fecha** o #16.

Por que dividir: persistir FAILED keyed no `stripe_payment_intent_id` (unique) colidiria com um
`succeeded` posterior do mesmo intent (recusa→reconfirmação). A solução correta é transicionar **um
row por intent**, não criar rows novos por status.

## Fix

- **`create_payment_intent`** ([services.py](../../../backend/apps/payments/services.py)): persiste
  `Payment(status=PENDING)` via `get_or_create(stripe_payment_intent_id=intent.id, ...)` após a
  criação do intent na Stripe — idempotente a retry/segunda-aba (o `idempotency_key` determinístico
  retorna o mesmo `intent.id`). Write envolto em try/except defensivo: o intent já existe na Stripe,
  então uma falha de DB **não** quebra o checkout (loga; o fallback-create do webhook recupera o row).
- **`handle_payment_success`**: deixa de criar e passa a **transicionar** PENDING/FAILED→SUCCEEDED com
  `select_for_update` (serializa entregas concorrentes; idempotência = "já SUCCEEDED? → ValueError").
  Fallback `create()`+`except IntegrityError→ValueError` quando não há row (webhook antes do commit do
  PENDING / intent out-of-band). Invariantes do **#12** (log ERROR de duplicate-charge + `enrollment.
  payment` nunca re-apontado) preservados.
- **`handle_payment_failed`** (novo): `get_or_create(...FAILED)`; se o row já existia, `select_for_
  update` + transição →FAILED, **nunca rebaixando** um SUCCEEDED (loga warning e no-op). Sem enrollment.
- **`_resolve_succeeded_intent`→`_resolve_intent_context`** (compartilhado pelos dois handlers; mantém
  #18 NonRetryable + #14 Decimal + #27 warning).
- **`views.py`**: `post` despacha para `_process_succeeded`/`_process_failed` (mantém complexidade
  ≤10, `.flake8` `max-complexity=10`); `payment_intent.payment_failed` agora persiste FAILED e
  retorna 200, transiente → 500.

## Verificação

- **RED:** 8 testes novos falharam pelo motivo documentado (PENDING não criado; transição virava
  ValueError de colisão; `handle_payment_failed` inexistente; view sem persistir FAILED).
- **GREEN:** `pytest apps/payments/`: **60 passed**. flake8/black/isort limpos. **Sem drift de
  migração** (nenhuma mudança de model — todos os status já existiam no enum). Coverage payments
  **99%** (services 94%; faltantes = `verify_webhook_signature` #17 + branch pré-existente de
  enrollment-link, ambos fora de escopo).
- **code-reviewer:** **APPROVE WITH NITS**, 0 Blocking / 0 Major. Confirmou: locking correto (FAILED
  não clobbera SUCCEEDED; idempotência sob lock; sem lost-update no race succeeded×failed), fallback
  sem hazard de transação quebrada, `update_fields=["updated_at"]` correto (auto_now), get_or_create
  com savepoint correto, #12/#13/#14/#18/#27 preservados. 3 nits aplicados (wrap defensivo do PENDING,
  docstring da view, concat de string).
- **Prod (2026-06-26):** smoke rollback-safe (`transaction.atomic()`+`raise`, Stripe mockado no
  `create_intent`, dados via factories):
  - create_intent persiste PENDING ✅
  - success transiciona PENDING→SUCCEEDED sem duplicar row (+enrollment) ✅
  - 2ª entrega succeeded → ValueError idempotente ✅
  - failed sem row → FAILED ✅
  - failed PENDING→FAILED ✅
  - failed nunca rebaixa SUCCEEDED (+warning) ✅
  - **`==== SMOKE RESULT: ALL PASS ====`**, `Payment rows still 0`.

## Testes adicionados (`tests/test_services.py`, `tests/test_webhooks.py`)

- `test_persists_pending_payment_on_intent_creation`, `test_pending_payment_is_idempotent_on_retry`,
  `test_pending_write_failure_does_not_break_checkout`
- `test_success_transitions_pending_payment_to_succeeded`
- `TestStripeServiceHandlePaymentFailed`: `test_persists_failed_payment_when_no_row_exists`,
  `test_transitions_pending_to_failed`, `test_does_not_downgrade_succeeded_payment`
- `test_payment_failed_event_persists_failed_payment` (reescreve o antigo `..._returns_200`),
  `test_failed_event_transient_error_returns_500`

## Done-criteria (#16)
- [x] PENDING e FAILED alcançáveis e persistidos; lifecycle documentado é real
- [x] Idempotência do sucesso race-safe via lock; sem downgrade do audit trail
- [x] validado em prod (2026-06-26)
- [ ] **REFUNDED → 16b** (`charge.refunded`) — **#16 permanece aberto até o 16b**

## Notas / deferidos (não-bloqueantes)
- Deploy só-de-código → `docker compose restart backend`.
- **Teste de concorrência real** (Postgres + threads pra provar o lock sob contenção): `select_for_
  update` é no-op no sqlite local; lógica validada, prod é Postgres. Candidato a 16b / Phase 3 (#82).
- Redelivery de failed em row já-FAILED não atualiza amount (no-op idempotente intencional) — nota
  pro 16b.
- Próximo: **16b** (refund, fecha #16). Depois OAuth #43/#44/#47 e certificates #78/#79/#80; então
  Phase 3 (07-tests inclui #17/#82 + 08-lint-style, + videos #60).
