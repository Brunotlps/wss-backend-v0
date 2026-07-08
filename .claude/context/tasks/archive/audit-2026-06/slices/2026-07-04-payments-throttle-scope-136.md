# Slice: PaymentIntentRateThrottle dedicated scope (#136)

**Data:** 2026-07-04
**Branch:** `fix/payments-throttle-scope-136` (a partir de `main`) → **PR #209 (squash → `main`, commit `bf2ad48`)**
**Layer:** `05-views-throttling.md` · **Phase 3** (residual, follow-up do #57)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-04)**.

## Fix (#136)

- **throttles.py** — `PaymentIntentRateThrottle(UserRateThrottle)` herdava `scope = "user"` (default
  de `UserRateThrottle`), então a chave de cache `throttle_user_<id>` era **a mesma** do throttle
  global `user` (1000/hour, `config/settings/base.py`). Tráfego autenticado comum corroía a cota de
  10/dia de create-intent, e vice-versa — mesmo defeito já corrigido no #57
  (`videos/throttles.py::UploadRateThrottle`, scope `video_upload`).
  Fix: `scope = "payment_intent"` como atributo de classe, ao lado de `rate = "10/day"` (já na
  classe, então `get_rate()` nunca consulta `DEFAULT_THROTTLE_RATES` — sem entrada nova em settings).

## TDD

- **RED:** `test_create_intent_limit_isolated_from_other_authenticated_requests` — 15
  `GET /api/payments/` (tráfego comum autenticado) antes das 10 criações de intent; falhou como
  esperado (429 na criação por causa das GETs comuns compartilhando o bucket).
- **GREEN:** após o fix, as 10 criações de intent sucedem normalmente mesmo com as 15 GETs
  intercaladas.

## Verificação

- `pytest apps/payments/`: **75 passed**, cobertura app **99%** (`throttles.py` 100%).
- flake8/black/isort limpos em `apps/payments/`.
- Confirmado: sem colisão de scope com outros throttles do projeto (`payment_intent`, `video_upload`,
  `verify`, `health`, `login`, `register`, `oauth` + built-ins DRF); `DEFAULT_THROTTLE_RATES` sem
  entrada nova necessária (mesma história do #57); `PaymentViewSet.get_throttles()` só sobrescreve
  para `create_intent`, então o GET de list realmente exercita o bucket global `user` (teste não é
  vácuo); testes existentes (`test_allows_up_to_10...`, `test_different_users...`) continuam válidos
  (mesmo bucket, só renomeado).
- **code-reviewer:** **APPROVE**, 0 findings blocking/should-fix (1 nit opcional sobre comentário no
  teste, não acionável).

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-04):** health `200`; shell do container confirmou
  `PaymentIntentRateThrottle.scope == "payment_intent"` e `.rate == "10/day"` no código deployado.

## Notas

- Fecha o último item pendente da camada `05-views-throttling` (residual do #57). Major residual da
  auditoria original baixa **4 → 3** (restam #59, #32, #33 — todos em `enrollments`/`videos`,
  ligados a decisões de produto/latência, não fixes mecânicos).
