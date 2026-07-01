# Slice: Payments reverse_lazy in throttling tests (#26)

**Data:** 2026-06-30
**Branch:** `test/payments-reverse-lazy-26` (a partir de `main`) → **PR #173 (squash → `main`)**
**Layer:** `07-tests.md` · **Phase 3 (hardening & hygiene)** · 7º e **último** slice de `07-tests` (Minor)
**Status:** mergeado em `main` (commit `e8b100e`), **validado por CI**. Sem deploy (test-only).
**→ Camada `07-tests` ENCERRADA.**

## Contexto

`test_throttling.py:27` fazia `URL = reverse("payment-create-intent")` no corpo da classe → resolvia a
URL em tempo de import/coleta, forçando o URLconf inteiro (e as views de todo app) a importar durante a
coleta. Foi exatamente isso que transformou um módulo quebrado no venv (`google-auth`) num erro de
coleta duro da suíte payments inteira. Item Minor do audit.

Mudança **test-only** (refactor de infra de teste) — nenhum runtime alterado → **sem deploy**; CI valida.

## Fix

`reverse` → `reverse_lazy`; `URL = reverse_lazy("payment-create-intent")` (+ comentário do porquê). O
proxy lazy resolve só quando um teste usa `self.URL` no `.post()` — importar o módulo não resolve mais a
URL na coleta. Mesmo valor resolvido, zero mudança de comportamento.

## Verificação

- **GREEN:** `pytest apps/payments/`: **74 passed** (throttling 3/3). Nenhum outro `reverse()` em nível
  de módulo/classe nos testes payments. flake8/black/isort limpos. Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE**, 0 findings. Confirmou drop-in fiel do `reverse_lazy` (o
  test client coage via `str()`/`force_str` antes de montar o request → mesmo valor), que a resolução
  não ocorre mais na definição de classe, e que `test_throttling.py` é o único módulo payments importando
  `django.urls`.
- **CI (PR #173):** verde.

## Testes tocados

- `tests/test_throttling.py`: import + `URL` da classe `TestPaymentIntentThrottling` (2 linhas + comentário).

## Done-criteria (`07-tests`)
- [x] `reverse` não é mais chamado em tempo de import/coleta (usa `reverse_lazy`)
- [x] suíte de throttling continua verde; sem mudança de comportamento

## Notas

- Sem deploy: test-only, nenhum runtime alterado.
- **`07-tests` 100% fechada:** #17, #26, #34, #35, #50, #72, #82, #86 todos mergeados e validados por CI.
- **PRÓXIMO na Phase 3: `08-lint-style`** (batch, todas as apps; inclui o dirt pré-existente de
  `config/urls.py` que o CI não linta) + videos **#60** (serializer docstring vs validation, Minor).
