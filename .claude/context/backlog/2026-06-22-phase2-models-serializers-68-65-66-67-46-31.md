# Slice batch: Phase 2 — camadas models + serializers (#68, #65, #66, #67, #46, #31)

**Data:** 2026-06-22
**Fase do plano:** Phase 2 — Major (`.claude/context/audit/remediation/00-plan.md`)
**Playbooks dono:** `02-models.md` (#68) · `03-serializers.md` (#65/#66/#67/#46/#31)
**Status:** ✅ mergeado (4 PRs squash) + deployado + validado em produção (smoke 9/9).

Sessão única que fechou a **camada de serializers da Phase 2** (resta só #60 videos, Minor → Phase 3)
mais a única model-issue Major aberta (#68). 4 PRs, 6 issues, 1 decisão de produto documentada, 1
follow-up aberto.

## Issues atacadas

| Issue | Sev | App | PR | Commit na main | O quê |
|---|---|---|---|---|---|
| #68 | Major | courses | #125 | `a2419a8` | `slugify()` cru + `unique=True` → títulos que reduzem ao mesmo slug davam `IntegrityError` 500 |
| #65 | Major | courses | #126 | `793a28f` | `price` sem validação → cursos com preço negativo |
| #66 | Major | courses | #126 | `793a28f` | serializers re-checavam authz e retornavam **400** (devia ser 403, já feito pelas permissions) |
| #67 | Major | courses | #126 | `793a28f` | publicação sem content-gate → curso com 0 lições publicável |
| #46 | Major | users | #123 | `224719c` | email não normalizado → unicidade case-sensitive + conta duplicada via OAuth |
| #31 | Major | enrollments | #124 | `af5c1e3` | `LessonProgress` POST pulava timestamp/duration (completed sem `completed_at`) |

## O que foi implementado

### #68 — slug collision-safe (`02-models.md`) · branch `fix/68-course-slug-collision`
- Helper module-level `generate_unique_slug(model_cls, value, *, exclude_pk=None)` em
  `courses/models.py`: `slugify` (ASCII deliberado, `allow_unicode=False`) + loop de sufixo `-2,-3…`.
- Fonte única: `Course.save()` e `Category.save()` usam o helper; serializers delegam (removido o
  `slugify` redundante do create; update via helper com `exclude_pk`).
- Slug **fornecido** pelo cliente colidente → 400 via `UniqueValidator` automático do DRF (verificado).

### #65/#66/#67 — courses serializers (`03-serializers.md`) · branch `fix/courses-serializers-65-66-67`
- **#65:** `MinValueValidator(Decimal("0.00"))` em `Course.price` — **fonte única** que cobre admin
  (ModelForm) **e** API (DRF propaga o validador → 400). **Migration `courses/0004_alter_course_price`**
  (AlterField, no-op de schema).
- **#66:** removido `create()` redundante do `CourseCreateSerializer` (instructor → `perform_create`,
  sem mass-assignment) e o re-check de dono do `CourseUpdateSerializer.validate`; authz fica nas
  permissions (`IsInstructorOrReadOnly`/`IsCourseOwnerOrReadOnly` → 403).
- **#67:** dupla defesa — `Course.clean()` (admin, inclusive toggle inline `list_editable`) +
  `CourseUpdateSerializer.validate` (API) bloqueiam `is_published=True` sem lições. Assimetria
  deliberada: serializer gateia **o ato de publicar** (request seta is_published); model gateia o
  **estado final** no save do admin.

### #46 — normalização de email ponta-a-ponta (`03-serializers.md`) · branch `fix/users-email-normalization-46`
- `User.save()` → `email.lower()` (fonte única; cobre admin/registro/OAuth).
- `UserRegistrationSerializer.validate_email` → lowercase + unicidade `email__iexact` (400 amigável).
- OAuth `_find_or_create_user` → lookup `email__iexact` (linka conta existente em vez de duplicar).
- `CustomTokenObtainPairSerializer` → lowercase do email no login (senão storage-lower quebraria
  login de quem digita casing diferente). Ligado em `CustomTokenObtainPairView`.

### #31 — timestamps de progresso no create (`03-serializers.md`) · branch `fix/enrollments-progress-timestamps-31`
- Extraído `_apply_completion_side_effects(validated_data, *, lesson, previously_completed)`
  compartilhado por `create()` e `update()` do `LessonProgressSerializer`. Ordem dos 3 branches
  **idêntica** ao `update()` original (equivalência byte-a-byte). POST `completed=True` agora seta
  `completed_at` e `watched_duration = lesson.duration`.

## Decisão de produto registrada
- **#45 (enumeração de email no registro) — FECHADA como documentado, sem código.** Mensagem
  "email já existe" mantida; registro throttled `register: 5/day` por IP torna enumeração em massa
  inviável; não-enumeração real exige fluxo de confirmação por email (feature à parte, arriscada em
  prod-live). Doc em `03-serializers.md`.

## Verificação
- `pytest` por app (RED→GREEN em cada fatia): courses **66**, users **107**, enrollments **66**.
- flake8 / black --check / isort --check: limpos em todos.
- code-reviewer sobre o **diff final** de cada fatia: **APPROVE** (0 Blocking/Major).
- Migration drift: `No changes detected` (a 0004 é a única; AlterField no-op).
- Smoke em **produção** pós-deploy: script `manage.py shell` com `transaction.atomic()` +
  `raise` (rollback total — exercita model/serializer/permission sem persistir nem disparar
  certificado; #31 usa curso com 2 lições p/ não completar) → **9/9 PASS**.

## Deploy (2026-06-22)
- Ordem de merge: #68 (#125) antes do courses-serializers (#126, empilhado e rebaseado limpo);
  #46 (#123) e #31 (#124) independentes da main.
- VPS: `git pull` → `docker compose exec backend python manage.py migrate` (courses/0004 OK) →
  `docker compose restart backend` (só-de-código; bind mount + gunicorn sem reload). Backend
  `healthy`, health público 200. **Sem** `--build`, **sem** mexer no nginx, **sem** rebuild de celery.

## Follow-ups (NÃO resolvidos aqui)
1. **#122 (aberta, Minor):** `ModuleSerializer._validate_ownership` repete o anti-padrão do #66
   (authz no serializer → 400), mas **não** é código morto — é a única checagem de ownership no
   create de módulo (a permission só checa `is_instructor` no view). Mover p/ permission (403) e
   reescrever `test_create_module_as_non_owner_returns_400` → 403. Playbooks `04`/`03`.
2. **Legacy email duplicado por case (pré-#46):** linhas antigas com `a@x`/`A@x` podem fazer o
   lookup `email__iexact` do OAuth levantar `MultipleObjectsReturned`. Precisa detecção/merge
   one-off antes que isso aconteça (não auto-mesclado aqui).
3. **#60 (videos, Minor):** docstring do serializer vs `validators.py` (2GB/sem avi) — Phase 3.

## Próximos passos
- Camada **views/throttling** (`05-views-throttling.md`): #64 (N+1 enrolled/lessons count), #69
  (price soft-freeze + adjust-price audited), #15 (409 vs 400), #57/#58/#59 (videos throttle +
  IsEnrolled em list), #81 (negar download de cert revogado), #88 (readiness endpoint).
- Depois: camada **services/signals/tasks** (`06`) — inclui webhooks Stripe #13/#14/#16/#18
  (**produção live, atenção redobrada**) e certificates #78/#79/#80.
- Por fim Phase 3: `07-tests` + `08-lint-style` (batch).
