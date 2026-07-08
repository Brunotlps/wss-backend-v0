# Slice: deny module create uniformly for nonexistent/hidden courses (#223)

**Data:** 2026-07-08
**Branch:** `fix/courses-module-create-enumeration-223` (a partir de `main`) → **PR #238 (squash →
`main`, commit `225e039`)**
**Layer:** nenhum específico — achado de code-reviewer, follow-up do #122, fora da auditoria
original 2026-06
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-08)**. **Último item da auditoria
2026-06 e seus follow-ups.**

## Contexto

`IsModuleCourseInstructorOrReadOnly.has_permission`, na criação de módulo (`POST /api/modules/`),
resolvia o curso alvo via o manager **sem filtro** (`Course.objects.get(pk=course_id)`). Isso
ignorava a regra de visibilidade que `CourseViewSet.get_queryset` já aplica em outros lugares
(`Q(instructor=user) | Q(is_published=True)` pra instrutores). Consequência: um instrutor
sondando `POST /api/modules/` com um `course` id arbitrário conseguia distinguir "curso existe
mas não é meu" (403) de "curso não existe" (400, do FK do serializer), permitindo enumerar a
**existência** de cursos não-publicados de outros instrutores — ids que não dá pra descobrir via
`GET /api/courses/` (esconde não-publicados de quem não é dono).

## ⚠️ Regressão pescada e revertida durante o desenvolvimento

A primeira tentativa filtrava o lookup da permission pela regra de visibilidade e, quando o curso
não era encontrado nesse conjunto filtrado (existe mas é invisível), retornava `True` — pra
"cair" no serializer e virar 400, igual a um curso inexistente. **Isso era uma regressão de
segurança real**: o campo `course` do `ModuleSerializer` é um `PrimaryKeyRelatedField` gerado
automaticamente com `queryset=Course.objects.all()` (sem filtro) — então `True` na permission
deixava a escrita seguir, e o módulo era **criado de verdade** contra um curso que o instrutor
não conseguia ver nem era dono. Um teste pegou isso na hora (201 em vez de 400, linha do módulo
existindo no banco). Revertido em favor do desenho final, mais simples.

## Fix (#223)

- `apps/courses/permissions.py` — `Course.DoesNotExist` agora retorna `False` (403) em vez de
  `True` (fallthrough pro 400 do serializer). ID malformado (`ValueError`/`TypeError`) continua
  `True` (deixa o serializer dar 400 de tipo inválido). Resultado: "não existe", "existe mas
  invisível (não-publicado, de outro)" e "existe, visível, mas não é meu" caem todos no mesmo 403
  — a permission nunca deixa a escrita chegar no serializer quando o curso não é do requisitante,
  então não existe um segundo caminho de escrita pra também trancar.

## TDD

- **RED:** teste novo falhou com 403 (esperando o 400 renomeado da primeira tentativa) — depois,
  mais importante, confirmou que a primeira tentativa **permitia a criação real** do módulo
  (201 + linha existindo no banco), revelando a regressão antes de qualquer merge.
- **GREEN (desenho final):** `test_create_module_nonexistent_course_returns_400` renomeado pra
  `..._returns_403` (comportamento mudou deliberadamente, documentado no docstring); novo
  `test_create_module_for_unpublished_other_instructor_course_returns_403` verifica **status E**
  que o módulo não foi criado de fato (`not Module.objects.filter(title="Ghost").exists()`).
  Testes existentes preservados: `test_create_module_as_non_owner_returns_403` (curso publicado
  de outro instrutor, continua 403) e `test_create_module_missing_course_returns_400` (campo
  ausente, continua 400).

## Verificação

- `pytest apps/courses/ apps/videos/`: **186 passed**. flake8/black/isort limpos (rodados direto,
  sem `python -m`, graças ao #183). `makemigrations --check --dry-run`: sem drift.
- **code-reviewer:** **APPROVE WITH NITS**. Traçou o fluxo do DRF de ponta a ponta
  (`has_permission` → `check_permissions` → `PermissionDenied` levantado em `initial()`, **antes**
  de `create()` rodar) confirmando que não há caminho onde um curso real-e-não-seu resulte em
  `True`. Rodou um PoC próprio e confirmou o `assert not Module.objects.filter(...).exists()` é
  uma prova sólida (sem colisão de título, sem vazamento entre testes). 1 nit de clareza na
  docstring aplicado. **Achado real fora de escopo:** o campo `course` também é gravável no
  **update** (PATCH) sem nenhuma trava de ownership — PoC confirmou reatribuição de módulo pra
  curso de outro instrutor com 200 OK. **Aberta issue de follow-up #237** (não bloqueia este PR,
  escopo do #223 era só `create`).

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-08):** health `200`; `inspect.getsource` via shell do container
  confirmou o bloco `except Course.DoesNotExist: return False` presente no código deployado.

## Notas

- **🎉 Fecha o mini-ciclo dos 2 follow-ups pós-auditoria (#220, #223).** Não resta mais nenhum
  item aberto da auditoria 2026-06 nem dos follow-ups surgidos durante ela — só o novo achado
  #237, que é trabalho futuro genuinamente novo, não uma pendência da auditoria.
