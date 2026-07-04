# Slice: IsEnrolled raises PermissionDenied instead of mutating self.message (#58)

**Data:** 2026-07-04
**Branch:** `fix/videos-is-enrolled-message-58` (a partir de `main`) → **PR #207 (squash → `main`, commit `56e96c4`)**
**Layer:** `04-permissions.md` · **Phase 3** (residual Major nunca agendado na Phase 2 original)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-04)**.

## Fix (#58)

- **permissions.py** — `IsEnrolled.has_object_permission`: caminho de negação trocou
  `self.message = f"..."; return is_enrolled` (mutação de estado da instância, thread-safety smell —
  a permission pode ser reusada entre múltiplos objetos no mesmo request lifecycle, vazando o título
  de um curso pra resposta de negação de outro) por
  `raise PermissionDenied(detail=f"Você precisa estar matriculado no curso '{course.title}'...")` +
  `return True` no sucesso. Mensagem com nome do curso preservada — só mudou o mecanismo.
  Import de `PermissionDenied` de `rest_framework.exceptions`. Docstring atualizada (`Raises:` em vez
  de `Returns: False`).

## TDD

- **RED:** `test_denial_does_not_mutate_shared_message_state` — instancia `IsEnrolled()` diretamente,
  chama `has_object_permission` com um `DummyRequest` stub (só `.method`/`.user`) contra uma lesson
  não-preview sem enrollment; falhou como esperado (`DID NOT RAISE PermissionDenied`) antes do fix.
- **GREEN:** após o fix, o teste confirma `pytest.raises(PermissionDenied)` com o detail citando o
  curso, e que `permission.message == IsEnrolled.message` (classe, não mutado).

## Verificação

- `pytest apps/videos/`: **101 passed**, cobertura app **97%**.
- flake8/black/isort limpos em `apps/videos/`.
- Grep confirmou nenhum outro caller (views.py, outros apps) depende do antigo contrato
  `return False` de `IsEnrolled.has_object_permission`.
- **code-reviewer:** **APPROVE**, 0 findings — confirmou que `raise` dentro de
  `has_object_permission` propaga corretamente via `check_object_permissions` → `dispatch()` →
  exception handler padrão do DRF (403 `{"detail": ...}`, sem try/except no meio que engula a
  exceção); double do teste (`DummyRequest`) suficiente pro que o método lê.

## Deploy

- **Código-only, sem migração** — precisa de `docker compose restart backend` pra valer em prod
  (bind mount, sem reload automático).
- **Validado em prod (2026-07-04):** health `200`; `inspect.getsource` no shell do container confirmou
  o código deployado contém `raise PermissionDenied` e não contém mais `self.message =` na negação.

## Notas

- Fechar #58 baixa o Major residual da camada `04-permissions` de 5 → 4 (restam #59, #32, #33, #136).
- Ver [[feedback_pr_deploy_flag]]: a partir desta sessão, todo slice indica explicitamente
  no-deploy vs precisa-de-deploy, e a validação em prod é confirmada antes de fechar o doc.
