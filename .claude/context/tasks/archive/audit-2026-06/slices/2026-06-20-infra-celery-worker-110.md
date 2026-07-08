# Slice: Celery worker nunca rodou em prod (entrypoint ignora command) (#110)

**Data:** 2026-06-20
**Branch:** `fix/celery-worker-entrypoint` → **PR #113** (squash → `c77bd80` em `main`)
**Milestone:** #2 Production Stabilization (NÃO é finding do audit)
**Status:** mergeado, **deployado e validado em prod 2026-06-20**. Issue fechada.

## Bug

`backend/Dockerfile` usa `ENTRYPOINT ["/entrypoint.sh"]` e o `entrypoint.sh` termina com
`exec gunicorn …` **sem `exec "$@"`**. Logo o `command:` dos serviços `celery`/`celery-beat`
(`celery -A config worker/beat`) era **ignorado** — os containers `wss_celery`/`wss_celery_beat`
subiam **gunicorn**, não worker/beat. Resultado: nenhum worker consumia a fila do Redis; tasks
(ex.: geração de PDF de certificado via `generate_certificate_pdf_async.delay()`) ficavam presas
para sempre. Sintoma no front: certificado eterno "PDF em processamento" (`pdf_file` vazio,
`pdf_generation_failed_at=None`, `is_valid=True`).

Não era regressão (entrypoint inalterado desde o Sprint 10); `CELERY_TASK_ALWAYS_EAGER=True` só em
dev escondia o problema nos testes. Provado em prod 2026-06-19 (`docker compose logs celery` mostrava
access logs de gunicorn, não `celery@host ready`).

## Fix (Option B — compose-only)

Nos serviços `celery`/`celery-beat` (e staging `celery`): `entrypoint: ["celery"]` +
`command: ["-A","config","worker"/"beat","--loglevel=info"]`, bularem o `entrypoint.sh` do web.
`entrypoint.sh` e o serviço `backend` **não foram tocados** (menor risco). Arquivos:
`docker-compose.yml`, `docker-compose.staging.yml`.

## Deploy + validação (prod 2026-06-20)

`docker compose up -d --force-recreate celery celery-beat`. Worker subiu `celery@… ready`,
conectado a `redis://redis:6379/0`, task registrada. As **4 tasks de cert presas já estavam na fila
do Redis** (broker up há 2 semanas, nunca perdeu) e drenaram sozinhas ao subir o worker — certs 1–4
geraram PDF (`pdf=True`, `failed_at=None`). Reprocesso manual ficou desnecessário.

> ⚠️ Efeito colateral durante o deploy: o `--force-recreate` expôs o bug do nginx (IP do backend
> obsoleto) → 502 geral; resolvido com `docker compose restart nginx`. Virou a issue **#114**.

## Verificação
- CI verde (mas não prova o fix: `CELERY_TASK_ALWAYS_EAGER` nos testes). Validação foi operacional.
- Prod: worker `ready`, certs 1–4 com PDF, download disponível.

## Follow-ups
- **#78** — limpar retry vs final-failure da task de PDF.
- Memória: [[infra-celery-entrypoint-bug]].
