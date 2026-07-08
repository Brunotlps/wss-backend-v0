# Slice: wrap 123-char f-string in LessonProgressSerializer (#180)

**Data:** 2026-07-08
**Branch:** `fix/enrollments-fstring-wrap-180` (a partir de `main`) → **PR #232 (squash → `main`,
commit `5ecf642`)**
**Layer:** mesma classe do `08-lint-style` #21 (payments), sem playbook próprio — follow-up do
baseline do #37, 2026-07-02
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-08)**.

## Contexto

A mensagem de `ValidationError` de `watched_duration` em `LessonProgressSerializer.validate()`
era uma única f-string de 123 caracteres, acima do limite de 88 (`code-style.md`). `.flake8`
extend-ignora E501 e o black não quebra literais de string, então escapava dos dois linters.
Mesma classe do fix já feito em payments (#21, `Payment.__str__`).

## Fix (#180)

- `apps/enrollments/serializers.py:401-409` — f-string quebrada em duas via concatenação
  implícita de literais, ambas ≤88 chars, mensagem final idêntica (sem mudança de comportamento).

## TDD

- **Sem RED tradicional** — é fix puramente de formatação/line-length, sem mudança de
  comportamento (mesmo precedente do #21). Em vez de RED→GREEN, estendida a asserção do teste
  existente `test_create_progress_watched_exceeds_duration_returns_400` pra também travar o texto
  exato da mensagem (`response.data["watched_duration"][0]`), prevenindo que um reformat futuro
  mude a wording silenciosamente.

## Verificação

- `pytest apps/enrollments/`: **85 passed**. flake8/black/isort limpos.
- `makemigrations --check --dry-run`: sem drift (não é mudança de model).
- **code-reviewer:** **APPROVE**, 0 findings. Verificou programaticamente a equivalência
  byte-a-byte da string concatenada pra vários valores de `lesson.duration` (0, 1, 7.5, 100, "10"),
  confirmou todas as linhas ≤88 chars (máximo 85), e traçou o comportamento do DRF confirmando que
  `ValidationError({"watched_duration": "..."})` levantado dentro de `.validate()` produz
  `errors == {"watched_duration": [ErrorDetail("...")]}` — a asserção do teste acessa a chave
  certa.

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-08):** health `200`; `inspect.getsource` via shell do container
  confirmou o fragmento da mensagem quebrada presente e a f-string de uma linha antiga ausente.

## Notas

- Minor residual da auditoria original baixa **2 → 1** (resta só #183, venv shebangs — pode nem
  precisar de fix de código, só documentação).
