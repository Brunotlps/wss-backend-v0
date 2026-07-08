# Slice: make Payment.status read-only in admin (#24)

**Data:** 2026-07-07
**Branch:** `fix/payments-admin-status-readonly-24` (a partir de `main`) → **PR #228 (squash →
`main`, commit `9d8e9ed`)**
**Layer:** `02-models.md`
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-07)**.

## Contexto

`PaymentAdmin` já tinha todo campo read-only exceto `status`, e add/delete desabilitados pra
preservar a trilha de auditoria financeira — mas `status` (ex.: SUCCEEDED → REFUNDED) ficava
editável sem log de auditoria. Se intencional (marcação manual de refund), estava indocumentado;
se não, era um buraco na trilha de auditoria.

## Investigação

Grep em `apps/payments/services.py` confirmou que `Payment.status` é movido **exclusivamente**
pelo lifecycle de webhook do Stripe: PENDING→SUCCEEDED (`services.py:335`), →FAILED
(`services.py:435`), →REFUNDED (`services.py:506`), todos disparados pela view de webhook a
partir dos eventos `payment_intent.succeeded`/`payment_intent.payment_failed`/`charge.refunded`.
Nenhum código, management command ou runbook documentado depende de edição manual de status via
admin. Dado isso, escolhida a correção mais conservadora (read-only) em vez de instalar uma
dependência nova (`django-simple-history`) pra um item Minor — mesmo padrão já usado em
`has_add_permission`/`has_delete_permission` (ambos `False`, protegendo a trilha de auditoria).

## Fix (#24)

- `apps/payments/admin.py` — `"status"` adicionado a `readonly_fields`, com comentário inline
  explicando o porquê (lifecycle só-webhook; edição manual desincronizaria do estado real do
  Stripe).

## TDD

- **RED:** `test_status_is_in_readonly_fields` (unit) e
  `test_admin_change_view_does_not_update_status` (integração — POST real na change view do
  admin) falharam contra o código original: `status` não estava em `readonly_fields`, e o POST
  de fato mudava `succeeded` → `refunded` no banco.
- **GREEN:** 2 testes novos em `test_admin.py` (novo arquivo).

## Verificação

- `pytest apps/payments/`: **77 passed** (era 75). flake8/black/isort limpos.
- `makemigrations --check --dry-run`: sem drift (mudança só em `admin.py`, não em model —
  diferente do #62, que mexeu num validator de model field e gerou migração).
- **code-reviewer:** **APPROVE WITH NITS**. Verificou empiricamente (POST real + inspeção de
  response/DB) que a proteção é server-side genuína — Django exclui `readonly_fields` do
  `ModelForm`, um POST forjado não alcança `Payment.save()`. Confirmou via grep que nenhuma
  capacidade legítima foi removida. 1 nit aplicado: teste de integração não checava
  `response.status_code`, então uma regressão futura de permissão/rota (403/404) faria o teste
  passar "por acidente" — corrigido com `assert response.status_code == 302`.

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-07):** health `200`; shell do container confirmou
  `"status" in PaymentAdmin(...).readonly_fields == True` (introspecção pura, sem escrever em
  dado financeiro real — nenhum POST de teste foi feito em prod).

## Notas

- Minor residual da auditoria original baixa **4 → 3** (restam #151, #180, #183).
- Aproveitada a sessão pra aplicar também as edições de playbook do #62 (2026-07-07) que tinham
  ficado sem commit na sessão anterior — combinadas neste mesmo ciclo de docs via `git stash`.
