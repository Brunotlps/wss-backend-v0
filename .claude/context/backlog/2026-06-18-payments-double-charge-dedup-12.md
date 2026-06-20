# Slice: Double-charge — dedupe de PaymentIntent + alerta de cobrança duplicada (#12)

**Data:** 2026-06-18
**Branch:** `fix/payments-double-charge-dedup`
**PR:** #106 (squash merge → `3e9866c` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `transactional-integrity` (**FECHA o tema, 4/4**)
**Playbook dono:** `06-services-signals-tasks.md`
**Status:** mergeado; CI verde (lint + suíte PostgreSQL). ⚠️ Stripe **live** em produção.

## Issue atacada

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #12 | Blocking (money) | payments | Duas superfícies de double-charge: criação sem `idempotency_key` (2 abas/retry → 2 intents vivos → cartão cobrado 2×) e webhook que gravava 2º `Payment` (pi_id diferente) p/ usuário já inscrito **silenciosamente**, sem alerta/refund |

## Escopo (conservador, acordado com Bruno via AskUserQuestion)
- **Auto-refund:** diferido (decisão de produto; movimentação de dinheiro irreversível em live).
- **Reuso de intent pendente:** fora — só `idempotency_key` (cobre o caso comum sem persistir estado).

## O que foi implementado — `backend/apps/payments/services.py`

### A — Prevenção na criação
`create_payment_intent`: `idempotency_key=f"pi:{user.id}:{course.id}"` no `PaymentIntent.create`.
Chamadas repetidas (mesma aba/retry) dentro da janela de 24h da Stripe retornam o **mesmo** intent
→ uma cobrança só. (Stripe rejeita key reusada com body divergente → erro alto, não double-charge.)

### B — Backstop no webhook (defense-in-depth)
`handle_payment_success`: novo branch `elif not created:` — já-inscrito **com** payment vinculado +
2º intent succeeded (pi_id diferente) → `logger.error(...)` alertável (Sentry) + `return`. O 2º
`Payment` é **mantido** como trilha de auditoria p/ refund manual; o link original
(`enrollment.payment`) nunca é repontado.

### Testes (TDD, RED→GREEN, Stripe mockado) — `tests/test_services.py`
- `test_uses_deterministic_idempotency_key`: confirma a key passada ao `PaymentIntent.create`.
- `test_second_succeeded_for_enrolled_user_logs_error`: 2º succeeded → ERROR logado, enrollment não
  duplicada, `Payment` gravado, e **link original intacto** (`pi_first`).

## Verificação
- `pytest apps/payments/`: **44 passed** · coverage `apps.payments` 98% (código novo coberto;
  gaps 122-130/191-193 são pré-existentes — `verify_webhook_signature` e link-branch, cobertos no
  view layer).
- `flake8 / black --check / isort --check`: limpos.
- code-reviewer: **APPROVE**, zero Blocking — sobre o diff final; 3 nits acatados (wording do
  comentário, `import logging` no topo, assert do invariante de audit-trail).
- CI (#106): lint + suíte PostgreSQL verdes.

## Done-criteria (06)
- [x] Webhook duplicado não dá double-record silencioso — logado/alertado (ERROR).
- [x] Criação não gera 2º intent no caso comum (idempotency_key).

## Follow-ups (NÃO neste slice)
1. **Auto-refund** do intent duplicado — decisão de produto (criar issue).
2. **Reuso/consulta de intent pendente** (janela > 24h).
3. Irmãs de robustez do webhook: **#13** (get_or_create race no Payment), **#14** (Decimal vs
   float no amount), **#16** (persistir FAILED/REFUNDED), **#18** (retryable vs não-retryable → 200).

## Próximos passos
- Tema `transactional-integrity` **fechado (4/4)**. Blocking milestone: **13/16**.
- Resta só o tema **certificate-trust** (#73/#75/#77, playbook `02-models.md`) para zerar os
  Blocking. Issues acopladas (snapshot/imutabilidade, código cripto, split do `is_valid`) —
  revisar se viram 1 ou mais fatias.
