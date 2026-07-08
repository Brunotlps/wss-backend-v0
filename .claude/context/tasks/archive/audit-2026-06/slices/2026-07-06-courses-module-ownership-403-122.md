# Slice: move module create ownership check to permission layer (#122)

**Data:** 2026-07-06
**Branch:** `fix/courses-module-ownership-403-122` (a partir de `main`) → **PR #224 (squash → `main`, commit `1cb9701`)**
**Layer:** `04-permissions.md` (novo) + `03-serializers.md` (cleanup)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-06)**.

## Contexto

Mesmo anti-padrão do #66 (authz no serializer → 400 em vez de 403), mas **não era código morto**
aqui — era a única enforcement de ownership na criação de módulo, já que
`IsModuleCourseInstructorOrReadOnly.has_object_permission` só roda em ações de objeto
(retrieve/update/delete), nunca em `create` (sem objeto ainda).

## Fix (#122)

- `apps/courses/permissions.py` — `IsModuleCourseInstructorOrReadOnly.has_permission` resolve o
  `course` do body em `create` (`view.action == "create"`) e checa `course.instructor ==
  request.user`. Curso ausente/inválido (`Course.DoesNotExist`/`ValueError`/`TypeError`) passa
  adiante (`True`) deliberadamente pro 400 do serializer.
- `apps/courses/serializers.py` — removido `_validate_ownership`/`validate()` do
  `ModuleSerializer` por inteiro (nada mais vivia lá; unicidade de `(course, order)` é do
  `UniqueTogetherValidator` via Meta, intocado).

## TDD

- **RED:** `test_create_module_as_non_owner_returns_400` reescrito → `_403`, falhou como esperado
  (400 antes do fix).
- **GREEN:** 3 testes de view (403 não-dono, 400 curso ausente, 400 curso inexistente) + removido
  teste obsoleto em `test_serializers.py` que testava o comportamento retirado do serializer.

## Verificação

- `pytest apps/courses/ apps/videos/`: **181 passed**, cobertura **98%**.
- flake8/black/isort limpos. `makemigrations --check --dry-run`: sem drift (mudança de lógica pura).
- **code-reviewer:** **APPROVE WITH NITS** — 1 nit aplicado (docstring do módulo listando a
  permission). 1 achado "should fix" não-bloqueante: `Course.objects.get(pk=course_id)` usa o
  manager sem filtro de visibilidade, permitindo distinguir "curso existe mas não é seu" (403) de
  "curso não existe" (400) — deixa enumerar cursos não-publicados de outros instrutores. **Não é
  leak novo** (o `_validate_ownership` removido já vazava o mesmo fato via corpo de erro
  diferente); só ficou mais nítido com status codes distintos. **Aberta issue de follow-up #223.**

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-06):** health `200`; shell do container confirmou a checagem de
  ownership no permission e a ausência de `_validate_ownership` no serializer.

## Notas

- Minor residual da auditoria original baixa **6 → 5** (restam #62, #24, #151, #180, #183).
- Novo achado #223 (enumeração de cursos não-publicados) fica pra outro ciclo, não conta nos
  residuais desta auditoria.
