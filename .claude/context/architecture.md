# Architecture & Design Decisions

**Projeto:** WSS Backend — LMS API (NousFlow)
**Última atualização:** 2026-05-26

---

## Padrões Arquiteturais

### Arquitetura em Camadas

```
Presentation  → DRF Views + Serializers
Business      → Services + Signals + Permissions
Data Access   → Django ORM Models
Infrastructure → PostgreSQL, Redis, Celery, Storage local
```

### Service Layer
Lógica de negócio complexa fica em `services.py`, fora das views. Exemplo: `apps/payments/services.py` (StripeService). Views apenas orquestram.

### ViewSet Pattern
- **CRUD padrão:** `ModelViewSet`
- **Ações customizadas:** `@action` decorator
- **Lógica não-CRUD:** `GenericViewSet` ou `APIView`

---

## Decisões Técnicas

| # | Decisão | Escolha | Motivo |
|---|---------|---------|--------|
| 1 | Framework | Django + DRF | Admin, ORM, ecosystem |
| 2 | Banco | PostgreSQL | ACID, JSON support, queries complexas |
| 3 | Cache/Broker | Redis (único serviço) | Cache de permissões + broker Celery |
| 4 | Pagamentos | Stripe Payment Intent API | 3D Secure, webhooks, moderno |
| 5 | Tarefas async | Celery + Redis | PDF assíncrono, email futuro |
| 6 | Fixtures de teste | Factory Boy + pytest | Dados programáticos, sem JSON frágil |
| 7 | Auth | JWT (simplejwt) | Stateless, CORS, mobile-ready |
| 8 | Side effects | Django Signals (leves) | Certificados, cache invalidation |

**Regra dos signals:** manter leves — tarefas pesadas vão para Celery.

---

## Data Model

### TimeStampedModel (base de todos os models)
```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
```

### Relacionamentos-chave
- `User ↔ Course` via `Enrollment` (M2M explícito com campos extras: `completed`, `payment`)
- `Enrollment → Certificate` (1:1, criado via signal ao completar)
- `Payment → Enrollment` (1:1, obrigatório para cursos pagos)

---

## Segurança

### Fluxo de autenticação
```
POST /api/auth/login/ → access_token (60min) + refresh_token (7d)
POST /api/auth/refresh/ → novo par de tokens (rotação)
Logout → blacklist do refresh_token
```

### Camadas de permissão
1. `IsAuthenticated` — autenticação
2. `IsCourseInstructor` / `IsCourseOwner` — ownership
3. `IsEnrolled` — regra de negócio (Redis cache 15min)

---

## Performance

- **N+1:** sempre usar `select_related` (FK) e `prefetch_related` (reverse FK, M2M)
- **IsEnrolled:** cacheado no Redis com key `enrollment:{user_id}:{course_id}`, TTL 15min, invalidado via signal
- **Paginação:** 20 itens/página (padrão DRF)

---

## Deployment (Produção)

