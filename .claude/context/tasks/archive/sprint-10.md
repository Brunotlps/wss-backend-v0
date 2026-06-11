# Sprint 10 — Deploy Readiness

**Sprint:** 10  
**Start Date:** 2026-04-14  
**Branch:** claude-edits  
**Status:** ⬜ Não iniciado

---

## Objetivo

Tornar o backend deployável em produção. Toda a lógica de negócio está completa
(Sprints 8 e 9). O que falta são as correções de infraestrutura que impedem o
container de rodar corretamente em ambiente produção.

**Foco exclusivo:** infraestrutura e operações — sem novas features de negócio.

---

## Análise do Estado Atual

### O que já existe e está correto ✅

| Artefato | Status |
|---------|--------|
| `docker-compose.yml` | Completo — PostgreSQL, Redis, Django, Celery worker, Celery beat |
| `config/settings/production.py` | Completo — HSTS, HTTPS, WhiteNoise, Sentry, logging rotativo |
| `.env.example` | Existe — documenta todas as variáveis |
| `Dockerfile` | Existe — Python 3.12-slim, dependências do sistema |
| `entrypoint.sh` | Existe — migrations, collectstatic, superuser |
| `planning_deploy/` | Documentação anterior de planejamento |

### O que está bloqueando o deploy 🔴

**1. `runserver` em produção**  
`entrypoint.sh` termina com `exec python manage.py runserver` — servidor de
desenvolvimento, single-threaded, sem tratamento de erros de produção.

**2. Gunicorn ausente**  
`gunicorn` não está no `requirements.txt`. Sem ele não há como rodar em produção.

**3. `libmagic` ausente no Dockerfile**  
`python-magic` (validação de upload de vídeo) depende de `libmagic1` no sistema.
Está instalado localmente mas ausente no Dockerfile — uploads quebram no container.

**4. Credenciais hardcoded no `entrypoint.sh`**  
```bash
email='admin@example.com', password='admin123'
```
Cria superuser com credenciais conhecidas em qualquer ambiente que rodar o container.

---

## Tasks

### P0 — Crítico (blockers de deploy)

---

#### P0.1 — Gunicorn como servidor de produção

**Arquivos:** `backend/requirements.txt`, `backend/entrypoint.sh`, `backend/Dockerfile`

**Problema:** `entrypoint.sh` usa `runserver`. O Django documenta explicitamente
que `runserver` não deve ser usado em produção (sem multi-threading, sem graceful
shutdown, sem tratamento de sinais POSIX).

**Solução:**

1. Adicionar ao `requirements.txt`:
```
gunicorn==23.0.0
```

2. Substituir no `entrypoint.sh` a linha final:
```bash
# ANTES:
exec python manage.py runserver 0.0.0.0:8000

# DEPOIS:
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -
```

3. Limpar no `Dockerfile` o `CMD` morto (não tem efeito pois ENTRYPOINT está definido,
   mas é enganoso):
```dockerfile
# Remover esta linha:
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

4. Adicionar ao `.env.example`:
```
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120
```

**Por que 3 workers?**  
Fórmula padrão Gunicorn: `2 * CPU_cores + 1`. Para um VPS de 1 core, 3 workers é
o ponto de partida correto. Parametrizado via env var para ajuste por ambiente.

**Testes a escrever:**  
Não aplicável — operacional, sem lógica de negócio. Validação é funcional
(subir o container e verificar que responde).

---

#### P0.2 — `libmagic` no Dockerfile

**Arquivo:** `backend/Dockerfile`

**Problema:** `python-magic` usa a biblioteca C `libmagic1` para detecção de MIME type.
No `apt-get install` do Dockerfile faltam `libmagic1` e `file` (utilitário base).
Localmente funciona pois a lib está instalada no sistema operacional do dev.

**Solução:** Adicionar ao bloco `apt-get` do Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    netcat-openbsd \
    libmagic1 \        # ← adicionar
    file \             # ← adicionar
    && rm -rf /var/lib/apt/lists/*
```

**Validação:** Upload de vídeo com MIME inválido deve retornar 400 dentro do container.

---

#### P0.3 — Superuser via variáveis de ambiente

**Arquivo:** `backend/entrypoint.sh`, `.env.example`

**Problema:** Credenciais hardcoded (`admin@example.com` / `admin123`) criam um
superuser com senha pública em qualquer ambiente que rodar o container.

**Solução:** Ler credenciais de env vars, com skip se não estiverem definidas:

