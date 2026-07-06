# Slice: Enrollment.is_active semantics — enforcement (#32)

**Data:** 2026-07-04
**Branch:** `fix/enrollments-is-active-semantics-32` (a partir de `main`) → **PR #211 (squash → `main`, commit `d30ea24`)**
**Layer:** `02-models.md` (decisão) + `03-serializers.md`/`06-services-signals-tasks.md` (enforcement) · **Phase 3** (residual, `04-permissions.md` nunca agendado na Phase 2 original)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-04)**.

## Decisão de produto (registrada)

`is_active=False` — hoje setado só em `payments.services.StripeService.handle_refund` (refund total
revoga acesso, mantém a linha pra auditoria) — significa:
- **Bloqueia** acesso a vídeo (já era o caso via `IsEnrolled`)
- **Bloqueia** escrita de novo progresso e conclusão automática do curso
- **NÃO revoga retroativamente** certificado já emitido antes da desativação

## Achado (mais grave que "ambiguidade de nomenclatura")

`LessonProgressSerializer.validate()` só checava ownership (`enrollment.user == request.user`),
nunca `is_active`; `check_course_completion` (signal) também não checava. Um usuário
**reembolsado** continuava conseguindo criar/atualizar `LessonProgress` via
`POST/PATCH /api/progress/` e **completar o curso + gerar certificado depois do refund**. O RED
test provou o exploit completo: `generate_certificate_pdf_async` rodou de verdade pra um enrollment
`is_active=False` antes do fix.

## Fix

- **serializers.py** — `LessonProgressSerializer.validate()` ganha guard após o check de ownership:
  `enrollment` inativo → `ValidationError({"enrollment": "..."})` (400), cobre create e update
  (`enrollment` resolvido de `attrs` no create ou `self.instance.enrollment` no update).
- **signals.py** — `check_course_completion` ganha guard de defesa-em-profundidade (mesmo padrão
  do #29 cross-course) logo após `if enrollment.completed: return` — corta a cadeia
  `mark_as_completed() → Enrollment.save() → create_certificate_on_completion` antes do primeiro elo.
- **models.py** — docstring da classe `Enrollment` documenta a semântica decidida (Attributes,
  não `help_text` — sem migração).

## TDD

- **RED:** 3 testes novos falharam como esperado; `test_inactive_enrollment_not_auto_completed`
  provou o exploit completo (PDF de certificado gerado de verdade) antes do fix.
- **GREEN:** guards bloqueiam create/update via API (400) e o signal nunca completa o enrollment
  inativo.

## Verificação

- `pytest apps/enrollments/`: **85 passed**, cobertura **99%** (`serializers.py`/`signals.py` 100%).
- flake8/black/isort limpos. `makemigrations --check --dry-run`: sem drift (docstring-only).
- **code-reviewer:** **APPROVE** — confirmou que o guard cobre create+update, que a ordem dos
  checks (ownership → is_active → cross-course) não esconde nenhum erro relevante, que a cadeia do
  signal é cortada antes do certificado, e que nenhuma lógica toca `Certificate`/`completed` na
  desativação (sem revogação retroativa). 1 "should fix" aplicado: docstring de `validate()`
  atualizada pra listar a regra nova.

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-04):** health `200`; shell do container confirmou via
  `inspect.getsource` que `serializers.py`/`signals.py` deployados contêm o guard
  `not enrollment.is_active`.

## Notas

- Decisões irmãs no mesmo lote de majors: **#59** (list gating de lessons) fechado como decisão
  documentada — catálogo intencional, sem mudança de código (metadata pública, bytes já gateados
  por `IsEnrolled`). **#33** (cache invalidation em bulk) fechado como decisão documentada —
  nenhum call site de bulk hoje, docstring no model alerta o constraint.
- Major residual da auditoria original baixa **3 → 0** (todos os majors fechados; restam só os 10
  Minor).