- **Servidor:** VPS DigitalOcean (NYC1), Docker Compose, Ubuntu 24.04
- **Web:** Gunicorn + Nginx (reverse proxy + SSL via Let's Encrypt)
- **Banco:** PostgreSQL 15 container (volume `postgres_data`)
- **Mídia:** Volume Docker local `wss-backend-v0_media_volume` (migrar para S3/R2 quando disco ~70%)
- **Celery:** worker (384MB limit) + beat (128MB limit) em containers separados
- **Backup:** pg_dump + tar do volume → Backblaze B2 via rclone (db 02h, media 03h, retenção 30 dias)
- **Swap:** 1GB (`/swapfile`) como rede de segurança para RAM
- **Nginx:** default server retorna 444 para requests com Host inválido (anti-bot)
- **Docker logs:** rotação configurada (10MB × 3 por container)
- **Redis:** maxmemory 64MB com política allkeys-lru

---

## Monitoramento

- **Erros:** Sentry (PII filtering ativo, LGPD-compliant, traces_sample_rate=0.1)
- **Uptime:** UptimeRobot → `/api/health/` a cada 5min
- **Logs:** containers Docker (`docker compose logs -f`), rotação 10MB × 3
- **Django logs:** `/app/logs/django.log` (RotatingFileHandler, 15MB × 10)
- **DisallowedHost:** logado como WARNING (não ERROR) — bots bloqueados no Nginx

---

## Estimativas de Capacidade (baseline 2026-05-26)

### Tráfego

| Métrica | Estimativa | Fator limitante |
|---------|-----------|-----------------|
| Requests/segundo (API) | ~15-30 req/s | Gunicorn 3 workers síncronos, 1 vCPU |
| Usuários simultâneos | ~50-150 | 3 workers = 3 requests concorrentes |
| Usuários ativos/dia | ~500-2.000 | Depende do padrão de uso |
| Transfer DigitalOcean | 2TB/mês | ~20.000 visualizações completas de vídeo (100MB avg) |

**Premissas:** tempo médio de resposta 50-200ms por request. Vídeos e estáticos servidos pelo Nginx (não passam pelo Gunicorn). Ratio pico/média de 3-5x.

### Armazenamento de Vídeos

| Dado | Valor |
|------|-------|
| Disco total | 48GB |
| Usado (sistema + app) | ~7.2GB |
| Threshold para migrar (70%) | 33.6GB |
| Headroom disponível | ~26GB |

| Qualidade | Tamanho médio (10-20 min) | Vídeos que cabem | Cursos (20 aulas) |
|-----------|--------------------------|------------------|--------------------|
| 480p | ~50MB | ~520 | ~26 |
| 720p | ~100-150MB | ~170-260 | ~8-13 |
| 1080p | ~300MB | ~85 | ~4 |

**Trigger para migração de storage:** disco > 30GB usados (~63%) ou > 8-10 cursos com vídeo.

### Sinais de que precisa escalar

- Response time médio > 500ms consistentemente
- RAM "available" < 200MB de forma constante
- Swap sendo usado continuamente (verificar `free -h`)
- Load average > 2.0
- Disco > 70% ocupado

---

## Estratégias de Escala Futura

### Fase 1 — Otimização sem custo (atual → ~3x tráfego)
- Aumentar Gunicorn workers para 5 (requer ~+300MB RAM, pode precisar upgrade)
- Separar Redis DB: broker em DB 0, cache em DB 1 (métricas independentes)
- Separar `requirements.txt` prod/dev (reduz imagem Docker ~100-150MB)
- Ativar cache de querysets frequentes (cursos públicos, listagens)

### Fase 2 — Upgrade de droplet (~5-10x tráfego)
- Upgrade VPS: 4GB RAM, 2 vCPUs (~$24/mês)
- Gunicorn com 5-9 workers → ~100-300 req/s
- Suporta ~5.000-10.000 usuários ativos/dia
- PostgreSQL connection pooling (pgbouncer) se necessário

### Fase 3 — Migração de storage (quando disco > 70%)
- **Opção A — Cloudflare R2:** sem egress fees, S3-compatible, ~$0.015/GB/mês
- **Opção B — AWS S3:** ecosystem amplo, ~$0.023/GB + egress, CDN via CloudFront
- **Opção C — DigitalOcean Spaces:** integração nativa, $5/mês por 250GB + CDN incluso
- Implementação: `django-storages` com `S3Boto3Storage`, variáveis de ambiente, migration script para mover arquivos existentes

### Fase 4 — Arquitetura distribuída (se necessário, pós-10k DAU)
- CDN para vídeos (CloudFront ou Cloudflare)
- Managed database (DigitalOcean Managed PostgreSQL)
- Horizontal scaling: múltiplos backend containers atrás de load balancer
- WebSockets via Django Channels para features ao vivo
- **Nota:** microserviços são prematuros — monolito suficiente até ~50k DAU com otimizações
