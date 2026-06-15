# Slice: Shared Redis cache backend (#97)

**Data:** 2026-06-15
**Branch:** `fix/41-users-pii-anonymous`
**Fase do plano:** Phase 0 — infra (follow-up do slice de throttling)
**Status:** implementado e testado; **aguardando aprovação de commit**. Deploy **adiado** (config-only).

## Issue
[#97](https://github.com/Brunotlps/wss-backend-v0/issues/97) — `infra: no shared CACHES backend —
throttle counters are per-worker (LocMemCache)` (severity:blocking, app:infra).

## Problema
Não havia `CACHES['default']` configurado → `django.core.cache` caía no `LocMemCache`
por-processo. Com múltiplos workers Gunicorn os contadores de throttle não eram compartilhados
(um `5/hour` virava `5 × nº_workers` e zerava a cada restart), esvaziando o valor de segurança
dos throttles de #49/#76. Também afetava o cache do `IsEnrolled`.

## O que foi implementado (config-only, sem nova dependência)
`django-redis==5.4.0` e `redis==5.0.8` já estavam no `requirements.txt`.

### `backend/config/settings/base.py`
- `CACHES['default']` usando `django_redis.cache.RedisCache`.
- `LOCATION` = `REDIS_CACHE_URL` (env), default **derivado do `CELERY_BROKER_URL`** trocando o
  Redis DB para `/1` (helper `_redis_url_with_db` via `urllib.parse`, robusto a URL sem DB e com
  query string) → cache e broker no **mesmo Redis, DBs separados** (gotcha broker+cache).
- `KEY_PREFIX = 'wss'`, `OPTIONS.IGNORE_EXCEPTIONS = True` + `DJANGO_REDIS_IGNORE_EXCEPTIONS = True`
  → **fail-open**: outage do Redis não dá 500; throttles ficam best-effort durante a falha
  (disponibilidade > enforcement; documentado em comentário no settings).

### `backend/config/settings/development.py`
- Override de `CACHES` → `LocMemCache`. Dev e a **suíte de testes não precisam de Redis**;
  produção (`production.py`) herda o Redis de base sem override.

### Teste (TDD, RED→GREEN) — `backend/apps/core/tests/test_cache_config.py`
Asserta a config de `base` (independe das settings ativas, não exige Redis rodando):
- backend default = `django_redis.cache.RedisCache`;
- `IGNORE_EXCEPTIONS is True`;
- cache no DB `/1`, diferente do broker (`/0`).

## Verificação
- `pytest` suíte completa: verde (sem regressões).
- flake8/black/isort no arquivo de teste (apps/): limpos. (`config/settings/*` fora do escopo de
  lint do projeto — CI roda só `apps/`.)
- code-reviewer: **sem Blocking**. Major (derivação frágil) corrigido com `urlsplit`; teste
  fortalecido para assertar `/1`; fail-open comentado.

## ⚠️ Checklist de DEPLOY (quando for subir)
1. **`requirements.txt` já tem `django-redis`** — garantir `pip install -r requirements.txt` no
   container (venv local estava dessincronizado; prod instala do requirements).
2. **`REDIS_CACHE_URL` é opcional**: se não setado, deriva do `CELERY_BROKER_URL` (mesmo host,
   DB 1). Opcional setar explicitamente no `.env` de prod: `REDIS_CACHE_URL=redis://redis:6379/1`.
   *(Nota: o `.env.example` não foi alterado neste slice — a pedido; a derivação cobre o default.)*
3. Confirmar que o Redis tem o **DB 1** disponível (Redis padrão tem 16 DBs; ok).
4. Pós-deploy: validar que um limite de throttle **persiste entre requests/workers** e **sobrevive
   a restart** (antes não sobrevivia). Ex.: estourar `register` (5/day) e ver 429 mantido.

## Follow-ups remanescentes (de #97 e do slice de throttling)
- **[Major aberto]** `TokenRefreshView`/`TokenBlacklistView` sob anon 100/hour — aceitável com
  `NUM_PROXIES` resolvendo IP real; revisitar se surgir 429 legítimo.
- **[Minor aberto]** Validar `NUM_PROXIES=2` contra o `nginx.conf` real (ligado a #48).
- **[Minor]** Adicionar `REDIS_CACHE_URL` ao `.env.example` se quiser torná-lo explícito no deploy.

## Próximos passos
1. **Aprovar e commitar** este slice.
2. Deploy (adiado) seguindo o checklist acima — fecha #97.
3. Retomar Phase 0: **protected media #54/#74** (`01-infra-storage.md`).
