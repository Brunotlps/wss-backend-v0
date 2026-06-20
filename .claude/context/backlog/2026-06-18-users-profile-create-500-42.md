# Slice: Profile create/destroy quebrados → 500 removidos (#42)

**Data:** 2026-06-18
**Branch:** `fix/users-profile-create-500`
**PR:** #103 (squash merge → `9c847ef` em `main`)
**Fase do plano:** Phase 1 — Blocking by theme · tema `privilege-pii` (`.claude/context/audit/remediation/00-plan.md`)
**Playbook dono:** `05-views-throttling.md`
**Status:** mergeado; CI verde (lint + suíte PostgreSQL). **Fecha o tema privilege-pii (4/4).**

## Issue atacada

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #42 | Blocking | users | `ProfileViewSet` era `ModelViewSet` mas `ProfileSerializer` não tem campo `user` nem `perform_create` → `POST /api/profiles/` levantava `IntegrityError` (`NOT NULL users_profile.user_id`) → **HTTP 500** |

Profiles são criados automaticamente por signal na criação do usuário e são 1:1 com o User —
create e destroy não fazem sentido.

## O que foi implementado

### Views — `backend/apps/users/views.py`
- `ProfileViewSet`: `viewsets.ModelViewSet` → composição
  `mixins.ListModelMixin + RetrieveModelMixin + UpdateModelMixin + GenericViewSet`.
  POST e DELETE deixam de existir nas rotas → **405**. O único caminho de escrita (update) opera
  sobre instância existente, já escopada ao dono via `IsOwnerOrReadOnly`.
- Import de `mixins`.

### URLs — `backend/apps/users/urls.py`
- Docstring de rotas atualizado: removidas as linhas `POST /api/profiles/` e
  `DELETE /api/profiles/{pk}/`.

### Testes (TDD, RED→GREEN) — `apps/users/tests/test_views.py`
- `test_create_profile_not_allowed`: POST → 405 (antes: 500 IntegrityError).
- `test_destroy_profile_not_allowed`: DELETE → 405 (antes: 403 staff-only).
- `test_update_own_profile_allowed`: guard de não-regressão (PATCH do próprio profile → 200).

## Verificação
- `pytest apps/users/`: **103 passed** · coverage `apps.users` 96%.
- `flake8 / black --check / isort --check` em `apps/users/`: limpos.
- code-reviewer: **APPROVE**, zero Blocking (nits Minor abaixo).
- CI (#103): lint + suíte PostgreSQL verdes.

## Mudança de comportamento (registrar)
`POST /api/profiles/` e `DELETE /api/profiles/{pk}/` não existem mais (405). Profile é 1:1 com
User (`on_delete=CASCADE`) → deleção é transitiva via deleção do usuário. Read/list (escopado ao
dono)/update do próprio profile inalterados.

## Done-criteria (playbook `05`) — desta fatia
- [x] Profile create não dá mais 500 (rota removida).
- [~] (demais itens do `05` — #28 409, #69 adjust-price, #88 /ready/ — outras fatias.)

## Follow-ups (NÃO resolvidos aqui)
1. **[Minor — DEFERIDO]** `Profile.Meta` sem `ordering` → `UnorderedObjectListWarning` no list
   (agora o principal read path). Fix toca `Meta.options` e geraria migration `AlterModelOptions`
   (dispara o check de migration-drift do CI; exige aprovação de migration). Slice separado.
2. **[Minor — ACEITO]** Branch DELETE de `IsOwnerOrReadOnly.has_object_permission` deixa de
   participar do fluxo de Profile, mas segue viva para `UserViewSet` (ModelViewSet com destroy).
   Sem ação.

## Próximos passos
- Tema `privilege-pii` **fechado (4/4)**. Blocking milestone: 9/16.
- Próximo tema: `transactional-integrity` (#12/#28/#29/#30). Candidata: #28 (dup enrollment → 409)
  + #30 (mass-assignment em enrollment create) — mesma app/camada, pareáveis com `06` (`get_or_create`).
