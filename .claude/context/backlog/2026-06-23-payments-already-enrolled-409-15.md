# Slice: "already enrolled" 400 → 409 no create-intent (#15)

**Data:** 2026-06-23
**Branch:** `fix/payments-already-enrolled-409-15` (a partir de `main`) → **PR #132** (squash → `main`)
**Layer:** `05-views-throttling.md` · **Phase 2 (Major)** · 3ª slice do bloco views/throttling
**Status:** mergeado, **deployado e validado em prod 2026-06-23**.

## Bug

`POST /api/payments/create-intent/` retornava **400** quando o usuário já estava matriculado
no curso. Frontends não conseguem distinguir esse conflito de regra de negócio de um erro de
validação (também 400). `api-conventions.md` (Status Codes) manda **409 Conflict** para
"already enrolled". App **prod-live** (payments).

## Fix (cirúrgico — só o status code)

- `apps/payments/views.py` — branch "already enrolled" em `PaymentViewSet.create_intent`
  passa a retornar `HTTP_409_CONFLICT`. Docstring atualizada (separa 400 = course_id ausente /
  curso grátis, de 409 = já matriculado, e 404 = curso inexistente).
- **Inalterados** (erros de validação genuínos): curso grátis → 400; `course_id` ausente → 400.
- Alinha payments à convenção já existente em `enrollments/views.py`, que retorna 409 para a
  mesma regra.
- O 409 retorna **antes** de qualquer chamada Stripe (ordem: serializer → course → free-check →
  enrolled-check → Stripe), então não há cobrança/escrita nesse caminho.

## Verificação

- RED: teste reescrito in-place `test_already_enrolled_returns_400` → `_returns_409`
  (não duplicado); falhou como esperado (view retornava 400).
- `pytest apps/payments/`: **44 passed** (views.py 100% coberto). flake8/black/isort limpos.
  Migration drift: nenhum.
- code-reviewer (diff final): **APPROVE**, 0 Blocking / 0 Major / 0 nits. Confirmou: 409 correto
  por api-conventions.md; único ponto que retorna esse status; free-course 400 intacto; teste
  reescrito, não duplicado.
- **Prod (2026-06-23):** smoke rollback-safe (`scripts/smoke_15_already_enrolled_409.py`,
  atomic+raise, `manage.py shell` no container, via `APIRequestFactory`+`force_authenticate`):
  - curso pago + já matriculado → **409** `detail='Already enrolled in this course.'`
  - nada persistido, **nenhuma chamada Stripe**.

## Done-criteria (`05`, #15)
- [x] "already enrolled" → 409
- [x] free-course 400 e course_id-missing 400 intactos
- [x] teste reescrito para 409
- [x] validado em prod (2026-06-23)

## Notas
- Deploy foi só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- Próximo no Phase 2 views/throttling: **#81** (certificates: download não checa revogação →
  410/403). Depois #57 (videos upload throttle) → #88 (core readiness endpoint).
