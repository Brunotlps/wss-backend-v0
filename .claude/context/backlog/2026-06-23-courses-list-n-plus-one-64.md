# Slice: N+1 em enrolled_count/lessons_count no list/detail de courses (#64)

**Data:** 2026-06-23
**Branch:** `fix/courses-n-plus-one-64` (a partir de `main`) → **PR aberto** (squash → `main`)
**Layer:** `05-views-throttling.md` · **Phase 2 (Major)** · primeira slice do bloco views/throttling
**Status:** commitado e pushado; **aguardando merge + deploy + smoke em prod**.

## Bug

`CourseListSerializer.get_enrolled_count` fazia `obj.enrollments.filter(is_active=True).count()`
**por linha** → cada curso numa página de list disparava um `COUNT` extra (N+1 clássico).
Mesmo padrão em `CourseDetailSerializer.get_enrolled_count` e `get_lessons_count`. O
`prefetch_related("lessons")` do viewset não ajudava: `.count()` ignora o prefetch e
emite SQL próprio. Contradizia a claim de otimização no docstring do viewset e
`django-patterns.md` (Query Optimization).

## Fix (annotate no get_queryset, ler no serializer)

- `apps/courses/views.py` — `CourseViewSet.get_queryset` anota no `super().get_queryset()`:
  - `annotated_enrolled_count = Count("enrollments", filter=Q(enrollments__is_active=True), distinct=True)`
  - `annotated_lessons_count = Count("lessons", distinct=True)`
  - **`distinct=True` nos dois é obrigatório**: sem ele, o JOIN combinado das duas relações
    multiplica as linhas (fanout) e cada `Count` infla. Verificado: 3 enrollments × 2 lessons
    → conta 3 e 2 (não 6).
  - Q/Count movidos para import de topo (`from django.db.models import Count, Q`); removido o
    `from ... import Q` local que existia no branch de instrutor.
- `apps/courses/serializers.py` — os três métodos de contagem leem a annotation via
  `getattr(obj, "annotated_*_count", None)` com **fallback** ao `.count()` original quando o
  serializer é usado fora do queryset anotado (ex.: testes que instanciam o serializer direto).
  Fallback é defensive code intencional (não coberto por teste; reconhecido no review).

## Verificação

- RED: `test_list_course_counts_have_no_n_plus_one` falhou como esperado (1 COUNT de
  enrollment p/ 1 curso → 5 COUNTs p/ 5 cursos, confirmado nos logs SQL).
- `pytest apps/courses/`: **68 passed**; coverage courses **97%**.
- flake8 / black / isort: limpos. Migration drift: nenhum (mudança sem migração).
- code-reviewer (diff final): **APPROVE WITH NITS**, 0 Blocking / 0 Major. Nit principal
  (faltava cobrir detail/`lessons_count`) endereçado com 2º teste antes do commit.

## Testes adicionados (`apps/courses/tests/test_views.py`)

1. `test_list_course_counts_have_no_n_plus_one` — contagem de queries do list deve ser
   **igual** com 1 e com 5 cursos (detector robusto de N+1, independe de threshold fixo).
2. `test_retrieve_counts_use_annotations_no_extra_count_queries` — detail lê os valores
   anotados (`enrolled_count==2`, `lessons_count==3`) e **não** emite `COUNT` em
   `enrollments_enrollment`/`videos_lesson`.

## Done-criteria (`05`, parte de #64)
- [x] list/detail sem `COUNT` por linha (asserção de query count em teste)
- [ ] validado em prod (após merge+deploy) — smoke: `GET /api/courses/` e `GET /api/courses/{id}/`
      retornam `enrolled_count`/`lessons_count` corretos; sem regressão de contrato

## Notas
- Deploy será só-de-código → `docker compose restart backend` (sem rebuild/nginx, sem migração).
- `prefetch_related("lessons")` no queryset de classe foi **mantido**: ainda serve à action
  `/lessons/` e aos serializers aninhados; não alimenta mais as contagens (agora via annotation).
- Próximo no Phase 2 views/throttling: **#69** (price soft-freeze + action `adjust-price`),
  depois #15 → #81 → #57 → #88. PRs/docs separados por slice (não agrupar).
