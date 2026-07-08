# Slice: download bloqueia certificado revogado com 410 Gone (#81)

**Data:** 2026-06-23
**Branch:** `fix/certificates-revoked-download-410-81` (a partir de `main`) → **PR #134** (squash → `main`)
**Layer:** `05-views-throttling.md` · **Phase 2 (Major)** · 4ª slice do bloco views/throttling
**Status:** mergeado, **deployado e validado em prod 2026-06-23**.

## Bug

A action `download` (`CertificateViewSet`) servia o PDF sempre que `pdf_file` existisse e
**nunca** checava `certificate.is_valid`. Um certificado **revogado** (`is_valid=False`)
continuava baixável pelo dono. Para a revogação ter efeito, o caminho de download precisa
respeitá-la. App `certificates` (critical-path, coverage ≥90%).

## Fix (gate de revogação na action)

- `apps/certificates/views.py` — `download`: se `not certificate.is_valid` → **410 Gone**
  (JSON `{"error": "This certificate has been revoked"}`), checado **depois** do
  `IsCertificateOwner` (ownership) e **antes** do 404 de PDF ausente. Docstring atualizada (#81).
- Ordem: ownership → revogação → presença de PDF. Um cert revogado sem PDF retorna 410 (não 404).
- Sem regressão de #74/#116: `/media/certificates/` segue `internal`; o `FileResponse` (#116)
  intacto (só foi adicionado um `return` antecipado).

## Por que 410 (e não 403)

O recurso existe e é do próprio dono (ownership já passou) — não é negação de autorização (403),
é um recurso deliberadamente aposentado. `05-views-throttling.md` sanciona "410/403";
`api-conventions.md` lista 410 como código de regra de negócio válido. 410 é o mais preciso.

## Verificação

- RED: `test_download_revoked_certificate_returns_410` (cert revogado **com PDF real** via
  `SimpleUploadedFile`) falhou como esperado (servia o PDF).
- `pytest apps/certificates/`: **51 passed** · views.py **100%** coberto. flake8/black/isort
  limpos. Migration drift: nenhum.
- code-reviewer (diff final): **APPROVE**, 0 Blocking / 0 Major. Confirmou: 410 justificado;
  ordem correta; deny-test prova bloqueio de PDF baixável (não pdf-absence); sem bypass via
  `validate_by_code`/`retrieve`; #74/#116 não regrediram.
- **Prod (2026-06-23):** smoke rollback-safe (`scripts/smoke_81_revoked_download_410.py`,
  atomic+raise, `manage.py shell`, `APIRequestFactory`+`force_authenticate`):
  - revogado (sem PDF) → **410**; válido (sem PDF) → **404** (guard específico de revogação).
  - **Sem escrita de arquivo** (de propósito: o gate roda antes da checagem de PDF, então
    `revoked → 410` em vez de `404` já prova o guard; o caso "revogado COM PDF → 410" fica
    coberto airtight pelo deny-test local). Nada persistido (rollback).

## Testes adicionados (`apps/certificates/tests/test_views.py`)

- `test_download_revoked_certificate_returns_410` — revogado + PDF real → 410.
- `test_download_valid_certificate_with_pdf_returns_200` — válido + PDF → 200 (anti over-block).
- `test_download_returns_404_when_no_pdf` (existente) — inalterado.

## Done-criteria (`05`, #81)
- [x] `download` retorna 410 quando `is_valid` é False (revogado)
- [x] caminho válido segue baixável; no-pdf → 404 intacto
- [x] sem bypass (única entrada é a action gated; `/media/` internal)
- [x] validado em prod (2026-06-23)

## Notas
- Deploy foi só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- Nit fora de escopo (reviewer): o serializer ainda expõe `download_url` para cert revogado;
  o cliente já tem `is_valid` para gate de UI; seguir a URL dá 410. Aceitável, não alterado.
- Próximo no Phase 2 views/throttling: **#57** (videos: upload throttle 10/day no create).
  Depois **#88** (core: readiness endpoint /health/ready/) — fecha o bloco views/throttling.
