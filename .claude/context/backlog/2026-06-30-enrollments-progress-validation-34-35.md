# Slice: Enrollments progress API + validation coverage (#34, #35)

**Data:** 2026-06-30
**Branch:** `test/enrollments-progress-validation-34-35` (a partir de `main`) → **PR #167 (squash → `main`)**
**Layer:** `07-tests.md` · **Phase 3 (hardening & hygiene)** · 4º slice da camada de testes (após #82, #50, #17)
**Status:** mergeado em `main` (commit `abaa1f6`), **validado por CI**. Sem deploy (test-only).

## Contexto

Slice de **irmãos** (mesmo app) em um PR. `serializers.py` estava em 87% (subiu de 72% pós #31/#29) com
os branches de regra de negócio críticos descobertos, e a escrita via progress API (POST/PATCH) sem
teste; além disso um teste de model afirmava um "bug" que não existe mais.

Mudança **test-only** — nenhum runtime alterado → **sem deploy e sem smoke de prod**; CI é a validação.

## #34 — progress API + branches de validação

Cobertos via `/api/progress/` e `/api/enrollments/`:
- **deny:** progress em enrollment de outro usuário → 400 (guard de owner no serializer, `serializers.py`
  ~373); `watched_duration` negativo → 400; `watched_duration` > `lesson.duration` → 400 (POST **e**
  PATCH, ~388); rating fora de faixa → 400; review sem lição completa → 400 (~540).
- **success:** PATCH resume (`watched_duration` + `last_watched_at`, ~427/445-450); PATCH complete
  (`completed_at` + duração cheia); completed com duração parcial é **capado** para a duração da lição
  (395-396); review após lição completa; `next_lesson` exposto no detail (220).
- **end-to-end:** completar todas as lições auto-completa o enrollment e **enfileira a task de
  certificado** (`generate_certificate_pdf_async.delay` mockado; assere `completed` + delay 1× +
  `next_lesson` None).
- `test_serializers.py` (novo): unit tests diretos de 3 guards de **defesa-em-profundidade** que o
  caminho da API sombreia — `watched_duration` negativo (PositiveIntegerField rejeita antes no DRF),
  rating fora de faixa (MaxValueValidator(5) rejeita antes), e **update por não-dono** (a view filtra
  não-donos com 404 antes do `validate` rodar → o guard do serializer é o único lugar da regra).

## #35 — teste obsoleto reescrito

`test_enrollment_created_without_payment_verification` afirmava um "bug" (enrollment de curso pago sem
pagamento) que **não existe**: o 402 é enforçado na **view** (`EnrollmentViewSet.create`, testado em
`test_create_enrollment_paid_course_without_payment_returns_402`). Reescrito para
`test_model_allows_paid_enrollment_without_payment_by_design`, documentando o split model-permissivo /
view-enforçado (o model fica permissivo de propósito para o webhook Stripe usar `get_or_create`).

## Verificação

- **RED (baseline):** `serializers.py` **87%** (220, 337, 373, 388, 395-396, 427, 445-450, 506, 535,
  540-541 descobertas); teste de model obsoleto afirmava bug inexistente.
- **GREEN:** `pytest apps/enrollments/`: **82 passed**. `serializers.py` **100%**, `views.py` **100%**,
  app enrollments **99%** (resta só `models.py:297`, divisão de `progress_percentage`, pré-existente e
  fora de escopo). flake8/black/isort limpos. Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE WITH NITS**. **1 Major corrigido** — dois testes novos de
  conclusão disparavam geração **real** de PDF sob Celery eager (`CELERY_TASK_ALWAYS_EAGER=True` no dev
  + `MEDIA_ROOT` não sobrescrito nos testes escrevia PDFs em `media/certificates/`); agora mockam
  `generate_certificate_pdf_async.delay` (como o end-to-end já fazia). 2 Minor aplicados (asserir a
  chave de erro `"enrollment"`/`"review"` para fixar o branch certo). Os 3 unit tests de serializer
  confirmados legítimos (não-tautológicos); o de não-dono é o mais valioso (única cobertura da regra).
- **CI (PR #167):** verde.

## Testes adicionados/reescritos

- `tests/test_views.py`: progress deny/success + end-to-end conclusão→certificado + next_lesson +
  rating fora de faixa + review sem/com lição completa.
- `tests/test_serializers.py` (novo): `TestLessonProgressValidators`, `TestEnrollmentUpdateValidators`.
- `tests/test_models.py`: `test_model_allows_paid_enrollment_without_payment_by_design` (substitui o
  obsoleto, #35).

## Done-criteria (`07-tests`)
- [x] progress API POST/PATCH (success, wrong-owner, watched>duration, foreign-course já coberto) +
      end-to-end conclusão→certificado com `.delay` mockado (#34)
- [x] teste obsoleto reescrito; não afirma bug inexistente (#35)
- [x] serializers enrollments ≥80% (100%)
- [x] nenhum teste afirma comportamento inseguro/velho como esperado
- [x] `pytest` verde sem depender de linhas só-de-import

## Notas

- Sem deploy: test-only, nenhum runtime alterado.
- Gotcha registrado: testes que completam **todas** as lições de um curso disparam a cadeia de signal
  `check_course_completion → mark_as_completed → certificado`; sob Celery eager isso gera PDF real →
  sempre mockar `generate_certificate_pdf_async.delay` nesses testes. (4 PDFs residuais restantes vêm de
  testes **pré-existentes** — `test_signals.py` / o `test_create_completed_progress` legado — fora do
  escopo deste slice.)
- Próximo em 07-tests: **#86** (core — TimeStampedModel behavioral test + health check HEAD/contract),
  depois **#26/#72** (menores). Depois `08-lint-style` (batch) + videos #60.
