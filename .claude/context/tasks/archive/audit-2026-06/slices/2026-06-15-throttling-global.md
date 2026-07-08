# Slice: Throttling global + por-endpoint (#76, #87, #49)

**Data:** 2026-06-15
**Branch:** `fix/41-users-pii-anonymous`
**Fase do plano:** Phase 0 — Foundations (`.claude/context/tasks/archive/audit-2026-06/remediation/00-plan.md`)
**Playbook dono:** `05-views-throttling.md`
**Status:** implementado e testado; **aguardando aprovação de commit** (não commitado, não pushado).

## Issues atacadas

| Issue | Severidade | App | O quê |
|---|---|---|---|
| #76 | Blocking | certificates | Endpoint público `validate_by_code` sem throttle → enumeração de códigos + vazamento de nome do aluno |
| #87 | Major | core | `health_check` (`AllowAny`) sem throttle → alvo de abuso/DoS |
| #49 | Major | users | Registro e OAuth Google sem throttle (só login estava protegido) |

Raiz comum (item #2 dos "cross-cutting fixes" do plano): **não existia `DEFAULT_THROTTLE_RATES`
global no `REST_FRAMEWORK`** — uma única mudança de settings habilita a base para todos.

## O que foi implementado

### Settings — `backend/config/settings/base.py`
Dentro de `REST_FRAMEWORK`:
- `DEFAULT_THROTTLE_CLASSES = (AnonRateThrottle, UserRateThrottle)`
- `DEFAULT_THROTTLE_RATES = { anon: 100/hour, user: 1000/hour, login: 5/hour,
  register: 5/day, oauth: 20/hour, verify: 20/min, health: 120/min }`
- `NUM_PROXIES = env.int("NUM_PROXIES", default=2)` — Cloudflare + Nginx; sem isso o throttle
  chavearia todos no IP do proxy. (Endereça parcialmente #48; ver follow-ups.)

> Nota de estilo: `base.py` usa aspas simples e **não** está no escopo de black/isort do projeto
> (CI roda lint só em `apps/`). Mantido o estilo do arquivo de propósito.

### Throttle classes (scope-based, buckets de cache separados)
- `apps/users/throttles.py`: `LoginRateThrottle` migrado de `rate` hardcoded para `scope="login"`;
  novos `RegistrationThrottle (scope="register")`, `OAuthRateThrottle (scope="oauth")`.
- `apps/certificates/throttles.py` (novo): `VerifyThrottle (scope="verify")`.
- `apps/core/throttles.py` (novo): `HealthCheckThrottle (scope="health")`.

### Wiring nas views
- `apps/certificates/views.py`: `throttle_classes=[VerifyThrottle]` na action `validate_by_code`.
- `apps/core/views.py`: `@throttle_classes([HealthCheckThrottle])` no `health_check`.
- `apps/users/views.py`: `RegistrationThrottle` em `UserRegistrationView` e em
  `UserViewSet.create` (via `get_throttles`); `OAuthRateThrottle` em `GoogleLoginView` e
  `GoogleCallbackView`.
- `apps/payments/views.py`: `throttle_classes = []` em `StripeWebhookView` — **isenção** (ver
  follow-up Blocking abaixo).

### Testes (TDD, RED→GREEN)
- `apps/certificates/tests/test_throttling.py` (novo): rate 20/min + 21ª req → 429.
- `apps/core/tests/test_throttling.py` (novo): rate configurado + 429 ao exceder.
- `apps/users/tests/test_throttling.py`: + classes de registro (5/day) e OAuth (20/hour).
- `apps/payments/tests/test_throttling.py`: + isenção da webhook (`get_throttles() == []`).

## Verificação
- `pytest` suíte completa: **353 passed**.
- `flake8 / black --check / isort --check` em `apps/`: limpos.
- code-reviewer: rodado; achados tratados/registrados (abaixo).

## Done-criteria (playbook `05`) — desta fatia
- [x] Throttle global ativo; verificação ≤20/min; registro e OAuth throttled; `NUM_PROXIES` setado.
- [~] (outros itens do `05` — 409 enrollment, profile 500, query opt, adjust-price, /ready/ —
  pertencem a outras fatias, fora deste slice.)

## Follow-ups gerados pelo code-reviewer (NÃO resolvidos aqui)

1. **[Blocking — RESOLVIDO neste slice] Webhook Stripe caía no throttle global.**
   O `DEFAULT_THROTTLE_CLASSES` global passaria a aplicar `AnonRateThrottle` (100/hour) à
   `StripeWebhookView`, que não tinha throttle. Stripe entrega de poucos IPs fixos → 429 →
   retries → endpoint desabilitado → confirmações de pagamento/enrollment perdidas.
   **Fix aplicado:** `throttle_classes = []` na view (assinatura HMAC já protege) + teste.

2. **[Blocking — ABERTO] `CACHES` não configurado → throttle por-worker.**
   Não há `CACHES['default']` em nenhum settings; `django.core.cache` cai no `LocMemCache`
   por-processo. Com múltiplos workers Gunicorn, os contadores **não são compartilhados**: um
   limite "5/hour" vira `5 × nº_workers` e zera a cada restart. Isso esvazia o valor de segurança
   de #49 (anti brute-force/spam) em produção. Também afeta o cache de `IsEnrolled` (CLAUDE.md).
   **Direção:** configurar Redis compartilhado como `CACHES['default']` (django-redis). O Redis já
   está provisionado (broker/cache do Celery — ver memory `infra_observability_gotchas`).
   **Issue aberta:** **#97** (severity:blocking, app:infra) — requer instalar `django-redis`
   (pedir aprovação) + config em base/production + deploy.

3. **[Major — ABERTO] `TokenRefreshView` / `TokenBlacklistView` agora sob anon 100/hour.**
   São chamadas anônimas (refresh token no corpo). Com `NUM_PROXIES` resolvendo o IP real do
   cliente, 100/hour por cliente é folgado (access token de 15min → ~4 refresh/hour), então é
   **aceitável**. Se houver NAT agressivo/cliente compartilhado, considerar scope `refresh`
   dedicado. Decisão: aceitar por ora; revisitar se surgir 429 legítimo.

4. **[Minor — ABERTO] Validar `NUM_PROXIES=2` contra o nginx.conf real.**
   Se o Nginx usa `set_real_ip_from`/`real_ip_header` (reescreve `REMOTE_ADDR` em vez de só
   anexar ao XFF), a contagem pode ficar off-by-one — bucketizar clientes juntos ou confiar em
   XFF spoofável. Verificar a config real do Nginx (ligado a #48).

5. **[Minor — ACEITO] Throttles custom herdam `AnonRateThrottle`** → só limitam anônimos
   (`get_cache_key` retorna `None` p/ autenticado). Correto para todos os endpoints aqui (todos
   `AllowAny`). Anotar em docstring se algum dia forem reusados em endpoint autenticado.

## Próximos passos (sequência sugerida)
1. **Aprovar e commitar** este slice (`fix(api): add global + endpoint throttling (closes #76, #87, #49)`).
2. Abrir issue para o **Blocking #2 (CACHES/Redis compartilhado)** — pré-requisito para os
   throttles valerem em prod multi-worker. Forte candidato à próxima fatia de Phase 0/infra.
3. Seguir Phase 0: **protected media (#54/#74)** — playbook `01-infra-storage.md` (toca nginx.conf,
   precisa `--force-recreate`).
4. Phase 1 privilege-pii: serializers #39/#40/#30 + view #42.
