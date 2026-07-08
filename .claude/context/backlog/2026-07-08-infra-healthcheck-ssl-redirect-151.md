# Slice: fix backend Docker healthcheck false-healthy on SSL redirect (#151)

**Data:** 2026-07-08
**Branch:** `fix/infra-healthcheck-ssl-redirect-151` (a partir de `main`) → **PR #230 (squash →
`main`, commit `2f84a99`)**
**Layer:** nenhuma (infra, fora do mapa de camadas da auditoria original — achado em
2026-06-27, não faz parte dos 81 findings)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-08)**.

## Contexto

O healthcheck do container `backend` fazia `curl -f http://localhost:8000/api/health/` sem
header de proxy. Com `SECURE_SSL_REDIRECT=True` em produção, o `SecurityMiddleware` do Django
retorna **301** antes da view rodar (o curl interno não carrega `X-Forwarded-Proto: https`).
`curl -f` não falha em 3xx e não segue redirect, então o healthcheck saía com exit 0 e o
container era reportado "healthy" **sem a view de saúde (nem DB/cache) nunca terem rodado**. Se
o app ou o banco estivessem quebrados atrás do redirect, o healthcheck continuaria passando (falso
positivo). O caminho externo real (nginx → HTTPS) não era afetado — gap de observabilidade
interna, não uma indisponibilidade.

## Nota importante: não é um bug de código

O comportamento de redirect do `SecurityMiddleware` é correto e intencional — não há defeito de
aplicação aqui. O defeito estava inteiramente no `docker-compose.yml`. Por isso não houve um
ciclo RED→GREEN tradicional de bug; os testes novos são um **regression-lock** do contrato Django
do qual o `curl` corrigido depende.

## Fix (#151)

- `docker-compose.yml` — healthcheck do `backend` passou a enviar `-H 'X-Forwarded-Proto:
  https'` e apontar pro endpoint de **readiness** (`/api/health/ready/`, já verifica DB+cache,
  do #88) em vez do de liveness (`/api/health/`, sem dependências).
- `backend/apps/core/tests/test_views.py` — nova classe `TestReadinessCheckBehindSSLRedirect` (2
  testes, fixture `settings` do pytest-django simulando `SECURE_SSL_REDIRECT=True` só nesse
  escopo — off por padrão nos settings de dev/test).

## Verificação

- Confirmado empiricamente: sem o header → 301 (reproduz exatamente o bug); com o header → 200
  com a view de readiness rodando de verdade.
- `pytest apps/core/`: **26 passed**. flake8/black/isort limpos. `makemigrations --check
  --dry-run`: sem drift (não é mudança de model). `docker compose config -q`: YAML válido.
- **code-reviewer:** **APPROVE**, 0 findings bloqueantes. Confirmou: sem risco de carga nova
  (readiness usa a mesma throttle 120/min, 2/min de uso = 1.7% do budget); sem risco de
  restart-loop (`restart: unless-stopped` só reage a saída do processo; nada no repo observa
  status "unhealthy"); `SecurityMiddleware` roda primeiro no `MIDDLEWARE`, confirmando que os
  testes não passam "por acidente"; `docker-compose.staging.yml` tem o mesmo padrão mas foi
  deliberadamente deixado intocado (Sprint 12 arquivado, nunca deployado — fora de escopo).
  Nit informativo: mudança de `healthcheck:` exige recriar o container, não só `restart`.

## Deploy

- **Mudança em `docker-compose.yml`** (não só código) — `restart backend` **não** aplica; precisou
  de `docker compose up -d --force-recreate backend`. Por precaução (recreate troca o IP interno
  do backend — gotcha conhecido do nginx cachear IP antigo, #114), também rodado `docker compose
  restart nginx`.
- **Validado em prod (2026-07-08):** `docker inspect` confirma o `Healthcheck.Test` novo;
  `State.Health.Status` = `healthy`; `State.Health.Log` mostra **5 execuções consecutivas com
  exit code 0** e output real `{"status":"ready","checks":{"database":"ok","cache":"ok"}}` (sem
  nenhum 301 — está genuinamente executando a view de readiness); curl externo via HTTPS `200`.

## Notas

- Minor residual da auditoria original baixa **3 → 2** (restam #180, #183 — ambos mecânicos).
- `docker-compose.staging.yml` tem o mesmo padrão de healthcheck buggy, mas fica fora de escopo
  (ambiente nunca deployado, Sprint 12 arquivado). Se o staging for retomado, vale aplicar o
  mesmo fix lá.
