# Slice: Enrollment create — 409 em duplicata + bloqueio de mass-assignment (#28, #30)

**Data:** 2026-06-18
**Branch:** `fix/enrollments-create-409-mass-assignment`
**PR:** #104 (squash merge → `c1dbcb9` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `transactional-integrity` (`.claude/context/audit/remediation/00-plan.md`)
**Playbook dono:** `05-views-throttling.md` (#28) + `03-serializers.md` (#30)
**Status:** mergeado; CI verde (lint + suíte PostgreSQL).

## Issues atacadas

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #28 | Blocking | enrollments | POST duplicado levantava `IntegrityError` (UNIQUE user_id+course_id) → **500** em vez de **409**. Test antigo mascarava o bug (enviava `{"course"}` em vez de `course_id` → 400) |
| #30 | Blocking | enrollments | `create` usava `EnrollmentDetailSerializer` → `completed/rating/review/is_active` graváveis no POST → enrollment "concluído"/auto-avaliado, burlando as regras do update serializer (caminho p/ certificado fraudulento) |

## O que foi implementado

### Serializers — `backend/apps/enrollments/serializers.py`
- Novo `EnrollmentCreateSerializer`: só `course_id` gravável. `is_active`/`completed` em
  `read_only_fields`; `completed_at`/`certificate_issued`/`rating`/`review` ausentes de `fields`
  → assumem defaults do model. Resposta 201 útil (`id`, `course` aninhado, `enrolled_at`,
  `is_active`, `completed`).

### Views — `backend/apps/enrollments/views.py`
- `get_serializer_class`: action `create` → `EnrollmentCreateSerializer`.
- `create()`: pre-check `Enrollment.objects.filter(user, course).exists()` → **409**; `perform_create`
  envolto em `try/except IntegrityError` → **409** (fecha o race TOCTOU contra o unique constraint).
- Ordem **409 antes de 402**: já-inscrito tem precedência sobre cobrança.
- Import de `IntegrityError`; docstring da classe atualizado (lista os 4 serializers).

### Testes (TDD, RED→GREEN) — `apps/enrollments/tests/test_views.py`
- `test_cannot_enroll_twice_in_same_course`: reescrito (`{"course"}`/400 → `course_id`/**409**).
- `test_create_ignores_system_managed_fields` (novo): POST com `completed/rating/review/is_active`
  → 201 + defaults preservados (`completed=False`, `rating=None`, `review=""`, `is_active=True`).
- `test_duplicate_enrollment_race_returns_409` (novo): mocka `perform_create` p/ levantar
  `IntegrityError` → 409 (cobre a branch TOCTOU; `views.py` 100%).

## Verificação
- `pytest apps/enrollments/`: **63 passed** · coverage `apps.enrollments` 95% (`views.py` 100%).
- `flake8 / black --check / isort --check`: limpos.
- code-reviewer: **APPROVE**, zero Blocking — rodado **2×** (fix principal + re-review do diff
  final após adicionar o teste TOCTOU + docstring, a pedido do Bruno).
- CI (#104): lint + suíte PostgreSQL verdes.

## Done-criteria
- [x] #28: duplicata → 409 (não 500), caminho normal e race.
- [x] #30: campos system-managed ignorados no POST (deny-test confirma defaults).
- [x] Ordem 409-antes-de-402 validada.

## Follow-ups (NÃO resolvidos aqui)
1. **[Minor — ACEITO]** `format="json"` inconsistente entre os 3 testes de create (cosmético,
   PK serializa bem form-encoded). Sem ação.
2. **[Processo]** O gate (code-reviewer) deve rodar sobre o **diff final**, não só sobre o fix
   antes de acatar nits. Nesta fatia re-rodamos a pedido do Bruno. Manter como padrão.

## Próximos passos
- Tema `transactional-integrity` 2/4 (restam #29, #12). Blocking milestone: 11/16.
- Candidatas: **#29** (cross-course lesson progress → conclusão/certificado fraudulento,
  `03-serializers` + `06` signal) ou **#12** (double-charge: dedupe de PaymentIntent + webhook
  idempotente, `06-services`). PRs próprios — fluxos distintos.