```bash
echo "👤 Creating superuser if it doesn't exist..."
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
email = '${DJANGO_SUPERUSER_EMAIL}'
username = '${DJANGO_SUPERUSER_USERNAME:-admin}'
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        email=email,
        username=username,
        password='${DJANGO_SUPERUSER_PASSWORD}'
    )
    print('✅ Superuser created: ' + email)
else:
    print('ℹ️  Superuser already exists: ' + email)
"
else
    echo "⚠️  DJANGO_SUPERUSER_EMAIL/PASSWORD not set — skipping superuser creation"
fi
```

Adicionar ao `.env.example`:
```
DJANGO_SUPERUSER_EMAIL=admin@yourdomain.com
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=change-me-on-first-login
```

---

### P1 — Importante (deploy frágil sem isso)

---

#### P1.4 — Endpoint `/api/health/`

**Arquivo:** `backend/apps/core/views.py` (novo), `backend/config/urls.py`,
`backend/docker-compose.yml`

**Problema:** O healthcheck do docker-compose usa `python manage.py check --database default`
— lento (~2s), carrega todo o Django, executado a cada 30s em cada container.
Load balancers e plataformas cloud esperam um endpoint HTTP simples.

**Solução:** View mínima em `apps/core/`:

```python
# apps/core/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness probe — retorna 200 se o processo está vivo."""
    return Response({"status": "ok"})
```

Registrar em `config/urls.py`:
```python
path("api/health/", health_check, name="health-check"),
```

Atualizar docker-compose healthcheck:
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/api/health/ || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 40s
```

Adicionar `curl` ao Dockerfile (para o healthcheck funcionar dentro do container):
```dockerfile
RUN apt-get update && apt-get install -y \
    ...
    curl \
    ...
```

**Testes a escrever:**
- `test_health_check_returns_200_unauthenticated`
- `test_health_check_response_format`

**Nota:** Este endpoint é *liveness probe* — verifica que o processo está vivo.
Não é *readiness probe* (não verifica DB/Redis). Isso é intencional:
se o DB cair, o Gunicorn ainda está de pé e o load balancer não deve
redirecionar — a app deve tentar reconnect. Readiness pode ser adicionado depois.

---

#### P1.5 — Nginx como reverse proxy

**Arquivo:** `docker-compose.yml`, `nginx/nginx.conf` (novo arquivo na raiz)

**Problema:** O backend está exposto diretamente na porta 8000 sem reverse proxy.
Em produção, o Nginx é necessário para:
- Terminar SSL (HTTPS)
- Servir static/media files sem passar pelo Django/Gunicorn
- Rate limiting no nível de rede
- Compression (gzip)
- Buffer de requests (protege Gunicorn de slow clients)

**Solução:** Adicionar serviço `nginx` ao `docker-compose.yml`:

```yaml
nginx:
  image: nginx:1.26-alpine
  container_name: wss_nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - static_volume:/app/staticfiles:ro
    - media_volume:/app/media:ro
    - ./nginx/certs:/etc/nginx/certs:ro  # para SSL
  depends_on:
    backend:
      condition: service_healthy
  networks:
    - backend_network
  restart: unless-stopped
```

Criar `nginx/nginx.conf` com:
- Upstream `backend` apontando para `wss_backend:8000`
- Serve `/static/` e `/media/` diretamente (sem passar pelo Django)
- Proxy reverso para todo o restante → Gunicorn
- Headers de segurança (X-Frame-Options, X-Content-Type-Options)
- Gzip habilitado
- Client max body size configurado para uploads de vídeo (500MB)
- Bloco comentado para HTTPS / SSL (ativado ao configurar certificado)

**Tradeoff:** Em plataformas como Railway, Render ou fly.io, o proxy reverso é
gerenciado pela plataforma — o serviço Nginx no docker-compose seria desnecessário
nesse caso. A config será criada para deploy em VPS (Docker direto no servidor).
Uma nota no arquivo documentará como desabilitar para cloud platforms.

---

### P2 — Desejável (qualidade e operações)

---

#### P2.6 — GitHub Actions CI

**Arquivo:** `.github/workflows/ci.yml` (novo)

**Objetivo:** Rodar a suite de testes completa automaticamente em cada push/PR
para `main`. Com 269 testes e 96% de cobertura, o CI é de valor imediato.

**Pipeline:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt
      - run: pytest --cov=apps --cov-fail-under=80
        working-directory: backend
        env:
          DJANGO_SETTINGS_MODULE: config.settings.development
          SECRET_KEY: ci-test-secret-key
          DATABASE_URL: sqlite:///test.db
          REDIS_URL: redis://localhost:6379/0
          CELERY_BROKER_URL: redis://localhost:6379/0
```

