# Slice: harden OAuth exchange endpoint (#155)

**Data:** 2026-07-06
**Branch:** `fix/users-oauth-exchange-hardening-155` (a partir de `main`) → **PR #216 (squash → `main`, commit `6439ed6`)**
**Layer:** `05-views-throttling.md` (throttle scope) + padrão de observabilidade (cache round-trip, já usado no `/api/health/ready/` #88)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-06)**.

## Contexto

Follow-up de hardening não-bloqueante levantado na review do PR #154 (#43 passo 1). Duas partes,
nenhuma delas um buraco de segurança por si só (o código single-use de 256 bits já é suficiente).

## Fix (#155)

1. **Scope de throttle dedicado** — `GoogleTokenExchangeView` compartilhava o scope `oauth` com
   `/auth/google/` (login init) e `/auth/google/callback/`; um login completo já gastava ~3 das
   20/hora em vez de 2, e o endpoint de exchange é o alvo natural de brute-force do código
   single-use. Nova `OAuthExchangeRateThrottle` (`apps/users/throttles.py`, `scope =
   "oauth-exchange"`) + entrada `DEFAULT_THROTTLE_RATES["oauth-exchange"] = "20/hour"` — seguindo
   o precedente do irmão `OAuthRateThrottle` no mesmo arquivo (rate via settings, não classe, ao
   contrário de `UploadRateThrottle`/`PaymentIntentRateThrottle` que resolvem uma colisão de scope
   diferente). Mesma classe de fix que #57 e #136.
2. **Observabilidade de outage do Redis** — `GoogleOAuthService.issue_exchange_code` ganhou check
   de leitura-após-escrita (`cache.get(key) != user.id` logo após `cache.set(...)`). Com
   `DJANGO_REDIS_IGNORE_EXCEPTIONS=True` (prod), uma queda de Redis faz `cache.set` virar no-op
   silencioso — sem o check, isso só apareceria depois como "invalid or expired code" no exchange,
   indistinguível de um código realmente inválido. Agora loga `ERROR` distinto ("suspected
   cache/Redis outage, not a bad code"), espelhando o idioma de round-trip de cache já usado no
   `/api/health/ready/` (#88).

## TDD

- **RED:** `ImportError` (throttle não existia) + `test_logs_distinct_error_when_cache_write_does_not_persist`
  falhou (nenhum log de outage) — ambos confirmados antes do fix.
- **GREEN:** 5 testes novos — rate/scope do throttle, isolamento do bucket (429 no 21º código
  ruim), tráfego de exchange não corrói o budget do login init, log de outage distinto sob falha
  simulada, e ausência do log no caminho feliz.

## Verificação

- `pytest apps/users/`: **151 passed**, cobertura **99%** (`throttles.py`/`google_oauth.py` 100%).
- flake8/black/isort limpos. `makemigrations --check --dry-run`: sem drift.
- **code-reviewer:** **APPROVE**, 0 findings blocking/should-fix. 2 nits informativos: possível
  falso-positivo raro do log de outage sob blip transitório de conexão (tradeoff aceito, mesmo do
  `/ready/`); +1 round-trip de Redis por login (negligível, OAuth não é hot path).
- Confirmado: `cache.get(key) != user.id` é seguro e backend-agnóstico — `LocMemCache` (dev/test)
  é síncrono, sem janela de inconsistência eventual; chave é `secrets.token_urlsafe(32)` fresca,
  sem risco realista de colisão coincidente.

## Deploy

- **Código-only, sem migração** — precisou de `docker compose restart backend`.
- **Validado em prod (2026-07-06):** health `200`; shell do container confirmou
  `OAuthExchangeRateThrottle.scope == "oauth-exchange"`, `.rate == "20/hour"`, entrada em
  `DEFAULT_THROTTLE_RATES`, e o check de outage presente no código deployado (validação inicial
  com `inspect.getsource` deu falso-negativo por causa da string quebrada em duas linhas pelo
  black — corrigido checando os fragmentos separadamente).

## Notas

- Minor residual baixa **9 → 8** (restam #183, #180, #151, #122, #85, #62, #38, #24).
