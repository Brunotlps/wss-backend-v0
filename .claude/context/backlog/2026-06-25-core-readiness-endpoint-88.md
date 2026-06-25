# Slice: readiness endpoint /api/health/ready/ (#88)

**Data:** 2026-06-25
**Branch:** `feat/core-readiness-endpoint-88` (a partir de `main`) → **PR #139** (squash → `main`)
**Layer:** `05-views-throttling.md` · **Phase 2 (Major)** · 6ª e **última** slice do bloco views/throttling
**Status:** mergeado, **deployado e validado em prod 2026-06-25**.

## Bug

`/api/health/` é só liveness (200 estático, não checa DB/Redis). Não havia readiness em lugar
nenhum → o LB/monitoramento não detecta queda de DB, Redis cheio ou worker morto: a API reporta
"ok" enquanto serve 500s.

## Fix (endpoint de readiness separado, liveness intocado)

- `apps/core/views.py` — nova `readiness_check`:
  - `_check_database()` — `SELECT 1` via `connection.cursor` + `fetchone`.
  - `_check_cache()` — round-trip `cache.set`/`cache.get` (pega split-brain write-ok/read-fail).
  - cada check em try/except: loga server-side (`exc_info=True`), retorna bool; **nada** do
    exception vaza no body.
  - 200 `{"status":"ready","checks":{"database":"ok","cache":"ok"}}` se ambos ok; senão **503**
    `{"status":"not ready","checks":{...}}`.
  - `AllowAny` + reusa `HealthCheckThrottle` (scope `health`, #87). Liveness `health_check`
    **byte-for-byte intocado**.
  - Celery worker ping **deferido** (documentado no docstring): adicionaria broadcast/latência;
    fora do done-criteria do playbook; coberto por monitoramento separado.
- `config/urls.py` — wire `path('api/health/ready/', readiness_check, name='health-ready')`.

## Verificação

- RED: `TestReadinessCheck` — 4 falharam como esperado (endpoint 404).
- `pytest apps/core/`: **13 passed**. **Suíte completa: 456 passed.** flake8/black/isort limpos
  (apps/core). Migration drift: nenhum.
- code-reviewer (diff final): **APPROVE WITH NITS**, 0 Blocking / 0 Major. Confirmou: 503 sem leak
  de stack trace; liveness intocado; checks corretos (SELECT 1 sem injeção, round-trip de cache).
  **Insight do throttle×cache:** o `HealthCheckThrottle` usa o mesmo cache default no `initial()`
  (antes da view); em prod `CACHES['default'].OPTIONS.IGNORE_EXCEPTIONS=True` + django-redis fail
  open → numa queda de Redis o throttle não levanta, a view roda e devolve **503 limpo** com
  `cache:"error"`. Acoplamento registrado: a garantia de 503-limpo depende desse fail-open.
- **Prod (2026-06-25):** smoke read-only via curl:
  - `GET /api/health/ready/` → **200** `{"status":"ready","checks":{"database":"ok","cache":"ok"}}`
    (DB+cache reais checados).
  - `GET /api/health/` → **200** (liveness intacto).
  - Caminho 503 não exercitado em prod (simular outage de DB/Redis seria destrutivo); coberto
    airtight pelos testes.

## Testes adicionados (`apps/core/tests/test_views.py::TestReadinessCheck`)

- ready 200 (sem auth) quando DB+cache ok;
- 503 quando DB cai (`patch connection.cursor` → raise);
- 503 quando cache cai (`patch _check_cache` — não o cache compartilhado, p/ não quebrar o
  throttle do próprio endpoint);
- unit tests: `_check_database`/`_check_cache` retornam False em erro de backend;
- body do 503 sem traceback/detalhe de exceção.

## Done-criteria (`05`, #88)
- [x] `/api/health/ready/` checa DB (SELECT 1) + cache (round-trip)
- [x] 503 gracioso em outage (sem stack trace, log server-side)
- [x] liveness probe preservado + throttle (#87)
- [x] validado em prod (2026-06-25)

## Notas
- Deploy foi só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- `config/urls.py` tem lint dirt **pré-existente** (W291/W293/E111/E114 + black/isort) fora das
  linhas tocadas; CI lint é em `apps/`, então não quebra. Cleanup avulso recomendado (não misturado
  aqui).
- **Bloco views/throttling do Phase 2 COMPLETO:** #64 · #69 · #15 · #81 · #57 · #88 ✅.
  Próximo: layer `06` (services/signals/tasks — inclui webhooks Stripe #13/#14/#16/#18, prod-live,
  cuidado redobrado) e depois Phase 3 (07-tests + 08-lint-style; #08 inclui o cleanup do urls.py).
  Follow-up aberto: **#136** (PaymentIntentRateThrottle mesmo defeito de scope do #57).
