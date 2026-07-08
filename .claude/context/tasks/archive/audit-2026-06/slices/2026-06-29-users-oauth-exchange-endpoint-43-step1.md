# Slice: OAuth token-exchange endpoint — #43 Step 1 (additive)

**Data:** 2026-06-29
**Branch:** `feat/users-oauth-exchange-endpoint-43-step1` (a partir de `main`) → **PR #154 (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · slice OAuth (parte 2 de 2) — **Passo 1 de 2** do #43
**Status:** mergeado, **deployado e validado em prod 2026-06-29**. **#43 NÃO fecha aqui** (fecha no Passo 2).

## Contexto

Terceiro e último finding OAuth da camada `06` (após #44/#47). O #43 remove os JWT da URL de
redirect do callback Google. Como tirar o token da URL **muda o contrato do frontend** (o Vue hoje
parseia o fragment `#access=&refresh=`), o fix foi dividido em **2 passos** para deploy desacoplado:

- **Passo 1 (este, aditivo):** adicionar o mecanismo de código single-use + endpoint de exchange,
  **sem tocar no callback** (que segue emitindo o fragment antigo). Nada quebra; o front passa a ter
  o endpoint real para integrar.
- **Passo 2 (futuro, após o front pronto):** virar o callback para emitir `#code=<code>` e fechar #43.

**Fork de design (aprovado): opção (a)** — o exchange devolve o par `{access, refresh}` no **corpo**
da resposta (casa com o storage atual do front; refresh em cookie httpOnly = opção (b) ficou como
evolução à parte).

## Mudanças (deploy só-código, sem migração)

- `services/google_oauth.py` — `issue_exchange_code(user)` (gera `secrets.token_urlsafe(32)`, grava
  `oauth:exchange:<code> → user.id` no cache, **TTL 60s**) + `consume_exchange_code(code)` (`get`+
  `delete` via cache API portável — LocMem no teste não tem `GETDEL`; janela get-then-delete é benigna,
  mesmo usuário, sem escalonamento; trata ausente/vazio/expirado/reusado/usuário-deletado).
- `views.py` — `GoogleTokenExchangeView` (`AllowAny`, `OAuthRateThrottle`): `POST {code}` → **200**
  `{access, refresh}` ou **400** `{detail}`.
- `urls.py` — rota `POST /api/auth/google/exchange/`.
- **Callback intocado** (ainda emite `#access=&refresh=`).

## Verificação

- **RED:** 9 testes novos falharam pelo motivo certo (métodos do serviço inexistentes; rota
  inexistente). Os testes do fragment antigo do callback **continuam verdes** (provam que nada quebrou).
- **GREEN:** `pytest apps/users/`: **117 passed** (no PR; **121** após rebase sobre o main com #152).
  flake8/black/isort limpos. Sem migration drift. Código novo 100% coberto.
- **code-reviewer (diff final):** **APPROVE WITH NITS**, 0 Blocking / 0 Major. Confirmou: single-use
  por get+delete é são (corrida benigna, mesmo usuário); body delivery (opção a) ok; entropia
  256-bit + TTL 60s + throttle adequados; 400 (não 401) correto p/ input inválido em endpoint
  `AllowAny`; fail-closed em queda de Redis. **Nits → follow-up #155** (scope dedicado `oauth-exchange`
  + distinguir queda de Redis de código inválido nos logs).
- **Conflito de merge (rebase):** o PR foi cortado de `main` antes do #152 (fix #44/#47); ambos
  editaram `google_oauth.py` (auto-merge limpo) e `test_google_oauth_service.py` (conflito **trivial**
  — duas classes de teste independentes no mesmo ponto de ancoragem). Resolvido por rebase mantendo as
  três classes (`TestHandleCallbackSessionInvalidation` + `TestAccountLinkingSecurity` do #152 +
  `TestExchangeCode` do feat); 121 passed pós-rebase; force-push-with-lease; merge squash (#154).
- **Prod (2026-06-29):** curl read-only (`POST` com código inválido → **400**) + smoke rollback-safe
  (`transaction.atomic()` + `raise`, dados via factories, chaves de exchange limpas do Redis ao fim,
  `docker compose exec -T backend python manage.py shell <`):
  - service: código emitido resgata o user; single-use (2º consume → None); desconhecido/vazio → None
  - endpoint: código válido → **200** com `access`+`refresh`; reusado → **400**; ausente → **400**
  - **`ALL PASS`** (7/7), `user rows persisted: 0`, `exchange codes lingering in Redis: 0`.

## Testes adicionados

- `tests/test_google_oauth_service.py`: `TestExchangeCode` (issue→consume, single-use, desconhecido,
  usuário-deletado, vazio/None).
- `tests/test_google_views.py`: `TestGoogleTokenExchangeView` (200, inválido 400, ausente 400,
  single-use, acesso público).

## Done-criteria
- [x] Endpoint de exchange entrega o par no corpo; código single-use, 60s, 256-bit (Passo 1)
- [ ] JWT fora da URL (flip do callback) → **Passo 2**, após o front integrar e validar

## Frontend (handoff feito 2026-06-29)

Prompt entregue ao agente de frontend. Estratégia transition-safe: o front passa a suportar **os dois
formatos** na rota `/auth/callback` — `#code=` (novo, troca via exchange) **e** `#access=&refresh=`
(legado, ainda emitido pelo backend). Assim o front vai pra produção **sozinho**, sem janela de quebra;
o branch legado só sai depois do Passo 2 estável. Front em andamento.

## Notas / próximos passos

- Deploy só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- **Passo 2 (engatilhado):** virar o callback (`GoogleCallbackView`) para gerar o código via
  `issue_exchange_code` e redirecionar com `#code=`; reescrever os testes do callback (fragment →
  code); deploy + smoke; **fecha #43**. Disparar só quando o front estiver pronto e validado em prod.
- Com isto a camada `06` (services/signals/tasks) fica **completa** após o Passo 2. Depois:
  **Phase 3** (07-tests: #17/#82/#34/#35/#50/#86 + 08-lint-style batch + videos #60).
- Follow-ups abertos: **#155** (hardening do exchange), #136, #122, #38, #151.
