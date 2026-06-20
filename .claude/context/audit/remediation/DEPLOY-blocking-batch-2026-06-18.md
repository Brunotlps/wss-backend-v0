# Deploy Runbook — Blocking Remediation batch (#102–#109)

> **✅ EXECUTADO E VALIDADO em 2026-06-18 ~23:27 UTC.** Migrations 0003/0004/0005 aplicadas;
> backfill ok (is_valid=False=0, snapshot vazio=0); health público 200. Staging pulado (sem
> dados reais). Doc mantido como histórico/replay.
>
> **⚠️ Post-mortem (2026-06-19):** teste manual pós-deploy revelou que o serviço `celery` **roda
> gunicorn, não o worker** (`entrypoint.sh` ignora o `command` — bug pré-existente, **issue #110**,
> milestone #2). Por isso certificados ficam "PDF em processamento" (task enfileirada, nunca
> consumida). Também: vídeo com `duration` 0:00 (#111) e playback intermitente (#112). Nenhum é
> regressão deste lote. Corrigir #110 antes de seguir. Recriar serviços de worker exige
> `--force-recreate`.
>
> **✅ #110 RESOLVIDO E DEPLOYADO 2026-06-20** (PR #113, `c77bd80`). Fix compose-only: `celery`/
> `celery-beat` ganham `entrypoint: ["celery"]` + command próprio, bularem o `entrypoint.sh`. Deploy:
> `docker compose up -d --force-recreate celery celery-beat`. Worker `celery@… ready`; as 4 tasks de
> cert presas drenaram da fila do Redis sozinhas (broker nunca perdeu a fila) → certs 1–4 com
> `pdf=True`. Restam #111/#112.

**Data:** 2026-06-18
**Executor:** Bruno (no VPS). Claude preparou; **não** executa no servidor.
**Alvo:** produção `https://api.nousflow.com.br` — VPS `deploy@161.35.14.136`, projeto em
`/home/deploy/wss-backend-v0/`.
**Commit alvo:** `37f30d2` (HEAD da `main`).

## O que vai no deploy

8 PRs Blocking mergeados desde o último deploy (#99/#101, 2026-06-17):

| PR   | Issue(s)      | Resumo                                                           |
| ---- | ------------- | ---------------------------------------------------------------- |
| #102 | #39/#40       | `is_instructor` não-atribuível via API                           |
| #103 | #42           | profiles create/destroy removidos (fim do 500)                   |
| #104 | #28/#30       | enrollment duplicado → 409 + bloqueio mass-assignment            |
| #105 | #29           | progresso cross-course bloqueado (certificado fraudulento)       |
| #106 | #12           | dedupe de PaymentIntent + alerta de cobrança duplicada           |
| #107 | #73/#75       | `is_valid` = revogação só + código cripto (**migration 0003**)   |
| #108 | #77           | snapshot imutável do certificado (**migration 0004 + backfill**) |
| #109 | #73 follow-up | backfill do `is_valid` (**migration 0005**)                      |

**Migrations (só app certificates):** `0003` (max_length 15→24), `0004` (AddField×4 snapshot +
RunPython backfill), `0005` (RunPython backfill do is_valid). Aplicam **automaticamente** no start
do backend (`entrypoint.sh` roda `migrate --noinput`).

**Sem mudança de nginx** → rebuild normal, **não** precisa `--force-recreate`.
**Celery worker carrega código novo** (signal/task de certificados) → precisa rebuild/restart.

---

## 0. Staging — PULADO (decisão 2026-06-18)

Não há container de staging provisionado (`.env.staging` inexistente) e a prod está em **fase de
testes iniciais sem dados verdadeiros**. Decisão com Bruno: **validar direto em produção**, já que
os dados são descartáveis. Os testes destrutivos da seção 4 podem rodar em prod sem risco real;
opcionalmente limpar os artefatos depois. Backup (seção 2) e pré-flight (seção 1) **continuam
obrigatórios**.

## 1. Pré-flight em produção (read-only) — dimensiona o backfill do is_valid

Antes de qualquer mudança, medir o que a `0005` vai tocar:

```bash
cd /home/deploy/wss-backend-v0
docker compose exec backend python manage.py shell -c "
from apps.certificates.models import Certificate as C
print('is_valid=False total      :', C.objects.filter(is_valid=False).count())
print('  -> sem failed_at (flip) :', C.objects.filter(is_valid=False, pdf_generation_failed_at__isnull=True).count())
print('  -> com failed_at (mantém):', C.objects.filter(is_valid=False, pdf_generation_failed_at__isnull=False).count())
"
docker compose exec backend python manage.py showmigrations certificates
```

> Se "sem failed_at (flip)" for alto e inesperado, **pausar** e revisar antes do deploy
> (a 0005 vai marcar esses como is_valid=True). Esperado: número pequeno ou 0.

## 2. Backup do banco (antes de migrar)

```bash
# Usa o script já existente (pg_dump via docker exec wss_postgres)
/home/deploy/scripts/backup_db.sh
# fallback direto, se preferir:
# docker compose exec -T db pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > ~/backups/db/pre-deploy-2026-06-18.sql.gz
ls -lh /home/deploy/backups/db/ | tail -3
```

## 3. Deploy

```bash
cd /home/deploy/wss-backend-v0
git fetch origin
git checkout main
git pull --ff-only origin main
git log --oneline -1   # deve mostrar 37f30d2

# Rebuild + sobe backend (auto-migra via entrypoint) e o Celery (código novo de signal/task)
docker compose up -d --build backend celery celery-beat
```

Acompanhar o backend aplicar as migrations no boot:

```bash
docker compose logs -f backend
# procurar: "Running database migrations" → 0003, 0004, 0005 aplicadas → "Starting Gunicorn"
```

## 4. Verificação pós-deploy

**Migrations aplicadas + sem drift:**

```bash
docker compose exec backend python manage.py showmigrations certificates   # 0001..0005 [X]
docker compose exec backend python manage.py migrate --check               # sem pendências
```

**Smoke read-only (seguro em prod):**

```bash
# Health
curl -s -o /dev/null -w "%{http_code}\n" https://api.nousflow.com.br/api/health/      # 200

# profiles create removido → 405 (precisa de um token; ou checar via OPTIONS/headers)
# verificação pública de um certificado existente → 200, com is_valid coerente e snapshot
curl -s https://api.nousflow.com.br/api/certificates/validate/<UM_CODIGO_EXISTENTE>/ | head
```

**Smoke destrutivo (OK direto em prod — dados descartáveis):** registro com `is_instructor=true` →
usuário criado com `is_instructor=false`; matrícula duplicada → 409; mass-assignment no enrollment
ignorado. Opcionalmente apagar os usuários/matrículas de teste depois.
**Stripe:** NÃO disparar cobrança real. Só confirmar que `create-intent` responde 200; idempotência
já coberta por teste (mock) — validar em live só se houver fluxo de teste com cartão de teste.

**Spot-check do backfill (read-only):**

```bash
docker compose exec backend python manage.py shell -c "
from apps.certificates.models import Certificate as C
print('is_valid=False restantes (devem ser só os com failed_at):', C.objects.filter(is_valid=False).count())
print('snapshot vazio (devem ser 0 após 0004 backfill):', C.objects.filter(student_name_snapshot='').count())
"
```

## 5. Rollback

- **Preferir fix-forward.** As migrations 0004/0005 são data migrations (reverse=noop) e 0003 é
  AlterField (reverter p/ max_length=15 falharia se já houver códigos de 21 chars). Portanto **não**
  fazer downgrade de migration.
- Rollback real = **restaurar o backup do passo 2** + `git checkout b4bdb25` (estado #101) +
  `docker compose up -d --build backend celery celery-beat`.
- Se só o app quebrar (não dados): `git checkout b4bdb25` + rebuild já reverte o código; mas a
  schema 0003 permanece (inofensiva — coluna maior).

## 6. Pós-deploy

- Monitorar Sentry/logs por erros de webhook Stripe e do branch novo de "Duplicate charge detected".
- Confirmar UptimeRobot verde em `/api/health/`.
- Atualizar memória/`current-sprint` com o deploy feito.

## Follow-ups que NÃO entram neste deploy (backlog)

- **#38** — `on_delete` do certificate (CASCADE→SET_NULL/PROTECT): durabilidade total contra delete.
- **#78** — limpar retry vs final-failure da task de PDF.
- **payments** — auto-refund do intent duplicado; reuso de intent pendente; robustez webhook
  #13/#14/#16/#18.
- Depois do deploy validado: **Phase 2 (Major)** via `/audit-status`.
