# Slice: Certificates utils/task test coverage (#82)

**Data:** 2026-06-30
**Branch:** `test/certificates-utils-task-coverage-82` (a partir de `main`) → **PR #161 (squash → `main`)**
**Layer:** `07-tests.md` · **Phase 3 (hardening & hygiene)** · primeiro slice da camada de testes
**Status:** mergeado em `main` (commit `d0bbdd0`), **validado por CI**. Sem deploy (test-only).

## Contexto

Primeiro slice da Phase 3. O #82 é puramente de cobertura: os dois módulos de maior risco do app
certificates estavam praticamente sem testes — `utils.py` em **25%** (todo o render ReportLab + a
geração de código) e `tasks.py` com o branch `Certificate.DoesNotExist` descoberto. A camada `06`
(PR #149) já havia adicionado `test_tasks.py` cobrindo retry/falha-final/idempotência (#78/#79/#80),
então o que faltava era cercar code-gen, render de PDF, o caso de cert deletado, e os contratos da
verificação pública.

Mudança **test-only** — nenhum arquivo de runtime alterado, logo **sem deploy e sem smoke de prod**
(não há comportamento novo em runtime; o CI no PR é a validação).

## Lacunas cobertas

- **`utils.generate_certificate_code`** — formato `WSS-<ano>-<12 [A-Z0-9]>`/comprimento; unicidade
  entre chamadas (entropia CSPRNG); collision-retry (mock de `Certificate.objects`, `exists` →
  `[True, False]`, assert 2 tentativas); `RuntimeError` após `MAX_ATTEMPTS=5` (mock sempre colidindo).
- **`utils.generate_certificate_pdf`** — smoke gravando PDF real em `MEDIA_ROOT` apontado p/ `tmp_path`
  (assert magic bytes `%PDF` + path relativo), exercitando todos os `_draw_*` helpers transitivamente;
  branch de fallback `completion_date is None` → `datetime.today()`.
- **`tasks.generate_certificate_pdf_async`** — `Certificate.DoesNotExist` (row deletada entre enqueue
  e execução): retorna `None`, não renderiza, e loga o id (asserção via `caplog`).
- **`views.validate_by_code` (verificação pública)** — não vaza email/id: contrato de chaves exato
  (`{valid, message, certificate_code, student_name}`) + `isdisjoint` de campos sensíveis + email
  ausente do corpo, **parametrizado** nos caminhos válido **e** revogado; cert PDF-pendente
  (`pdf_file=None`, `is_valid=True`) ainda verifica como válido (#73 — `is_valid` é só revogação).

## Verificação

- **RED (baseline):** `utils.py` **25%** (linhas 74–366 render+helpers, 407 RuntimeError);
  `tasks.py` **91%** (faltante = branch `DoesNotExist`, 37–41); `test_utils.py` inexistente.
  App total **84%**.
- **GREEN:** `pytest apps/certificates/`: **68 passed**. `utils.py` **100%**, `tasks.py` **100%**;
  app certificates **84% → 98%**. flake8/black/isort limpos (apps/certificates). Migration drift:
  nenhum.
- **code-reviewer (diff final):** **APPROVE WITH NITS**, 0 Blocking / 0 Major. 3 nits de maior valor
  aplicados antes do commit: variante de cert revogado no teste de PII (parametrize), asserção de log
  no teste de `DoesNotExist` (caplog), e captura única de `year` no teste de formato (remove a corrida
  teórica de virada de ano).
- **CI (PR #161):** verde (lint + migration-drift + suíte PostgreSQL/Redis, coverage ≥80%).

## Testes adicionados

- `tests/test_utils.py` (novo): `TestGenerateCertificateCode`
  (`test_code_matches_expected_format`, `test_consecutive_codes_differ`,
  `test_collision_retries_then_returns_unique`, `test_exhausting_attempts_raises_runtimeerror`) +
  `TestGenerateCertificatePDF` (`test_writes_pdf_file_and_returns_relative_path`,
  `test_falls_back_to_today_when_completion_date_missing`).
- `tests/test_tasks.py`: `TestTaskMissingCertificate.test_missing_certificate_is_swallowed`.
- `tests/test_views.py`: `test_validate_by_code_does_not_leak_pii` (parametrizado valid/revoked),
  `test_validate_by_code_pending_pdf_is_still_valid`.

## Done-criteria (`07-tests`)
- [x] `apps.certificates` task/utils ≥90% (ambos 100%)
- [x] `DoesNotExist`, code entropy/colisão/exaustão, render de PDF cobertos
- [x] Verificação pública não vaza PII (valid + revoked); cert PDF-pendente válido (#73)
- [x] Nenhum teste afirma comportamento inseguro como esperado
- [x] `pytest` verde sem depender de linhas só-de-import

## Notas

- Sem deploy: test-only, não há runtime alterado para o servidor servir.
- Próximo da Phase 3 / `07-tests` (ordem por risco): **#50** (users deny-tests: `is_instructor`
  rejeitado no register/PATCH, PII anônima negada, `_exchange_code` mockado, `audience` errado),
  depois **#17** (assinatura de webhook Stripe), **#34/#35** (enrollments), **#86** (core),
  **#26/#72** (menores). Depois `08-lint-style` (batch) + videos #60.
