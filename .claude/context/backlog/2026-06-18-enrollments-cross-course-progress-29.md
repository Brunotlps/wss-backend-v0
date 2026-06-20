# Slice: Cross-course lesson progress → conclusão/certificado fraudulento (#29)

**Data:** 2026-06-18
**Branch:** `fix/enrollments-cross-course-progress`
**PR:** #105 (squash merge → `f2a7efb` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `transactional-integrity` (`.claude/context/audit/remediation/00-plan.md`)
**Playbook dono:** `03-serializers.md` (primário) + `06-services-signals-tasks.md` (defensivo)
**Status:** mergeado; CI verde (lint + suíte PostgreSQL).

## Issue atacada

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #29 | Blocking | enrollments | `LessonProgressSerializer.validate()` checava ownership mas **não** que a `lesson` pertence à `enrollment.course`. O signal de conclusão contava `lesson_progress.filter(completed=True)` contra `course.lessons.count()` → progresso de lições de **outras courses** entrava na conta |

**Exploit verificado:** `POST /api/progress/` com `lesson_id` de outra course + `completed=True` →
201, enrollment auto-completado e task Celery de certificado disparada (certificado sem consumir
o conteúdo; também corrompia `progress_percentage`).

## O que foi implementado (cross-layer †)

### Serializer (primário) — `backend/apps/enrollments/serializers.py`
- `LessonProgressSerializer.validate()`: rejeita **400** quando
  `lesson.course_id != enrollment.course_id`. Cobre create e update (resolve enrollment/lesson de
  attrs-ou-instance; no create os `*_id` são obrigatórios, então o guard sempre roda).

### Signal (defense-in-depth) — `backend/apps/enrollments/signals.py`
- `check_course_completion`: conta só `lesson_progress.filter(completed=True, lesson__course=enrollment.course)`.
  Mesmo que um registro estrangeiro exista (criado antes do guard), nunca completa a enrollment.

### Testes (TDD, RED→GREEN)
- `tests/test_views.py` `test_progress_on_foreign_course_lesson_returns_400`: POST com lição
  estrangeira → 400.
- `tests/test_signals.py` `test_foreign_course_lesson_progress_not_counted`: progresso estrangeiro
  completo → enrollment permanece incompleta.
- Ambos com assert auto-documentado (`foreign_lesson.course_id != enrollment.course_id`).

## Verificação
- `pytest apps/enrollments/`: **65 passed** · coverage `apps.enrollments` 96% (`signals.py` 100%).
- `flake8 / black --check / isort --check`: limpos.
- code-reviewer: **APPROVE**, zero Blocking — rodado sobre o **diff final** (padrão desde #104).
  Reproduziu o exploit em HEAD e confirmou o fix.
- CI (#105): lint + suíte PostgreSQL verdes.

## Done-criteria (03 + 06)
- [x] Progresso com lição de course estrangeira → 400 (validate).
- [x] Signal conta só lições da própria course; conclusão legítima intacta.

## Follow-ups (NÃO resolvidos aqui)
1. **[Minor — pré-existente]** `serializers.py` branch de coerção `completed`/`watched_duration`
   referencia `lesson.duration` fora do `if lesson:`. Só alcançável com `lesson` setado (no create
   é obrigatório); não é regressão. Anotar p/ futuro refactor.

## Próximos passos
- Tema `transactional-integrity` 3/4 (resta **#12**). Blocking milestone: 12/16.
- **#12** (payments, double-charge): dedupe de PaymentIntent (`idempotency_key`) + webhook
  idempotente (`get_or_create`/catch `IntegrityError`). Playbook `06-services-signals-tasks.md`.
  **Atenção redobrada** — produção live com Stripe. PR próprio. Depois: certificate-trust
  (#73/#75/#77).
