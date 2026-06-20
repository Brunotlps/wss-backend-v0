# Slice: Certificate imutável/durável via snapshot denormalizado (#77)

**Data:** 2026-06-18
**Branch:** `fix/certificates-snapshot-immutable`
**PR:** #108 (squash merge → `0404364` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `certificate-trust` (Fatia 2 de 2) — **ÚLTIMA Blocking**
**Playbook dono:** `02-models.md`
**Status:** mergeado; CI verde (lint + migration check + suíte PostgreSQL). **Tem migration 0004 + backfill.**

## Issue atacada

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #77 | Blocking (integridade — doc legal) | certificates | Campos exibidos (`student_name`, `course_title`, `instructor_name`, `completion_date`) eram lookup vivo via `enrollment→user/course/instructor` → renomear curso/usuário reescrevia retroativamente um certificado já emitido (e a resposta de verificação pública) |

## O que foi implementado

### Model — `models.py`
- 4 campos write-once: `student_name_snapshot`, `course_title_snapshot`, `instructor_name_snapshot`
  (CharField, blank default ""), `completion_date_snapshot` (DateTimeField null).
- Properties `student_name/course_title/instructor_name/completion_date` reescritas: **preferem o
  snapshot**, fallback p/ lookup vivo só se vazio; guard `enrollment_id` (seguro p/ futuro #38).
  Sem colisão de nome (campos `*_snapshot` vs properties bare).

### Signal — `signals.py`
- Popula os 4 snapshots **uma vez** na emissão (a partir do enrollment); nunca reescreve.
  Imutabilidade **por convenção** (sem hook de save, decisão do Bruno via AskUserQuestion).

### Migration `0004_certificate_completion_date_snapshot_and_more`
- `AddField`×4 + `RunPython` **backfill** idempotente (reverse=noop) dos certs existentes a partir
  do lookup vivo atual. Helper `_full_name` espelha `User.get_full_name() or email` (models
  históricos não têm métodos). Deps cross-app (`courses 0003`, `enrollments 0003`, `users 0002`)
  p/ o estado histórico ter `instructor`/`title`/`completed_at` (sem isso, FieldError no backfill).

### Testes — `tests/test_signals.py`
- `test_signal_populates_snapshot_at_issue`; `test_issued_certificate_is_immutable` (renomeia
  curso+usuário, doc inalterado); `test_property_falls_back_to_live_lookup_when_snapshot_empty`.
- (Teste de instrutor-nulo descartado: `Course.instructor` é CASCADE não-nullable; estado impossível
  hoje — guards defensivos mantidos p/ futuro #38.)

## Verificação
- `pytest apps/certificates/`: **45 passed** · coverage `apps.certificates` 81% (model 88%,
  signals 100%; migration RunPython 41% = data migration não exercida em DB de teste vazio; utils
  PDF pré-existente). Migration drift: limpo.
- `flake8 / black --check / isort --check`: limpos.
- code-reviewer: **APPROVE**, zero Blocking (diff final). Nits acatados: comentário de coupling no
  `_full_name`.
- CI (#108): lint + migration check + suíte PostgreSQL verdes.

## Done-criteria (02)
- [x] Certificado renderiza do próprio snapshot; editar curso/usuário não muda doc emitido nem a verificação.
- [x] Backfill dos certs existentes (com fallback p/ legado).
- [x] Migration revisada.
- [ ] `on_delete` SET_NULL/PROTECT = **#38** (separado, NÃO re-litigado). Durabilidade total contra delete só com #38.

## Próximos passos
- **Milestone Blocking: 16/16 ✅ ZERADO.**
- **Pré-deploy:** escrever data migration `0005` de backfill do `is_valid` (#73 follow-up) — setar
  `is_valid=True WHERE is_valid=False AND pdf_generation_failed_at IS NULL`, senão certs legítimos
  com PDF pendente/falho seriam reportados como "revogados".
- **Deploy do lote #102–#108 + 0005** no VPS (Bruno executa, eu preparo runbook): migrations
  0003/0004/0005, rebuild backend, migrate, restart Celery, validação smoke.
- Depois: Phase 2 (Major) — `/audit-status`.
