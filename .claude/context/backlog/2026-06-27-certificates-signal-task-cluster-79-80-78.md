# Slice: Certificates signal/task hardening (#79, #80, #78)

**Data:** 2026-06-27
**Branch:** `fix/certificates-signal-task-cluster-79-80-78` (a partir de `main`) → **PR (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · slice certificates da camada services/signals/tasks
**Status:** mergeado, **deployado e validado em prod 2026-06-27**.

## Contexto

Cluster certificates da camada `06` (após payments/settings). Três findings coesos em
`apps/certificates/signals.py` + `tasks.py`, com suporte em `models.py`/`admin.py`. O Celery worker
roda de verdade em prod (#110 resolvido), então os caminhos `.delay()` são reais.

**Fork de design (#80), decidido com Bruno:** code-gen vai pro **task**, mas a **criação da row fica
no signal** (opção B). Motivo: a existência do certificado é garantia síncrona do sistema (e o #79 é
literalmente "torne a criação race-safe"); jogar a criação inteira pro worker fragilizaria isso.
Custo de B: a row existe brevemente sem código até o task rodar → `certificate_code` virou
**nullable** (migração `0006`, metadata-only).

## Bugs + Fix

- **#79 (Major) — criação não race-safe.** Era `filter(...).exists()` + `create()`. O OneToOne em
  `enrollment` já impede row duplicada, mas a janela check-then-create fazia um double-save
  concorrente estourar `IntegrityError` **cru** ao caller. Fix: `Certificate.objects.get_or_create(
  enrollment=instance, defaults={snapshots})` — no-op gracioso na corrida; `.delay()` só quando
  `was_created`.
- **#80 (Major) — trabalho pesado no signal.** `generate_certificate_code()` (loop de colisão com
  query no DB) + `create()` rodavam na thread da request. Fix: o loop de geração de código mudou
  pro **task** (`if not certificate.certificate_code: ... = generate_certificate_code()`), **dentro
  do `try`** pra que falha de alocação de código siga o mesmo caminho de retry/falha-final do #78. O
  signal fica leve (só `get_or_create` + snapshot + enqueue).
- **#78 (Major) — double-retry + falha permanente silenciosa.** O `raise self.retry(exc=exc)` estava
  **fora** do `if retries >= max`: na tentativa final marcava `pdf_generation_failed_at` **e** ainda
  re-tentava (`MaxRetriesExceededError`, log enganoso); e a falha permanente não alertava nada. Fix:
  branch mutuamente exclusivo — `if retries < max: raise self.retry(...)`; senão →
  `pdf_generation_failed_at` + `sentry_sdk.capture_exception(exc)` + log ERROR + `return`. Admin:
  `pdf_generation_failed_at` em `list_display` + `list_filter` p/ triagem.

Suporte: `certificate_code` `null=True, blank=True` (mantém `unique`/`db_index`; Postgres/SQLite
permitem múltiplos NULL sob unique) — migração `0006`. `__str__` mostra `(pending)` na janela
transitória.

## Verificação

- **RED:** 5 testes novos falharam pelo motivo documentado (signal gerava código no request path;
  `create()` cru estourava `IntegrityError`; `tasks` não chamava `generate_certificate_code` nem
  tinha `sentry_sdk`/branch limpo).
- **GREEN:** `pytest apps/certificates/`: **58 passed**. flake8/black/isort limpos
  (apps/certificates). Migration drift: nenhum. Coverage: `signals.py` **100%**, `tasks.py` **91%**
  (faltante = branch `DoesNotExist`, pré-existente).
- **code-reviewer (diff final):** **APPROVE WITH NITS**, 0 Blocking / 0 Major. Minor real corrigido
  (code-gen movido pra dentro do `try` → colisão de código segue retry/falha-final); nits aplicados
  (`__str__` `(pending)`, framing honesto do teste de race, asserção extra de que o código persiste
  na falha final, log do `except` generalizado). Consumidores de `certificate_code` NULL transitório
  verificados seguros: download 404 antes do filename; `validate_by_code` não casa NULL; serializer
  renderiza `null` (JSON válido).
- **Prod (2026-06-27):** smoke rollback-safe (`transaction.atomic()` + `raise`, `.delay()`/render de
  PDF/Sentry mockados, dados via factories, `docker compose exec -T backend python manage.py shell <`):
  - #0 migração `0006` aplicada (`certificate_code` nullable) ✅
  - #80 signal cria row sem código no request path + snapshot populado + enqueue 1x ✅
  - #79 sem duplicata no 2º save; `get_or_create` no-op sem `IntegrityError` ✅
  - #80 task atribuiu código `WSS-` + gravou `pdf_file` ✅
  - #78 falha final: sem retry, alerta Sentry, marca `pdf_generation_failed_at`, mantém código,
    `is_valid` True ✅
  - #78 admin `list_filter` expõe `pdf_generation_failed_at` ✅
  - **`ALL PASS`** (14/14), `rows persisted after rollback: 0` (nada persistido).

## Testes adicionados/reescritos

- `tests/test_tasks.py` (novo): `test_task_assigns_code_when_missing`,
  `test_task_keeps_existing_code`, `test_retries_while_attempts_remain`,
  `test_final_failure_does_not_retry_and_alerts` (retries via `push_request`/`run`),
  `test_task_noops_when_pdf_present`.
- `tests/test_signals.py`: classe `TestSignalStaysLightweight` —
  `test_signal_creates_row_without_code_in_request_path`,
  `test_signal_no_ops_when_certificate_already_exists`.

## Done-criteria (`06`)
- [x] Criação idempotente sob concorrência, sem `IntegrityError` cru ao caller (#79)
- [x] Signal leve; code-gen + PDF fora do request path (#80)
- [x] Task no-op com PDF presente; retry/falha-final mutuamente exclusivos; falha permanente alertada
      (Sentry) e visível no admin (#78)
- [x] validado em prod (2026-06-27)

## Notas

- Deploy = **código + migração** → `docker compose restart backend` aplica `0006` via entrypoint.
- Concorrência REAL (threads + Postgres) p/ o `get_or_create` do #79 segue **deferida** (candidata a
  Phase 3), conforme decidido na camada payments.
- Resto da camada `06`: OAuth #43/#44/#47. Depois **Phase 3** — `07-tests` (#17 assinatura webhook,
  #82 cobertura task/utils certs, #34/#35/#50/#86) + `08-lint-style` (batch) + videos #60.
