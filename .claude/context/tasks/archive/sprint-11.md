# Sprint 11 — Deploy em VPS

**Sprint:** 11
**Start Date:** 2026-04-17
**Branch:** main (infraestrutura — sem alterações de código de negócio)
**Status:** ✅ Fases 1-7 completas — Fase 8 (operações) pendente

## Dados do servidor (production_test)

| Item | Valor |
|------|-------|
| IP do Droplet | `<VPS_IP>` |
| Região | NYC1 (New York) |
| OS | Ubuntu 24.04.4 LTS |
| Usuário SSH | `<VPS_USER>` |
| Domínio | `nousflow.com.br` |
| API | `api.nousflow.com.br` |
| Frontend (Vercel) | `https://wss-frontend-seven.vercel.app` |

---

## Objetivo

Colocar o backend em produção em um VPS, acessível via HTTPS com domínio próprio.
Toda a lógica de negócio e infraestrutura de container estão prontas (Sprints 8-10).
O foco é exclusivamente na operação do servidor e no processo de deploy.

---

## Decisões Técnicas Fechadas

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Provedor VPS | DigitalOcean São Paulo | Baixa latência para público BR |
| Droplet | Basic 2GB RAM / 1 vCPU / 50GB SSD (~$12/mês) | Suficiente para fase inicial |
| Storage de mídia | Local (disco do VPS) por agora | Simples; migrar para Volume/R2 quando disco ~70% |
| Reverse proxy | Nginx (já configurado) | nginx/nginx.conf pronto no Sprint 10 |
| Servidor WSGI | Gunicorn (já configurado) | entrypoint.sh pronto no Sprint 10 |
| SSL | Let's Encrypt via Certbot | Gratuito, renovação automática |
| DNS/CDN | Cloudflare (recomendado) | DDoS protection, cache, IP do VPS oculto |

## Decisões Pendentes (resolver antes de iniciar)

| Decisão | Status | Observação |
|---------|--------|------------|
| Nome do domínio | ✅ Resolvido | `nousflow.com.br` — Registro.br |
| Chaves Stripe live vs test | ✅ Resolvido | `sk_test_` — fase production_test |
| Sentry DSN | ✅ Resolvido | Conta existente, pegar DSN na hora do .env |

---

## Fases de Deploy

### Fase 1 — Contas e serviços externos ✅
Pode ser feito agora, sem VPS ou domínio.

- [x] Criar conta DigitalOcean (login via GitHub)
- [x] Registrar domínio `nousflow.com.br` no Registro.br
- [x] Criar conta Cloudflare (login via GitHub)
- [x] Confirmar acesso às chaves Stripe (sk_test_ para production_test)
- [ ] Pegar DSN do Sentry (conta existe, pegar na hora do .env)

### Fase 2 — Preparação do domínio ✅ (propagação em andamento)
Depende da Fase 1.

- [x] Adicionar `nousflow.com.br` ao Cloudflare
- [x] Trocar nameservers no Registro.br para os do Cloudflare
- [ ] Aguardar propagação (iniciada ~14h BRT 2026-04-17, até 24h)
- [ ] Criar registro A: `api.nousflow.com.br → <VPS_IP>`

### Fase 3 — Criação e segurança do VPS ✅
Depende da Fase 1. Pode rodar em paralelo com a Fase 2.

- [x] Criar Droplet: Ubuntu 24.04, NYC1, 2GB/50GB, SSH key `nousflow-deploy`
- [x] IP público: `<VPS_IP>`
- [x] `apt update && apt upgrade -y` + reboot
- [x] Criar usuário `<VPS_USER>` + grupos (sudo, docker)
- [x] Transferir SSH key para o usuário `<VPS_USER>`
- [x] Configurar UFW (allow 22, 80, 443 → enable)
- [x] Editar `/etc/ssh/sshd_config` (PasswordAuthentication no, PermitRootLogin no)
- [x] Reiniciar sshd e testar login como `<VPS_USER>`
- [x] Instalar Docker 29.4.0

### Fase 4 — Configuração do servidor ✅
Depende da Fase 3.

- [x] Clonar repositório: `git clone https://github.com/Brunotlps/wss-backend-v0.git`
- [x] `cp .env.example .env`
- [x] Preencher `.env` com valores production_test
- [x] Gerar SECRET_KEY e senha do banco
- [x] Remover `ports` do db, redis e backend no docker-compose.yml (commit `b14aef9`)
- [x] `mkdir -p backend/logs`
- [x] `chmod 600 .env`

### Fase 5 — Primeiro deploy (HTTP) ✅