**Nota:** Usa SQLite em CI (sem PostgreSQL service) — suficiente pois os testes
já passam em SQLite localmente. PostgreSQL pode ser adicionado futuramente.

---

#### P2.7 — `manage.py check --deploy`

**Objetivo:** Rodar o check de deploy do Django e corrigir qualquer warning que
apareça antes de ir para produção.

```bash
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
```

Issues comuns que o check detecta:
- `SECURE_HSTS_SECONDS` não configurado
- `SECRET_KEY` fraco
- `SESSION_COOKIE_SECURE` ausente
- `CSRF_COOKIE_SECURE` ausente

O `production.py` já cobre a maioria — mas o check pode revelar algo pendente.
Qualquer issue encontrado será corrigido nesta task antes do merge.

---

## Progresso

| # | Task | Status | Prioridade | Commits |
|---|------|--------|------------|---------|
| P0.1 | Gunicorn como servidor de produção | ✅ Done | CRÍTICO | `6074397` |
| P0.2 | `libmagic` no Dockerfile | ✅ Done | CRÍTICO | `360d6a6` |
| P0.3 | Superuser via variáveis de ambiente | ✅ Done | CRÍTICO | `928bb67` |
| P1.4 | Endpoint `/api/health/` | ✅ Done | IMPORTANTE | `dfa1475` |
| P1.5 | Nginx como reverse proxy | ✅ Done | IMPORTANTE | `b0c57e8` |
| P2.6 | GitHub Actions CI | ✅ Done | DESEJÁVEL | `65f36d7` |
| P2.7 | `manage.py check --deploy` | ✅ Done | DESEJÁVEL | — |

**Progresso:** 7/7 tasks completas ✅

**Resultado P2.7:** `--tag security` → "System check identified no issues (0 silenced)".
21 warnings totais são todos `drf_spectacular.W001/W002` (schema Swagger), sem impacto no deploy.

---

## Ordem de Execução

```
P0.1 → P0.2 → P0.3   (fixes críticos — um commit cada)
     ↓
P1.4 → P1.5           (infraestrutura — um commit cada)
     ↓
P2.6 → P2.7           (qualidade — um commit cada)
     ↓
Merge + Push
```

As P0 podem ser commitadas juntas (são pequenas e relacionadas ao entrypoint/Dockerfile).
Cada P1 merece commit separado pela natureza diferente (app code vs config de infra).

---

## Princípios do Sprint 10

1. **Sem novas features de negócio** — escopo exclusivamente infraestrutura/deploy
2. **Nenhum teste de negócio deve quebrar** — os 269 testes devem continuar passando
3. **Testes para o que tem lógica** — endpoint `/api/health/` tem teste; fix de Dockerfile não
4. **Um commit por task** — mensagens com `fix:` ou `feat:` conforme o caso
5. **Validar container** — ao menos `docker-compose build` deve passar sem erros

---

## Decisões Técnicas

### Por que Gunicorn e não uWSGI ou Uvicorn?

Django recomenda Gunicorn oficialmente para WSGI. Uvicorn é para ASGI (async Django).
Este projeto usa WSGI puro (sem async views), então Gunicorn é a escolha correta.
uWSGI é mais complexo de configurar sem benefício adicional para este caso.

### Por que `--workers 3` e não mais?

Gunicorn usa processos (não threads). Cada worker carrega toda a aplicação Django
na memória (~80-120MB). Em um VPS de 1-2GB de RAM:
- 3 workers = ~360MB só para o Django
- 5 workers = ~600MB — arriscado em 1GB

`GUNICORN_WORKERS` como env var permite ajustar por ambiente sem alterar código.

### Por que não incluir notificações por email neste sprint?

Task 8 do planejamento anterior (emails transacionais) é feature de negócio, não
infraestrutura. Misturar features com deploy readiness aumenta risco e tamanho do
sprint. Emails pertencem ao Sprint 11 ou próximo sprint de features.

### Por que Nginx no docker-compose e não só no servidor?

Ter o Nginx configurado no docker-compose garante que o ambiente de staging
(docker-compose em um VPS) seja idêntico ao de produção. A alternativa (confiar no
Nginx do servidor) cria divergência entre ambientes.

Para plataformas cloud (Railway, Render, Heroku), o serviço Nginx pode ser removido
do compose pois a plataforma fornece o proxy. Isso será documentado.

---

## Validação Final (pré-merge)

```bash
# 1. Build sem erros
docker-compose build

# 2. Suite de testes continua passando
pytest --cov=apps --cov-fail-under=80

# 3. Deploy check sem erros
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy

# 4. Health check responde
curl http://localhost:8000/api/health/
# → {"status": "ok"}
```
