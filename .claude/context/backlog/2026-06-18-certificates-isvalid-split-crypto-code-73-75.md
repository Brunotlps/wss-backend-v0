# Slice: Certificate — split is_valid/PDF + código de verificação cripto (#73, #75)

**Data:** 2026-06-18
**Branch:** `fix/certificates-isvalid-split-crypto-code`
**PR:** #107 (squash merge → `cf07603` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `certificate-trust` (Fatia 1 de 2)
**Playbook dono:** `02-models.md` (+ task guard `06`)
**Status:** mergeado; CI verde (lint + migration check + suíte PostgreSQL). **Tem migration (0003).**

## Issues atacadas

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #73 | Blocking | certificates | `is_valid` sobrecarregado: signal criava com `is_valid=False`, task virava `True` após PDF (reusado como guard). (a) janela de falso-"revogado" durante geração; (b) revogação admin podia ser desfeita silenciosamente em re-run da task |
| #75 | Blocking | certificates | `generate_certificate_code` usava `random.choices` (Mersenne Twister), só 6 chars secretos → previsível/enumerable |

## O que foi implementado

### #73 — separar revogação de estado do PDF
- `signals.py`: cria sem `is_valid=False` → default do model (`True` = não-revogado). Fecha a janela
  de falso-"revogado".
- `tasks.py`: guard de idempotência `if certificate.pdf_file:` (presença do PDF), **não** `is_valid`;
  on success salva só `update_fields=["pdf_file"]` — nunca toca `is_valid`. Revogação não pode ser
  desfeita por re-run.
- `is_valid` agora = **revogação só**, independente da prontidão do PDF. `views.validate_by_code`
  reporta revogação independente do PDF (já estava, agora coerente).

### #75 — código cripto
- `utils.py`: `secrets.choice` (CSPRNG), 12 chars secretos (`WSS-YYYY-<12>`, 36¹²≈4.7e18); loop
  limitado (`MAX_ATTEMPTS=5`) + `RuntimeError` no lugar de `while True`; `random` removido.
- `models.py`: `certificate_code` max_length **15→24** (cabe os 21 chars).
- **Migration `0003_alter_certificate_certificate_code`** (AlterField only, sem perda de dados).

### Testes (TDD, RED→GREEN)
- Reescritos os de signal que afirmavam o acoplamento antigo (`is_valid` = PDF).
- Novos: cert válido antes do PDF; falha de PDF não revoga; task pula quando `pdf_file` presente e
  nunca des-revoga; formato do código = 12 chars.

## Verificação
- `pytest apps/certificates/`: **42 passed** · coverage `apps.certificates` 81% (signals/models/views
  100%, tasks 90%; utils 24% = render PDF ReportLab pré-existente). Migration drift: limpo.
- `flake8 / black --check / isort --check`: limpos.
- code-reviewer: **APPROVE**, zero Blocking (diff final). Nit acatado: constantes nomeadas no gerador.
- CI (#107): lint + migration check + suíte PostgreSQL verdes.

## Done-criteria (02)
- [x] Janela de falso-"revogado" fechada; revogação não desfeita por re-run.
- [x] Verificação reporta revogação independente do PDF.
- [x] Código `secrets`-based, ≥12 chars secretos, collision-safe; migration revisada.

## Follow-ups (NÃO neste slice)
1. **[Produção — IMPORTANTE]** Data migration one-off: setar `is_valid=True` onde
   `is_valid=False AND pdf_generation_failed_at IS NULL` (certs legítimos com PDF pendente/falho,
   não revogados) — senão a verificação os reporta como "revogados" pós-deploy. Checar contagem em
   produção antes. Avaliar bundle com o deploy do #77.
2. **[#78]** Branch de falha final da task ainda chama `raise self.retry` após gravar
   `pdf_generation_failed_at` — limpar (retry vs final failure). Fora do escopo do #73.

## Próximos passos
- Tema `certificate-trust` 3/4. Blocking milestone: **15/16**.
- **Fatia 2 — #77** (última Blocking): snapshot denormalizado (`student_name`, `course_title`,
  `instructor_name`, `completion_date`) + imutabilidade + **backfill** dos certs existentes
  (decidido com fallback). `on_delete` é o **#38**, separado (não re-litigar). Playbook `02-models.md`.
