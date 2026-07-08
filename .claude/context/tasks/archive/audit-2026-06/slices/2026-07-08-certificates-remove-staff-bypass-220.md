# Slice: remove dead is_staff bypass and fix docs (#220)

**Data:** 2026-07-08
**Branch:** `fix/certificates-remove-staff-bypass-220` (a partir de `main`) → **PR #235 (squash →
`main`, commit `76c544a`)**
**Layer:** nenhum específico — achado de code-reviewer, follow-up do #38, fora da auditoria
original 2026-06
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-08)**.

## Contexto

`IsCertificateOwner.has_object_permission` tinha um bypass `if request.user.is_staff: return
True` e docstrings extensas afirmando "staff pode acessar qualquer certificado (suporte/
auditoria)". Na prática isso era **código morto**: `CertificateViewSet.get_queryset()` filtra
`Certificate.objects.filter(enrollment__user=user)` incondicionalmente, staff incluído, sem
nenhum branch de `is_staff`. Como o `get_object()` do DRF roda `filter_queryset(get_queryset())`
**antes** de `check_object_permissions`, um certificado que o staff não é dono nunca alcança
`has_object_permission` — o `get_object()` já dá 404 antes.

Um teste existente (`test_staff_can_see_any_certificate`) também era enganoso: a docstring dizia
"staff pode recuperar qualquer certificado", mas o corpo do teste criava o certificado do
**próprio** staff e recuperava esse — nunca testava acesso cross-user de verdade, dando falsa
confiança de que o bypass documentado funcionava.

## Decisão de produto

Confirmada com o Bruno antes do fix: acesso de staff/suporte a certificados de outros usuários
acontece via Django admin (`CertificateAdmin`, já existe), **não** por essa API REST.

## Fix (#220)

- `apps/certificates/permissions.py` — removido o branch morto de `is_staff`; docstrings (módulo,
  classe, método, bloco de `Examples`) reescritas explicando a ausência do bypass e apontando pro
  Django admin como caminho de suporte.
- `apps/certificates/views.py` — comentário do `download` corrigido (`"owner only; #220"`).

## TDD

- **Sem RED tradicional** — os 4 testes novos/reescritos já passavam **antes** de remover o
  código morto, confirmando que o comportamento em runtime já estava correto (404 pra staff em
  certificado alheio). O defeito real era só código morto + docs/testes enganosos.
- `test_views.py` — `test_staff_can_see_any_certificate` (enganoso) substituído por
  `test_staff_cannot_access_other_users_certificate_via_api` (404 de verdade) +
  `test_staff_can_still_access_their_own_certificate` (200, caminho feliz inalterado).
- `test_permissions.py` — `test_staff_bypasses_ownership_on_validate_action` (enganoso, mesmo
  usuário) substituído por `test_staff_can_validate_their_own_certificate` (caminho feliz) +
  `test_staff_cannot_validate_other_users_certificate` (404 de verdade, cross-user).

## Verificação

- `pytest apps/certificates/`: **74 passed**. flake8/black/isort limpos (rodados direto, sem
  `python -m`, graças ao #183). `makemigrations --check --dry-run`: sem drift.
- **code-reviewer:** **APPROVE**, 0 findings bloqueantes. Verificou a ordem de chamada do DRF
  (`get_object()` filtra queryset antes da permission) pros 3 call-sites que usam essa permission
  (`retrieve`, `download`, `validate_ownership`); confirmou que `validate_by_code` (público) não é
  afetado; confirmou via grep que `IsCertificateOwner` só é usada neste viewset; confirmou que os
  factories geram usuários genuinamente distintos nos testes novos (sem repetir o erro dos testes
  antigos).

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-08):** health `200`; `inspect.getsource` via shell do container
  confirmou a última linha do método (`return obj.enrollment.user == request.user`, sem branch de
  `is_staff`). Nota: uma checagem automática ingênua (`"is_staff" not in source`) deu falso
  negativo porque a **docstring** menciona `is_staff` ao explicar por que o bypass não existe —
  não é uma inconsistência real, confirmado lendo o código de fato.

## Notas

- Fecha 1 dos 2 achados de follow-up pós-auditoria. Resta só **#223** (courses, enumeração de
  cursos não-publicados).
