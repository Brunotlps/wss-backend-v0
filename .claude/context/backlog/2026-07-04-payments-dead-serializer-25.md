# Slice: remove dead PaymentIntentResponseSerializer (#25)

**Data:** 2026-07-04
**Branch:** `fix/payments-dead-serializer-25` (a partir de `main`) → **PR #214 (squash → `main`, commit `159991e`)**
**Layer:** `03-serializers.md` · **Phase 3** (residual Minor)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-04)**.

## Fix (#25)

- **serializers.py** — remove `PaymentIntentResponseSerializer` (9 linhas). Nunca foi
  instanciado nem referenciado em lugar nenhum; `create_intent` (`views.py`) sempre retornou o
  dict cru de `StripeService.create_payment_intent()` diretamente via
  `Response(result, status=status.HTTP_200_OK)`.

## Verificação

- Grep repo-wide confirmou zero referências além da própria definição, antes do fix.
- `pytest apps/payments/`: **75 passed**, cobertura **99%** (`serializers.py` 100%).
- flake8/black/isort limpos.
- **code-reviewer:** **APPROVE**, 0 findings — confirmou que `drf-spectacular` (schema OpenAPI,
  `DEFAULT_SCHEMA_CLASS` em `config/settings/base.py`) nunca referenciou essa classe via
  `@extend_schema`, então sem regressão de documentação de API.

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend` (pura remoção de
  código morto, sem mudança de comportamento).
- **Validado em prod (2026-07-04):** health `200`; shell do container confirmou `ImportError` ao
  tentar importar a classe removida.

## Notas

- Fecha o último item da camada `03-serializers` (playbook 100% resolvido, incluindo #25).
- Minor residual baixa **10 → 9** (restam #183, #180, #155, #151, #122, #85, #62, #38, #24).
