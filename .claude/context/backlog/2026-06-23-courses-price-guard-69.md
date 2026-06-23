# Slice: Soft-freeze de preço + action adjust-price auditada (#69)

**Data:** 2026-06-23
**Branch:** `fix/courses-price-guard-69` (a partir de `main`) → **PR #130** (squash → `main`)
**Layer:** `05-views-throttling.md` · **Phase 2 (Major)** · 2ª slice do bloco views/throttling
**Status:** mergeado, **deployado e validado em prod 2026-06-23**.
**Decisão de produto:** registrada (soft-freeze + adjust-price auditado) — não re-litigada.

## Contexto (não há bug financeiro)

Mudar `course.price` **não** re-cobra alunos já matriculados: o valor pago é fixado em
`Payment.amount` (gravado pelo webhook do Stripe) e o acesso é gated pela existência de um
`Payment` SUCCEEDED, **não** pelo preço atual. `course.price` é lido só no momento da
compra/matrícula → é o "preço de tabela" para compras **futuras**. A preocupação é
integridade de negócio / relação com cliente, não cobrança.

## Fix (soft-freeze no update + action auditada)

- `apps/courses/serializers.py`:
  - `CourseUpdateSerializer.validate` — soft-freeze: se `price` está no payload, difere do
    atual **e** `instance.get_enrolled_count() > 0` → `ValidationError` (400) direcionando à
    action. Sem matrículas, PATCH de preço segue livre. (No-op de mesmo valor não bloqueia.)
  - novo `AdjustPriceSerializer` (`Serializer`): `new_price` DecimalField
    (max_digits=10, decimal_places=2, `min_value=Decimal("0.00")`) → negativo vira 400;
    `confirm` BooleanField(default=False).
- `apps/courses/views.py`:
  - `@transaction.atomic @action(POST, url_path="adjust-price")` em `CourseViewSet`.
  - Owner-only via `IsCourseOwnerOrReadOnly` (POST não-SAFE + `self.get_object()` →
    `has_object_permission` → 403 para não-dono; curso é criado `is_published=True` no teste/smoke
    para o não-dono enxergar e dar 403 genuíno, não 404).
  - Matrículas ativas + sem `confirm` → 400. Caso ok → aplica preço
    (`save(update_fields=["price", "updated_at"])`), loga audit
    (`old → new`, ator, enrolled_count) via `logging.getLogger(__name__)`, retorna 200.

## Verificação

- RED: `TestCoursePriceGuard` — 6/7 falharam como esperado (soft-freeze ausente; action 404).
- `pytest apps/courses/`: **75 passed** (68 + 7). flake8/black/isort limpos. Migration drift: nenhum.
- code-reviewer (diff final): **APPROVE WITH NITS**, 0 Blocking / 0 Major. Verificou owner-only
  real (403, não 404 mascarado) e `update_fields`+`auto_now` correto. Nit aplicado:
  `@transaction.atomic` na action.
- **Prod (2026-06-23):** smoke rollback-safe (`scripts/smoke_69_adjust_price.py`, atomic+raise,
  via `manage.py shell` no container) — exercitou o code path real (`APIRequestFactory` +
  `force_authenticate`):
  - owner sem matrícula, sem confirm → **200**, price 100→120
  - matriculado, sem confirm → **400**, price inalterado (120)
  - matriculado + confirm → **200**, price 120→200
  - não-dono → **403**
  - negativo → **400**
  - audit log emitido; **nada persistido** (rollback).

## Testes adicionados (`apps/courses/tests/test_views.py::TestCoursePriceGuard`)

PATCH preço bloqueado c/ matrícula (400) · PATCH preço livre s/ matrícula (200) ·
adjust owner s/ matrícula (200) · adjust c/ matrícula s/ confirm (400) ·
adjust c/ matrícula + confirm (200) · não-dono (403) · preço negativo (400).
Cada um afirma o preço persistido (`refresh_from_db`), não só o status.

## Done-criteria (`05`, #69)
- [x] `price` read-only no PATCH normal quando há matrículas ativas (soft-freeze)
- [x] action `adjust-price` owner-only + `confirm` obrigatório c/ matrículas + valida ≥0 + audit log
- [x] matrículas existentes intactas (`Payment.amount` é a fonte da verdade)
- [x] validado em prod (2026-06-23)

## Notas
- Deploy foi só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- Nuance 409-vs-400: o playbook/decisão fixa **400** para "active enrollments without confirm";
  `api-conventions.md` sugeriria 409, mas o contrato fica em 400 (testes encodam 400).
- Audit é `logger.info` (não-durável). Se virar requisito real, próximo passo = modelo persistido.
- Próximo no Phase 2 views/throttling: **#15** (payments "already enrolled" 400→409) — atenção,
  app prod-live. Depois #81 → #57 → #88.
