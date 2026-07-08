# Slice: Duração de vídeo nunca extraída — player 0:00 (#111)

**Data:** 2026-06-20
**Branch:** `fix/video-duration-ffprobe-111` → **PR #115** (squash → `f3cdce9` em `main`)
**Milestone:** #2 Production Stabilization (NÃO é finding do audit)
**Status:** mergeado, deployado (rebuild + backfill). Issue fechada via merge.

## Bug

`Video.duration` (DurationField) nunca era preenchido. O help_text prometia "auto-extracted from
file", mas **não havia extrator** (sem ffprobe/ffmpeg/moviepy; só `python-magic` p/ MIME).
`duration=None` → `duration_formatted="00:00:00"` → front mostra 0:00. Feature nunca implementada,
não regressão. Dependia do worker Celery ([[infra-celery-entrypoint-bug]], #110) p/ ser async.

## Fix (async via Celery — agora que o worker roda)

Decisão com Bruno: **ffprobe (pacote ffmpeg) async** + **management command de backfill**.

- `apps/videos/utils.py` (novo) — `extract_video_duration(path)`: wrapper `ffprobe` via `subprocess`
  (argv list, sem shell; `timeout=60`, `check=True`); nunca levanta, devolve `None` em falha.
- `apps/videos/tasks.py` (novo) — `extract_video_duration_async(video_id)`: seta `duration` +
  `is_processed=True`; idempotente/self-healing (deixa NULL em falha → re-rodável).
- `apps/videos/signals.py` (novo) + `apps.py ready()` — `post_save` em `Video` enfileira via
  `transaction.on_commit` quando há `file` e `duration is None` (cobre API **e** Django admin).
- `apps/videos/management/commands/backfill_video_durations.py` (novo) — `--sync` opcional.
- `backend/Dockerfile` — adiciona `ffmpeg`. **Sem migration** (help_text "auto-extracted" virou
  verdade).

## Verificação
- `pytest apps/videos/`: **95 passed** (12 testes novos: utils/tasks/signals/command).
- flake8/black/isort limpos; sem migration drift.
- code-reviewer: **APPROVE**, 0 Blocking (rodado sobre o diff; nits de type hint aplicados).

## Deploy
Requer **rebuild de imagem** (novo `ffmpeg`): `docker compose up -d --build backend celery`. Como
recria o `backend` (novo IP) → lembrar do **#114** (restart nginx depois). Backfill:
`docker compose exec backend python manage.py backfill_video_durations`.

## Follow-ups
- **#112** — playback intermitente / Range sobre URL assinada X-Accel (separado).
- `is_processed` agora significa "metadados extraídos" (não encoding) — semantic drift anotado.
- Teste de integração real do ffprobe (gated em `ffmpeg` disponível) — opcional.
