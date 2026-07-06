# Slice: Certificate.enrollment on_delete → SET_NULL (#38)

**Data:** 2026-07-06
**Branch:** `fix/certificates-on-delete-set-null-38` (a partir de `main`) → **PR #221 (squash → `main`, commit `8771bb8`)**
**Layer:** `02-models.md` (padrão canônico já documentado desde o #77)
**Status:** mergeado + **DEPLOYADO + MIGRADO + VALIDADO EM PROD (2026-07-06)**.

## Fix (#38)

`Certificate.enrollment` era `on_delete=CASCADE` — deletar um enrollment apagava silenciosamente
o certificado emitido, indesejável pra um documento que serve de prova legal de conclusão.
Trocado pra `SET_NULL` + `null=True` (**migração `0009`**, AlterField simples, metadata-only em
Postgres — `ALTER COLUMN DROP NOT NULL`, sem reescrita de tabela).

As properties do próprio model (`student_name`, `course_title`, `instructor_name`,
`completion_date`) já tratavam `enrollment` nulo com segurança (padrão snapshot-first do #77).
Corrigidos os 3 call sites que **bypassavam** essas properties e quebrariam num certificado
órfão:
- `Certificate.__str__` — agora usa `self.student_name` em vez de `self.enrollment.user.get_full_name()`
- `CertificateViewSet.validate_by_code` (endpoint público) — usa `certificate.student_name`
- `CertificateAdmin.student_name`/`.course_title` — delegam pras properties seguras do model

**Decisão de escopo deliberada:** `permissions.py::IsCertificateOwner` **não foi tocado**. O
reviewer confirmou via trace do DRF que `obj.enrollment.user == request.user` é inalcançável pra
um certificado órfão — `CertificateViewSet.get_queryset()` já filtra `enrollment__user=user` pra
**todo mundo** (staff incluso) antes de `has_object_permission` rodar, então `get_object()` 404
antes de chegar nessa linha.

## TDD

- **RED:** 3 testes falharam como esperado. O reviewer reproduziu o RED de verdade e corrigiu um
  detalhe da minha descrição original: a falha real é `Certificate.DoesNotExist` (CASCADE apaga a
  linha inteira, não um `IntegrityError`).
- **GREEN:** deletar o enrollment preserva o certificado (`enrollment_id` vira `None`); `__str__`
  não quebra, renderiza do snapshot; o endpoint público de verificação sobrevive à deleção do
  enrollment fonte.

## Verificação

- `pytest apps/certificates/ apps/enrollments/`: **157 passed**, cobertura **98%**.
- flake8/black/isort limpos. `sqlmigrate certificates 0009` confirmou: metadata-only em Postgres,
  sem perda de dados.
- **code-reviewer:** **APPROVE**, 0 findings blocking. 2 achados não-bloqueantes:
  1. Edge case pré-existente (não introduzido aqui): certificado muito antigo (pré-#77, sem
     snapshot) que fica órfão renderiza nome vazio em vez de quebrar — comportamento já existente
     na property, só parou de crashar.
  2. **Achado novo, fora de escopo:** staff não tem acesso real a certificados de outros usuários
     via essa ViewSet, apesar da docstring de `IsCertificateOwner` afirmar o contrário —
     `get_queryset()` filtra por dono pra todo mundo. **Aberta issue de follow-up: #220.**

## Deploy

- **Precisou de deploy + migração**: backup Postgres → `migrate --noinput` → `restart backend` +
  celery.
- **Validado em prod (2026-07-06):** health `200`; `showmigrations` confirma `0009` aplicada;
  shell do container confirmou `field.null == True` e `field.remote_field.on_delete.__name__ ==
  "SET_NULL"` no código deployado.

## Notas

- Minor residual baixa **7 → 6** (restam #62, #24, #122, #151, #180, #183). Novo achado #220
  (Minor) fica pra outro ciclo, não entra na contagem de residuais desta auditoria original.
