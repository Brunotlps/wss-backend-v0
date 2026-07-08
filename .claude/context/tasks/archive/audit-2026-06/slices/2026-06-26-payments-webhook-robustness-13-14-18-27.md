# Slice: Stripe webhook robustness (#13, #14, #18, #27)

**Data:** 2026-06-26
**Branch:** `fix/payments-webhook-robustness-13` (a partir de `main`) → **PR (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · 1ª slice do bloco services/signals/tasks
**Status:** mergeado, **deployado e validado em prod 2026-06-26**.

## Contexto

Primeira slice da camada `06`, no handler **prod-live** do webhook Stripe
(`payment_intent.succeeded`). Quatro findings cohesos, todos no mesmo caminho de sucesso
(`apps/payments/services.py` + `views.py`). O **#16** (persistir FAILED/REFUNDED) foi
**deliberadamente separado** numa slice própria seguinte — ver "Notas".

## Bugs + Fix

- **#13 (Major) — TOCTOU na idempotência.** Era `filter(...).exists()` + `create()`; entrega
  concorrente da Stripe passava os dois workers pelo `.exists()`, um gravava, o outro estourava
  `IntegrityError` → `except Exception` da view → **500 → Stripe re-tenta**.
  Fix: `create()` direto envolto em `except IntegrityError → raise ValueError("already
  processed")`. A janela check-then-create foi **eliminada**; a constraint unique arbitra a corrida.
- **#14 (Major) — float em dinheiro.** `payment_intent["amount"] / 100` gerava float binário.
  Fix: `Decimal(int(payment_intent["amount"])) / 100` (exato; `int()` explícito blinda contra
  float futuro).
- **#18 (Major) — falha permanente vira 500 eterno.** Metadata malformada (`KeyError`) ou
  usuário/curso deletado (`DoesNotExist`) caíam no `except Exception` → 500 → Stripe re-entrega por
  ~3 dias. Fix: nova exceção `NonRetryableWebhookError`; a view loga **ERROR** e devolve **200**
  (Stripe para). Erro transiente (ex.: DB) **continua 500** para retry.
- **#27 (Minor) — defesa amount/currency.** Divergência entre `payment_intent` e `course.price`
  agora loga `warning`, mas **ainda grava** a cobrança real (nunca recusa um charge já capturado;
  o amount é server-controlled na criação do intent).

Refactor de suporte: parse/validação/lookup extraídos para `_resolve_succeeded_intent`
(mantém `handle_payment_success` com complexidade ≤10 — `.flake8` `max-complexity=10`).
Invariantes do **#12** preservados: log ERROR de duplicate-charge (pi_id diferente, já matriculado)
e o `enrollment.payment` nunca é re-apontado (audit trail).

## Verificação

- **RED:** 9 testes novos/reescritos falharam pelo motivo documentado (float≠Decimal;
  `IntegrityError`/`KeyError`/`DoesNotExist` vazando; sem warning; view 500 em vez de 200).
- **GREEN:** `pytest apps/payments/`: **52 passed**. flake8/black/isort limpos (apps/payments).
  Migration drift: nenhum (sem mudança de model). Coverage: payments **99%**, `services.py` 92%
  (>90% crítico; faltantes = `verify_webhook_signature` mockado, gap **#17** fora de escopo).
- **code-reviewer (diff final):** **APPROVE**, 0 Blocking / 0 Major. Confirmou: (1) segurança
  transacional — `IntegrityError` real dentro do `@transaction.atomic` sem savepoint, re-raise
  `ValueError` e rollback do atomic são corretos (sem hazard de needs_rollback, pois nenhuma op de
  DB roda após o catch); (2) ordem de excepts correta — `NonRetryableWebhookError` **não** é
  subclasse de `ValueError`; (3) idempotência sem mudança observável; (4) #12 preservado; (5)
  `Decimal(int)/100` exato e comparação Decimal-vs-Decimal sólida. Aplicados 2 nits baratos
  (`Decimal(int(...))` + docstring `Raises:`).
- **Prod (2026-06-26):** smoke rollback-safe (`transaction.atomic()` + `raise`,
  `docker compose exec -T backend python manage.py shell <`), dados descartáveis via factories:
  - #14 amount = `Decimal('199.90')` exato ✅
  - #13 pi_id duplicado → `ValueError` idempotente (não `IntegrityError`) ✅
  - #18 metadata malformada → `NonRetryableWebhookError` ✅
  - #18 usuário órfão → `NonRetryableWebhookError` ✅
  - #27 amount mismatch → warning + grava R$50,00 ✅
  - #27 currency inesperada (usd) → warning ✅
  - **`==== SMOKE RESULT: ALL PASS ====`**, `Payment rows still 0` (nada persistido).

## Testes adicionados/reescritos

- `tests/test_services.py`: `test_amount_stored_as_exact_decimal` (reescreve o
  `test_amount_converted_from_cents_to_brl` que usava `pytest.approx` e mascarava o bug),
  `test_toctou_create_collision_raises_value_error_not_integrity`,
  `test_missing_metadata_/orphaned_user_/orphaned_course_raises_non_retryable`,
  `test_amount_mismatch_logs_warning_but_records`, `test_unexpected_currency_logs_warning`.
- `tests/test_webhooks.py`: `test_malformed_metadata_returns_200_not_500`,
  `test_orphaned_event_returns_200_not_500`.

## Done-criteria (`06`)
- [x] Duplicatas/concorrência nunca double-charge nem 500 espúrio; dup logada (#13/#12)
- [x] Handler retorna 200 em evento não-retryável; dinheiro em `Decimal` exato (#18/#14)
- [x] Defesa amount/currency com warning, sem recusar cobrança capturada (#27)
- [x] validado em prod (2026-06-26)
- [ ] FAILED/REFUNDED persistidos → **#16, slice dedicada seguinte**

## Notas

- Deploy só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- **#16 separado de propósito:** persistir FAILED keyed no mesmo `stripe_payment_intent_id` (unique)
  colide com um `succeeded` posterior do **mesmo** intent (cartão recusado → reconfirmado) — o
  `get_or_create`/`create` do sucesso acharia o row FAILED e puralaria a matrícula. O fix correto é
  o redesenho do ciclo de vida (`Payment(status=PENDING)` na criação do intent, transição via
  webhook), que merece TDD/review isolados. **Próxima slice.**
- Resto da camada `06` depois do #16: OAuth #43/#44/#47, certificates signals/tasks #78/#79/#80.
  Depois Phase 3 (07-tests — inclui #17 cobertura de assinatura — + 08-lint-style, + videos #60).
- Follow-up aberto: **#136** (`PaymentIntentRateThrottle` mesmo defeito de scope do #57).
