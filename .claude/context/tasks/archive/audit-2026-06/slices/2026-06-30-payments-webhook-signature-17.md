# Slice: Payments webhook signature coverage (#17)

**Data:** 2026-06-30
**Branch:** `test/payments-webhook-signature-17` (a partir de `main`) → **PR #165 (squash → `main`)**
**Layer:** `07-tests.md` · **Phase 3 (hardening & hygiene)** · 3º slice da camada de testes (após #82, #50)
**Status:** mergeado em `main` (commit `757469c`), **validado por CI**. Sem deploy (test-only).

## Contexto

3º slice da Phase 3 / `07-tests`. `verify_webhook_signature` é caminho de segurança crítico
(prod-live, Stripe), mas **todos** os testes de webhook mockavam o método inteiro
(`apps.payments.views.StripeService.verify_webhook_signature`), então nada assertava que
`stripe.Webhook.construct_event` é chamado com o **raw body**, o header `Stripe-Signature` e
`settings.STRIPE_WEBHOOK_SECRET`. Uma regressão (passar o body já parseado, ou o setting errado)
passaria a suíte inteira. RED confirmado: `services.py` linhas **163-171** descobertas.

Mudança **test-only** — nenhum runtime alterado → **sem deploy e sem smoke de prod**; CI é a validação.

## Abordagem (do playbook)

Patchar **um nível abaixo** do método sempre-mockado — `stripe.Webhook.construct_event` — e asserir
os argumentos exatos; mais um teste de **HMAC real** ponta-a-ponta (sem mock) para exercitar o
`construct_event` de verdade.

## Lacunas cobertas (`apps/payments/tests/test_services.py`, classe `TestVerifyWebhookSignature`)

- **Contrato (mock):** patch em `apps.payments.services.stripe.Webhook.construct_event` asserindo
  `assert_called_once_with(payload_bytes, header, "whsec_unit_secret")` + return passado adiante
  (sentinel). Pega regressão que parseie o body, altere o header ou leia o setting errado.
- **HMAC real aceito:** helper `_stripe_signature_header` monta `t=<ts>,v1=<hexdigest>` sobre
  `"{ts}.{rawbody}"` com HMAC-SHA256 (esquema idêntico ao do `stripe`); `construct_event` **não
  mockado** aceita.
- **Adulterado rejeitado:** `v1=deadbeef` → `SignatureVerificationError`.
- **Secret errado rejeitado:** assinatura feita com outro secret → `SignatureVerificationError`.

## Verificação

- **RED (baseline):** `services.py` **96%** (linhas 163-171 = corpo de `verify_webhook_signature`
  descobertas; 341-342 não relacionadas).
- **GREEN:** `pytest apps/payments/`: **74 passed**. `services.py` **99%** (163-171 cobertas; restam
  só 341-342, branch de `handle_payment_success`, fora do escopo do #17). flake8/black/isort limpos.
  Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE**, 0 Blocking / 0 Major. Verificou empiricamente o esquema
  HMAC contra o source instalado `stripe==8.5.0` (`_webhook.py`) e confirmou que os dois testes de
  rejeição batem no branch de HMAC-mismatch (`:82`), não no parse de header — rejeitam pelo motivo
  certo. Nits opcionais sem ação.
- **CI (PR #165):** verde.

## Testes adicionados

- `tests/test_services.py`: helper `_stripe_signature_header` + classe `TestVerifyWebhookSignature`
  (`test_passes_raw_body_signature_and_secret`, `test_real_hmac_signature_is_accepted`,
  `test_tampered_signature_is_rejected`, `test_wrong_secret_is_rejected`).

## Done-criteria (`07-tests`)
- [x] `stripe.Webhook.construct_event` asserido com raw body + `Stripe-Signature` + `STRIPE_WEBHOOK_SECRET`
- [x] teste de HMAC real (aceita válido; rejeita adulterado e secret errado)
- [x] caminho crítico de pagamento ≥90% (services 99%)
- [x] nenhum teste afirma comportamento inseguro como esperado
- [x] `pytest` verde sem depender de linhas só-de-import

## Notas

- Sem deploy: test-only, nenhum runtime alterado.
- `verify_webhook_signature` não muda; a classe `TestVerifyWebhookSignature` **não** usa
  `@pytest.mark.django_db` (sem acesso ao DB) — deliberado e consistente com as classes de serviço
  puras do arquivo.
- Próximo em 07-tests (ordem por risco): **#34/#35** (enrollments — progress API POST/PATCH +
  remover/reescrever o teste obsoleto `test_enrollment_created_without_payment_verification`), depois
  **#86** (core), **#26/#72** (menores). Depois `08-lint-style` (batch) + videos #60.
