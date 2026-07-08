# Slice: refund handling — charge.refunded (16b of #16, CLOSES #16)

**Data:** 2026-06-26
**Branch:** `feat/payments-refund-handling-16b` (a partir de `main`) → **PR (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · 3ª slice do bloco services/signals/tasks
**Status:** mergeado, **deployado e validado em prod 2026-06-26**. **#16 FECHADO** — lifecycle completo.

## Contexto

2ª e última metade do #16 (Opção A, lifecycle por transições). 16a entregou `pending → succeeded |
failed`; **16b** adiciona `REFUNDED` via `charge.refunded`, fechando o ciclo
`PENDING → SUCCEEDED | FAILED | REFUNDED`.

**Decisão de produto (confirmada por Bruno):** um refund **revoga acesso pago** (desativa o
enrollment), mantendo o registro para auditoria.

## Fix

- **`handle_refund`** ([services.py](../../../backend/apps/payments/services.py)): o objeto do evento
  é um **Charge** (não PaymentIntent), ligado ao nosso row via `charge["payment_intent"]`. Gate
  **estrito** em `charge["refunded"]` (a Stripe seta esse bool só em refund **total**) → marca
  `Payment.REFUNDED` e **revoga acesso** (`enrollment.is_active=False`, registro preservado).
  `select_for_update` + no-op se já REFUNDED → idempotente e race-safe. Refund **parcial** é logado e
  deixado intacto; charge sem/`payment_intent` desconhecido → `NonRetryableWebhookError` (→200).
- **`views.py`**: `post` roteia `charge.refunded` → `_process_refund` (NonRetryable→200,
  transiente→500).

## Verificação

- **RED:** 9 testes novos falharam pelo motivo documentado (`handle_refund` inexistente; view sem
  rotear `charge.refunded`).
- **GREEN:** `pytest apps/payments/`: **70 passed**. flake8/black/isort limpos. **Sem drift** (REFUNDED
  já existia no enum). Coverage payments **99%** (views 100%; services 96% — só `verify_webhook_
  signature` #17 + branch pré-existente de enrollment-link).
- **code-reviewer:** **APPROVE WITH NITS**, 0 Blocking / 0 Major. Confirmou: full-vs-partial correto,
  locking race-safe e interligado com os handlers do 16a (mesmo row), sem hazard transacional,
  dinheiro ok (amounts int só pra comparação; `Payment.amount` não é mutado no refund). Nit principal
  aplicado: gate **estrito** em `charge["refunded"]` (blinda a borda "ambos amounts zero → cairia em
  REFUNDED").
  - **Insight load-bearing:** a revogação realmente corta acesso porque `Enrollment.save()` invalida
    o cache Redis (`enrollment:{user}:{course}`) e `IsEnrolled._check_enrollment_cached` filtra
    `is_active=True` — então `is_active=False` remove o acesso a vídeos. Dependência não-óbvia,
    registrada.
- **Prod (2026-06-26):** smoke rollback-safe (`transaction.atomic()`+`raise`, dados via factories):
  - full refund → REFUNDED + enrollment desativado (log "Access revoked") ✅
  - partial refund → SUCCEEDED mantido, acesso intacto (+warning "Non-full refund") ✅
  - redelivery em já-REFUNDED → no-op idempotente ✅
  - refund sem enrollment → REFUNDED sem erro ✅
  - intent desconhecido → NonRetryableWebhookError ✅
  - **`==== SMOKE RESULT: ALL PASS ====`**, `Payment rows still 0`.

## Testes adicionados (`tests/test_services.py::TestStripeServiceHandleRefund`, `tests/test_webhooks.py`)

- `test_full_refund_marks_refunded_and_revokes_access`, `test_partial_refund_does_not_mark_refunded`,
  `test_refund_is_idempotent_when_already_refunded`, `test_refund_without_enrollment_still_marks_
  refunded`, `test_refund_for_unknown_intent_raises_non_retryable`,
  `test_refund_without_payment_intent_raises_non_retryable`
- view: `test_charge_refunded_event_marks_refunded`, `test_charge_refunded_unknown_intent_returns_200`,
  `test_charge_refunded_transient_error_returns_500`, `test_failed_event_malformed_metadata_returns_200`
  (fecha gap de cobertura herdado do 16a).

## Done-criteria (#16) — COMPLETO ✅
- [x] Lifecycle `PENDING → SUCCEEDED | FAILED | REFUNDED` todo alcançável e persistido
- [x] Refund total → REFUNDED + revoga acesso; parcial não marca total; idempotente/race-safe
- [x] validado em prod (2026-06-26) → **#16 fechado**

## Notas / próximos
- Deploy só-de-código → `docker compose restart backend`.
- **Bloco payments da camada `06` COMPLETO:** #12/#13/#14/#16/#18/#23?/#27 — (obs: **#23**
  fail-fast de keys Stripe/OAuth em settings ainda pendente, é config, não webhook).
- Restante da `06`: **#23** (settings fail-fast), OAuth #43/#44/#47, certificates #78/#79/#80.
  Depois Phase 3 (07-tests inclui #17/#82 + 08-lint-style, + videos #60).
- Deferido (não-bloqueante): teste de concorrência real (Postgres + threads) pros locks de
  payments — candidato a Phase 3 (#82).
