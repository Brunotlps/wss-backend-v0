# Slice: deny module course reassignment to unowned courses on update (#237)

**Data:** 2026-07-08
**Branch:** `fix/courses-module-update-reassign-237` (a partir de `main`) → **PR #240 (squash →
`main`, commit `46cd88d`)**
**Layer:** nenhum específico — achado de code-reviewer, follow-up do #223, fora da auditoria
original 2026-06
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-08)**. **Último item aberto do
repositório — zero issues abertas depois deste.**

## Contexto

O #223 fechou o caminho de **create** de módulo (o `course` id de um instrutor é validado contra
ownership antes do módulo ser criado). O caminho de **update** (`PATCH`/`PUT
/api/modules/{id}/`) tinha um gap relacionado, porém distinto:

- `IsModuleCourseInstructorOrReadOnly.has_object_permission` só checava
  `obj.course.instructor == request.user` — ownership do curso **atual** do módulo. Nunca
  validava o valor **novo** de `course` sendo escrito.
- `ModuleSerializer.course` é um `PrimaryKeyRelatedField` gerado automaticamente, sem filtro
  (`queryset=Course.objects.all()`), e não está em `read_only_fields`.

Consequência (confirmada por um PoC do reviewer durante o #223): um instrutor dono de `module_a`
(vinculado ao seu próprio `course_a`) conseguia `PATCH /api/modules/{module_a.id}/` com
`{"course": <course_b.id>}` de um instrutor **diferente** (publicado ou não), e a requisição
tinha sucesso com **200 OK** — reatribuindo `module_a` (e suas lições) pra um curso que não é
dele, sem nenhuma trava.

## Fix (#237)

- `apps/courses/permissions.py` — `has_object_permission` agora, depois de confirmar que o
  requisitante é dono do curso **atual**, também valida um valor **novo** de `course` presente no
  payload: mesma regra do `has_permission` de create (#223) — nega 403 uniformemente pra "não
  existe", "existe mas invisível" e "existe mas não é meu", nunca deixa a escrita alcançar o
  serializer.

## TDD

- **RED:** `test_update_module_cannot_reassign_to_unowned_course` e
  `test_update_module_cannot_reassign_to_hidden_course` falharam com `200` (reatribuição real)
  contra o código original — reprodução exata do PoC do reviewer.
- **GREEN:** os 2 testes RED + `test_put_module_cannot_reassign_to_unowned_course` (cobertura de
  método, já que `has_object_permission` não distingue PATCH de PUT). Todos verificam status **e**
  que a reatribuição não aconteceu de fato (`module.refresh_from_db()` +
  `module.course_id == own_course.pk`).

## Verificação

- `pytest apps/courses/ apps/videos/`: **189 passed**. flake8/black/isort limpos.
  `makemigrations --check --dry-run`: sem drift.
- **code-reviewer:** **APPROVE**. Foi além da checagem de claims: **reverteu temporariamente o
  fix e confirmou que os 2 testes falham** contra o código antigo (prova de que não passam "por
  acidente"), testou bypass via coerção de tipo (`1.5`, `True`, `'01'`, `'1e1'` etc.) confirmando
  que nenhum permite smuggling de outro curso, e traçou a ordem de chamada do DRF
  (`get_object()` → `check_object_permissions()` → só então `serializer.save()`) confirmando que
  a negação bloqueia a escrita antes de qualquer persistência. 2 nits baratos aplicados: docstring
  corrigida sobre o caso `course: null` (não gera o mesmo 400 do create, já que `Module.course`
  não é nullable) + teste de `PUT` adicionado.

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-08):** health `200`; `inspect.getsource` via shell do container
  confirmou o bloco `if "course" in request.data:` com `except Course.DoesNotExist: return False`
  presente no código deployado.

## Notas

- **🎉 Fecha o backlog inteiro.** Zero issues abertas no repositório depois deste PR — a
  auditoria 2026-06 (81 findings) e os 2 follow-ups que ela gerou (#220, #223) e o follow-up do
  follow-up (#237) estão todos resolvidos, deployados e validados.
