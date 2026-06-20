# Current Status

**Sprint 11 concluído. Sprint 12 em andamento.**

---

## Produção

| Item | Valor |
|------|-------|
| API | https://api.nousflow.com.br |
| Servidor | VPS DigitalOcean, Ubuntu 24.04, NYC1 (1.9GB RAM, 48GB disk) |
| SSH | <VPS_USER>@<VPS_IP> |
| Stack | Docker Compose (backend, nginx, postgres, redis, celery, celery-beat) |
| SSL | Let's Encrypt via Certbot |
| Backup | Backblaze B2 — db 02h, media 03h, retenção 30 dias |
| Monitoramento | UptimeRobot → /api/health/ (5 min) |
| Swap | 1GB ativo (`/swapfile`) |
| Docker logs | Rotação 10MB × 3 por container |
| Nginx | Bot blocking via default_server 444 |
| Resource limits | Backend 1GB, Celery 384MB, Beat 128MB, Redis 64MB maxmemory |

## Métricas

- **Testes:** 340 passando
- **RAM:** ~914MB / 1.9GB (47%) + 1GB swap
- **Disco:** ~7.2GB / 48GB (15%)

## Sprint 12 — Em andamento (branch: `claude-edits`)

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Stripe live — transação real | 🔄 Aguardando ativação da conta Stripe |
| 2 | Limpeza de dados de teste | ⬜ Aguardando Fase 1 |
| 3 | API production-ready (CORS, logs, staging, Sentry) | 🔄 3.2 e 3.5 concluídas, 3.4 parcial |

> Detalhes completos em `.claude/context/tasks/sprint-12.md`

## Histórico de Sprints

| Sprint | Entrega principal | Status |
|--------|------------------|--------|
| 8 | Pagamentos Stripe, Sentry, Redis cache, 253 testes (95.86%) | ✅ |
| 9 | Validação de pagamento na matrícula, conclusão automática de curso, Celery configurado¹, rate limiting | ✅ |
| 10 | Gunicorn, Nginx, /api/health/, GitHub Actions CI | ✅ |
| 11 | Deploy VPS, SSL, go-live, backup offsite (B2 + rclone), UptimeRobot | ✅ |
| 12 | Stripe live, limpeza de dados, API production-ready | 🔄 |
| — | Server optimization: bot blocking, memory limits, swap, log rotation (2026-05-26) | ✅ |

> Detalhes por sprint em `.claude/context/tasks/archive/`

¹ **Correção (2026-06-19):** o Celery foi *configurado* (código/tasks/broker), mas o **worker
nunca rodou em produção** — `entrypoint.sh` ignora o `command` dos serviços `celery`/`celery-beat`,
que sobem gunicorn. Tasks (PDF de certificado etc.) ficam enfileiradas e não são consumidas.
Issue **#110** (milestone #2 "Production Stabilization"). Ver memory `infra_celery_entrypoint_bug`.
**✅ RESOLVIDO E DEPLOYADO 2026-06-20** (PR #113, `c77bd80`): `celery`/`celery-beat` recebem
`entrypoint: ["celery"]` + command próprio (Option B, compose-only). Worker `ready`; os 4 certs
presos drenaram da fila do Redis e geraram PDF. Restam #111 (duração de vídeo) e #112 (playback).
