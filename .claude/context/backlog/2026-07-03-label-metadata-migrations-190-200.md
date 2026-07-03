# Slice: Label metadata migrations — updated_at help_text + User verbose_name (#190, #200)

**Data:** 2026-07-03
**Branch:** `chore/label-metadata-migrations-190-200` (a partir de `main` já com #63) → **PR #204 (squash → `main`, commit `ab1ff24`)**
**Layer:** Phase 3 · Slice 2 da **janela de migração** (#63 + #190 + #200)
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-03)**.

## Contexto

Os dois follow-ups de "label" carvados de slices anteriores (#190 do core #90; #200 do users #53), ambos
gerando migração metadata-only. Agrupados numa janela de migração com o índice do #63 → **um só deploy**.

**Por que sequencial (não PR único gigante):** #190 (base abstrata) e #200 (users) e #63 (videos)
gerariam migrações nos mesmos apps; em branches paralelas da mesma `main` os números colidiriam
(ex.: dois `videos/0005`). Solução: mergear #63 primeiro, depois branchar #190/#200 da `main` já
atualizada → grafo linear, sem conflito.

## Fix

- **#190** (`core/models.py`) — `TimeStampedModel.updated_at` help_text `"...object last updated"` →
  `"...was last updated"`. Por estar na base abstrata, gera `AlterField updated_at` em **cada app com
  subclasse concreta**: certificates/0007, courses/0005, enrollments/0004, payments/0002, users/0003,
  videos/0006 (6 migrações). core não tem model concreto → sem migração.
- **#200** (`users/models.py`) — `User.email`/`User.phone` verbose_name `"email_address"`/`"phone_number"`
  → `"email address"`/`"phone number"` → `users/0004` (AlterField, preserva
  `unique`/`error_messages`/`max_length`).

**Commits:** 2, um por issue (`makemigrations` após cada edit escopa a migração ao commit).

## Verificação

- flake8/black/isort limpos (migrations excluídas). `makemigrations --check` → No changes detected.
- **`sqlmigrate` nas 7 migrações → `(no-op)` em cada campo** (metadata-only, zero DDL). Dependências
  lineares (users 0003→0004; videos 0006→0005), sem número duplicado.
- Suíte **completa: 573 passed, 98.38%** (migrações cross-app aplicam limpo).
- **code-reviewer:** **APPROVE**, 0 findings — confirmou no-op de DB, fidelidade do `AlterField` do email
  (não dropa unique/error_messages), cadeias de dependência corretas.
- **PROD (deploy da janela):** `git pull` → `migrate --noinput` (8 migrações: videos/0005 índice +
  as 7 metadata) → `restart backend` + `restart celery celery-beat`. Validação: **todas aplicadas ✅**,
  health 200, 3 índices do videos confirmados no schema. Backup pré-migração feito
  (`pre-migrate-*.sql.gz`). Serviços do compose prod: `db`/`redis`/`backend`/`celery`/`celery-beat`/`nginx`
  (postgres = serviço **`db`**, container `wss_postgres`).

## Notas

- **#190/#200/#63 fechados e em prod.** A janela de migração agrupou 8 migrações num único `migrate`
  (1 índice + 7 no-op).
- **Gotcha de deploy registrado:** serviço postgres no compose de prod = **`db`** (não `postgres`);
  pg_dump com creds do container: `docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER"
  "$POSTGRES_DB"'`.
- **RESTA na Phase 3 apenas certificates #85** (envelope `{"error"}`→`{"detail"}` = **contrato de
  frontend**, coordenar com wss-frontend). Todo o resto do `08-lint-style` + hygiene está fechado.