### Fase 6 — SSL e HTTPS ✅
- Certbot standalone (não --nginx, pois Docker ocupa porta 80)
- `docker compose stop nginx` → certbot → `docker compose start nginx`
- Cert em `/etc/letsencrypt/live/api.nousflow.com.br/`
- Montado em nginx via volume `/etc/letsencrypt:/etc/letsencrypt:ro`

### Fase 7 — Validação e go-live ✅
- Smoke test E2E completo: registro, login, JWT, cursos, PaymentIntent Stripe
- Upload de vídeos funcionando
- Frontend Vercel conectado: `VITE_API_URL=https://api.nousflow.com.br`

### Fase 8 — Operações ✅ (concluída 2026-04-27)
Após go-live.

- [x] Configurar destino offsite — Backblaze B2 + rclone (remote `b2`, bucket `wss-backups`)
- [x] Criar `/home/<VPS_USER>/scripts/backup_db.sh` com retenção 30 dias
- [x] Criar `/home/<VPS_USER>/scripts/backup_media.sh` (volume `wss-backend-v0_media_volume` via Alpine)
- [x] Agendar via crontab: `0 2 * * *` (db) e `0 3 * * *` (media)
- [x] Testar ambos os scripts e verificar arquivos no B2
- [x] Testar restauração de backup (banco temporário, 21 tabelas validadas)
- [x] Configurar UptimeRobot para monitorar `https://api.nousflow.com.br/api/health/` a cada 5min
- [x] Fix: adicionar HEAD ao health check endpoint (commit `c353de5`)

---

## Template do .env — Fase production_test (Sprint 11)

> **Fase production_test:** Stripe em modo teste, dados sintéticos, sem cobrança real.
> Para virar produção real: trocar chaves Stripe, ENVIRONMENT=production, e rodar `docker compose down -v` para limpar o banco.

```env
# Django
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
SECRET_KEY=<gerar com get_random_secret_key()>
ALLOWED_HOSTS=api.nousflow.com.br

# Banco
POSTGRES_DB=wss_test_db
POSTGRES_USER=wss_user
POSTGRES_PASSWORD=<gerar com secrets.token_urlsafe(32)>
DATABASE_URL=postgres://wss_user:<senha>@db:5432/wss_test_db

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Gunicorn
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120

# Superuser
DJANGO_SUPERUSER_EMAIL=admin@nousflow.com.br
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=<senha forte e única>

# CORS — frontend Vercel
CORS_ALLOWED_ORIGINS=https://wss-frontend-seven.vercel.app

# Stripe — MODO TESTE (production_test)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # gerado no painel Stripe após criar o endpoint

# Sentry
SENTRY_DSN=https://...@sentry.io/...
ENVIRONMENT=production_test
RELEASE_VERSION=1.0.0-test

# Email (console até implementar emails transacionais no Sprint 12)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

## Migração production_test → production (quando chegar a hora)

```bash
# No VPS — limpa banco e recomeça do zero com chaves live
docker compose down -v          # apaga containers + volume pgdata
# Editar .env: sk_test_ → sk_live_, ENVIRONMENT=production, POSTGRES_DB=wss_prod_db
docker compose up -d
```

---

## Comandos úteis no servidor

```bash
# Ver logs de todos os serviços
docker compose logs -f

# Ver logs de um serviço específico
docker compose logs -f backend

# Status dos containers
docker compose ps

# Reiniciar um serviço após mudança no .env
docker compose restart backend

# Rebuild após mudança de código
git pull
docker compose build backend
docker compose up -d backend

# Acessar shell Django
docker compose exec backend python manage.py shell

# Rodar migrations manualmente
docker compose exec backend python manage.py migrate

# Verificar uso de disco
df -h
du -sh backend/media/
```

---

## Mapa de dependências

```
Fase 1 (contas)
    ↓
Fase 2 (domínio)       Fase 3 (VPS + segurança)
    ↓                        ↓
    └──────────┬─────────────┘
               ↓
         Fase 4 (.env + config)
               ↓
         Fase 5 (deploy HTTP)
               ↓
         Fase 6 (SSL + HTTPS)
               ↓
         Fase 7 (validação + go-live)
               ↓
         Fase 8 (operações)
```

---

## Pontos de atenção

- **Domínio antes de tudo:** propagação DNS leva até 24h — registrar com antecedência
- **Certbot e Cloudflare:** desativar proxy temporariamente para o HTTP-01 challenge
- **Webhook Stripe:** sem isso, pagamentos não geram matrícula automaticamente
- **Backup antes do go-live:** configurar pelo menos o backup local antes de receber usuários reais
- **docker-compose ports:** remover exposição de porta 5432 (PostgreSQL) e 6379 (Redis) em produção
- **SECRET_KEY:** nunca reutilizar a do desenvolvimento; gerar nova exclusiva para produção
