# Slice: OAuth callback cut-over — #43 Step 2 (FECHA #43)

**Data:** 2026-06-29
**Branch:** `fix/users-oauth-callback-code-cutover-43` (a partir de `main`) → **PR #157 (squash → `main`)**
**Layer:** `06-services-signals-tasks.md` · **Phase 2 (Major)** · **Passo 2 de 2** do #43 — **fecha #43 e a camada 06**
**Status:** mergeado, **deployado e validado em prod 2026-06-29**. **#43 CLOSED.**

## Contexto

Segundo e último passo do #43 (tirar o JWT da URL do callback Google). O Passo 1 (PR #154) já tinha
entregue o endpoint de exchange (aditivo); o front (PR #7, dual-format) já estava mergeado. Este passo
faz o **cut-over**: o callback passa a emitir o código single-use em vez dos tokens.

## Bug + Fix

- **#43 (Major, security) — JWT na URL.** O callback cunhava `RefreshToken.for_user(user)` e
  redirecionava com `#access=<jwt>&refresh=<jwt>`. Mesmo no fragment, o refresh de 7 dias ficava no
  histórico do browser / `window.location`. Fix: `GoogleCallbackView.get` agora faz
  `code = service.issue_exchange_code(user)` e `redirect(".../auth/callback#code={code}")` —
  **nenhum JWT na URL**. Caminhos de erro (missing params / oauth_failed) intocados.
- **Bug do token obsoleto (achado na validação conjunta front+back):** o `DEFAULT_AUTHENTICATION_CLASSES
  = (JWTAuthentication,)` é global e roda **antes** da permission. O axios do front anexa
  `Authorization: Bearer <token>` em toda requisição; no callback, o `googleExchange` é chamado
  **antes** de salvar os tokens novos → um token **expirado** da sessão anterior seria anexado →
  `JWTAuthentication` levanta `InvalidToken` → **401** no exchange (que é `AllowAny`), quebrando um
  login válido. Fix: `GoogleTokenExchangeView` ganha `authentication_classes = []` — não roda auth
  JWT; é autenticado pelo **código single-use**. Sem `SessionAuthentication` no projeto → sem
  exposição CSRF (confirmado no review). Throttle `OAuthRateThrottle` mantido.

## Verificação

- **RED:** 3 testes falharam pelo motivo certo — 2 do callback (ainda emitia `#access=&refresh=`) e
  `test_exchange_ignores_stale_bearer_header` falhou com **401** (`Unauthorized: /api/auth/google/
  exchange/`), provando o bug do token obsoleto.
- **GREEN:** `pytest apps/users/`: **122 passed**. flake8/black/isort limpos. Sem migration drift.
- **code-reviewer (diff final):** **APPROVE**, 0 Blocking / 0 Major. Confirmou: nenhum caminho vaza
  token na URL; instância única de `GoogleOAuthService` reusada corretamente; `authentication_classes
  = []` não enfraquece nada (já era `AllowAny`, throttle mantido, código single-use+TTL 60s, sem CSRF
  pois não há `SessionAuthentication`); `RefreshToken` ainda usado no exchange (import vivo); testes
  fiéis (asserções de ausência de token + regressão real do 401). 2 nits opcionais fora de escopo
  (`index("#")` defensivo; get-then-delete já documentado).
- **Prod (2026-06-29):** smoke rollback-safe (`transaction.atomic()` + `raise`, handshake do Google
  mockado, código real emitido pelo callback resgatado, chaves de exchange limpas do Redis):
  - callback → **302** com `#code=` e **sem** `access=`/`refresh=` na URL
  - código emitido pelo callback resgata o user via `consume_exchange_code`
  - exchange com `Authorization: Bearer invalid.stale.token` → **200** com `access`+`refresh`
  - **`ALL PASS`** (5/5), `user rows persisted: 0`, `exchange codes lingering in Redis: 0`.

## Testes (reescritos/adicionados)

- `tests/test_google_views.py`: 3 testes do callback reescritos (fragment-com-tokens →
  fragment-com-code; afirmam ausência de `access=`/`refresh=` em qualquer parte da URL) +
  `test_exchange_ignores_stale_bearer_header` (código real + Bearer inválido → 200).

## Done-criteria (#43)
- [x] JWT fora da URL (fragment só com código opaco; tokens no corpo do exchange)
- [x] Fix do 401 por token obsoleto (`authentication_classes = []`)
- [x] validado em prod (2026-06-29) → **#43 CLOSED**

## Cut-over com o frontend (em andamento)

- O front (PR #7, já em prod) suporta **os dois formatos**, então no instante do deploy deste passo
  ele passou a receber `#code=` e a chamar o exchange; o fix do `authentication_classes` garante que
  um token obsoleto não dá 401. **Login Google segue funcionando sem janela de quebra.**
- **Prompt 2 entregue ao agente de front** (a ser executado agora que o backend Passo 2 está em prod):
  (1) defesa em profundidade — `googleExchange` via axios cru (sem Bearer); (2) **remover o fallback
  legado** `#access=&refresh=` (agora código morto); (3) validação ao vivo no browser (click-through,
  refresh, token-obsoleto, hash limpo); (4) alinhar a URL hardcoded do `LoginView`.

## Estado da camada / próximos passos

- **Camada `06` (services/signals/tasks) COMPLETA:** payments/settings + certificates #79/#80/#78 +
  OAuth #44/#47 + #43 (passos 1+2), todos validados em prod.
- **Próximo: Phase 3** — `07-tests` (#17 assinatura webhook, #82 task/utils certs, #34/#35/#50/#86) +
  `08-lint-style` (batch, inclui dirt pré-existente de `config/`) + videos #60.
- Follow-ups abertos: #155 (hardening do exchange: scope `oauth-exchange` + observabilidade Redis),
  #136, #122, #38, #151.
