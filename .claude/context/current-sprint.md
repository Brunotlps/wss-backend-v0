# Current Status

**Sprint 11 concluído. Sprint 12 pausado (arquivado). Auditoria 2026-06 100% encerrada
(2026-07-08): 81/81 findings resolvidos (Blocking 18/18, Major 42/42, Minor 36/36) + 2 follow-ups
surgidos durante a remediação (#220, #223) + 1 follow-up de um deles (#237) — zero issues abertas
daquela auditoria.**

**Atualização documental 2026-07-11:** nova leitura read-only do codebase/infra local identificou
riscos operacionais e defasagens de documentação. Eles estão registrados em `README.md`,
`.claude/context/architecture.md`, `.claude/context/tech-stack.md` e
`.claude/context/tasks/backlog.md`. `INFRA-MELHORIAS.md` pode existir localmente
como contexto detalhado ignorado pelo git. Esses itens formam backlog de
hardening; não fazem parte da auditoria 2026-06 já encerrada.

> Jornada completa arquivada em `.claude/context/tasks/archive/audit-2026-06/` (resumo executivo,
> 8 playbooks de camada, logs de execução, e um doc por fatia de fix em `slices/`).

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
| Resource limits | Backend 1GB, Celery 512MB, Beat 256MB, Redis 64MB maxmemory documentado como runtime config |

## Métricas

- **Testes:** contexto pós-auditoria registra 596 passando, ~98% cobertura; CI impõe ≥80%
- **RAM:** ~914MB / 1.9GB (47%) + 1GB swap
- **Disco:** ~7.2GB / 48GB (15%)

## Backlog operacional aberto (coletado em 2026-07-11)

| Item | Prioridade sugerida | Motivo |
|------|---------------------|--------|
| Corrigir `entrypoint.sh` para `createsuperuser --noinput` | 🔴 Alta | Remove interpolação insegura de secrets em Python inline |
| Versionar scripts de backup e crontab documentado | 🔴 Alta | Backup offsite depende de automação fora do git |
| Persistir `redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru` no compose | 🟡 Média | Evita perda de limite após recreate |
| Reduzir porta 80 reconhecida para redirect HTTPS | 🟡 Média | Fecha serving/proxy em HTTP claro |
| Documentar/codificar firewall real | 🟡 Média | Estado de exposição de portas não é auditável pelo repo |
| Split requirements prod/dev + Dockerfile multi-stage/non-root | 🟡 Média | Reduz imagem e superfície de ataque |
| Decidir/remover `celery-beat` enquanto não houver schedule | 🟢 Baixa | Evita serviço ocioso |
| Alinhar staging Nginx com proteção de mídia de produção | 🟡 Média | Staging deve validar as mesmas garantias de segurança |
| Adicionar `.dockerignore` no build context `backend/` | 🟢 Baixa | Evita envio acidental de artefatos locais ao Docker build |
| Automatizar deploy ou criar `deploy.sh` | 🟢 Baixa | Reduz gotchas manuais de rebuild/recreate/reload |

## Sprint 12 — ⏸️ Pausado (arquivado 2026-07-04)

Pausado antes da Fase 1 (Stripe live) rodar — a prioridade virou a remediação da auditoria 2026-06,
feita direto em `main` (não na branch `claude-edits` referenciada no plano original).

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Stripe live — transação real | ⬜ Nunca rodou |
| 2 | Limpeza de dados de teste | ⬜ Nunca rodou |
| 3 | API production-ready (CORS, logs, staging, Sentry) | 🔄 3.2 e 3.5 concluídas, 3.4 parcial (staging: trabalho real não mergeado, branch `claude-edits` preservada) |

> Detalhes completos em `.claude/context/tasks/archive/sprint-12.md`. Retomar quando a ativação
> do Stripe live voltar a ser prioridade.

## Histórico de Sprints

| Sprint | Entrega principal | Status |
|--------|------------------|--------|
| 8 | Pagamentos Stripe, Sentry, Redis cache, 253 testes (95.86%) | ✅ |
| 9 | Validação de pagamento na matrícula, conclusão automática de curso, Celery configurado¹, rate limiting | ✅ |
| 10 | Gunicorn, Nginx, /api/health/, GitHub Actions CI | ✅ |
| 11 | Deploy VPS, SSL, go-live, backup offsite (B2 + rclone), UptimeRobot | ✅ |
| 12 | Stripe live, limpeza de dados, API production-ready | ⏸️ Pausado (arquivado) |
| — | Server optimization: bot blocking, memory limits, swap, log rotation (2026-05-26) | ✅ |
| — | Auditoria 2026-06 — remediação completa (81 achados + 3 follow-ups) | ✅ 100% fechada (0 abertas) |

> Detalhes por sprint em `.claude/context/tasks/archive/`

¹ **Correção (2026-06-19):** o Celery foi *configurado* (código/tasks/broker), mas o **worker
nunca rodou em produção** — `entrypoint.sh` ignora o `command` dos serviços `celery`/`celery-beat`,
que sobem gunicorn. Tasks (PDF de certificado etc.) ficam enfileiradas e não são consumidas.
Issue **#110** (milestone #2 "Production Stabilization"). Ver memory `infra_celery_entrypoint_bug`.
**✅ RESOLVIDO E DEPLOYADO 2026-06-20** (PR #113, `c77bd80`): `celery`/`celery-beat` recebem
`entrypoint: ["celery"]` + command próprio (Option B, compose-only). Worker `ready`; os 4 certs
presos drenaram da fila do Redis e geraram PDF. Restam #111 (duração de vídeo) e #112 (playback).
