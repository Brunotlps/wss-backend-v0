# Slice: is_instructor não-atribuível via API (#39, #40)

**Data:** 2026-06-18
**Branch:** `fix/users-is-instructor-mass-assignment`
**PR:** #102 (squash merge → `2a362af` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `privilege-pii` (`.claude/context/tasks/archive/audit-2026-06/remediation/00-plan.md`)
**Playbook dono:** `03-serializers.md`
**Status:** mergeado; CI verde (lint + suíte PostgreSQL).

## Issues atacadas

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #39 | Blocking | users | `UserRegistrationSerializer` expunha `is_instructor` → qualquer visitante anônimo podia se registrar como instrutor |
| #40 | Blocking | users | `UserUpdateSerializer` expunha `is_instructor` e o `validate_is_instructor` só bloqueava **demoção** → qualquer usuário autenticado se auto-promovia via `PATCH /api/users/me/` |

Raiz comum (item #4 dos "cross-cutting fixes" do plano — *create/update serializer mass-assignment*):
`is_instructor` gateia criação/gestão de cursos (`apps/courses/permissions.py`, `views.py`), então
deixá-lo gravável pelo cliente era escalada de privilégio direta para o papel de criador de conteúdo.

## O que foi implementado

### Serializers — `backend/apps/users/serializers.py`
- `UserRegistrationSerializer.Meta.fields`: removido `is_instructor` (#39) → ignorado no input,
  cai no default do model (`False`).
- `UserUpdateSerializer.Meta.fields`: removido `is_instructor` (#40) → ignorado no PATCH (bloqueia
  promoção **e** demoção).
- Deletado o `validate_is_instructor` (guard de demoção), agora código morto.

### Views — `backend/apps/users/views.py`
- Docstring de `CurrentUserView.patch` corrigido: campos permitidos = `first_name, last_name, phone`
  (não lista mais `is_instructor`).

### Testes (TDD, RED→GREEN)
- `apps/users/tests/test_serializers.py`: + `test_is_instructor_ignored_on_registration`;
  + `test_cannot_self_promote_to_instructor`; reescrito `test_cannot_demote_instructor` →
  `test_is_instructor_ignored_on_update` (antes afirmava 400; agora afirma campo ignorado).
- `apps/users/tests/test_views.py`: reescrito `test_patch_me_invalid_data_returns_400` →
  `test_patch_me_cannot_self_promote_to_instructor` (deny-test no nível da view).

## Verificação
- `pytest apps/users/`: **100 passed** · coverage `apps.users` 96% (serializers 100%).
- `flake8 / black --check / isort --check` em `apps/users/`: limpos.
- code-reviewer: **APPROVE**, zero Blocking.
- CI (#102): lint + suíte PostgreSQL verdes.

## Mudança de comportamento (registrar)
Status de instrutor passa a ser concedido **somente via Django admin**. Staff também **não**
seta `is_instructor` via API (nem para si nem para outros) — `UserViewSet.update` também usa
`UserUpdateSerializer`. Alinhado a least-privilege e ao escopo do audit ("admin is OK"). Se o
produto algum dia precisar de uma rota staff via API, abrir slice dedicado com permissão própria.

## Done-criteria (playbook `03`) — desta fatia
- [x] POST/PATCH não conseguem setar `is_instructor` — deny-tests afirmam que é ignorado.
- [x] Nenhum serializer retorna 400 para falha de autorização (demoção deixou de ser 400).
- [~] (outros itens do `03` — #30 enrollments, #29 foreign-course, #65 price, #46/#45 email —
  pertencem a outras fatias/apps, fora deste slice.)

## Próximos passos
1. Tema `privilege-pii` agora 3/4. Resta **#42** (users, view): `POST /api/profiles/` retorna 500
   (IntegrityError) — create sem owner. Playbook `05-views-throttling.md`. Forte candidato à
   próxima fatia (fecha o tema).
2. Depois: `transactional-integrity` (#28/#12/#30/#29) e `certificate-trust` (#73/#75/#77).
