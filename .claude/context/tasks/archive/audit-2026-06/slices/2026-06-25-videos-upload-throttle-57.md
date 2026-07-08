# Slice: throttle de upload de vídeo 10/day por usuário (#57)

**Data:** 2026-06-25
**Branch:** `fix/videos-upload-throttle-57` (a partir de `main`) → **PR #137** (squash → `main`)
**Layer:** `05-views-throttling.md` · **Phase 2 (Major)** · 5ª slice do bloco views/throttling
**Status:** mergeado, **deployado e validado em prod 2026-06-25**.

## Bug

`VideoViewSet` não definia `throttle_classes`; nada em `apps/videos/` limitava o create.
Uma conta de instrutor podia floodar o endpoint de upload (custo de storage + processamento).
`security.md` e `api-conventions.md` prescrevem `UploadRateThrottle (10/day)`.

## Fix (throttle com scope dedicado, só no create)

- `apps/videos/throttles.py` (novo) — `UploadRateThrottle(UserRateThrottle)` com
  **`scope = "video_upload"`** + `rate = "10/day"`.
- `apps/videos/views.py` — `get_throttles()` aplica o throttle **só** na action `create`;
  demais actions usam os defaults globais; o streaming (`VideoFileView`) mantém o scope
  próprio `video_stream` (#112), sem colisão.

### Por que o scope dedicado (Blocking pego no review)

`UserRateThrottle` tem `scope = "user"` por default → chave de cache `throttle_user_<id>`,
o **mesmo bucket** do throttle global `user` (1000/hour, em `config/settings/base.py`).
Sem o scope próprio, tráfego autenticado comum corroía a cota de upload (e uploads contavam
contra o limite global). `scope = "video_upload"` isola o bucket (`throttle_video_upload_<id>`).
Com `rate` na classe, `get_rate()` nunca consulta `DEFAULT_THROTTLE_RATES` → scope não precisa
de entrada em settings.

## Verificação

- RED: `test_upload_throttled_after_10_per_day` falhou como esperado (11º upload → 201).
- `pytest apps/videos/`: **100 passed** (97 + 3). flake8/black/isort limpos. Migration drift: nenhum.
- code-reviewer: 1ª passada pegou o **Blocking** do bucket compartilhado → corrigido (scope) e
  **re-revisado: APPROVE** (confirmou empiricamente que o teste de isolamento falha sem o scope).
- **Prod (2026-06-25):** smoke rollback-safe (scratchpad `smoke_57_upload_throttle.py`,
  atomic+raise, `APIRequestFactory`+`force_authenticate`, instrutor descartável):
  - `first 10 creates: [201×10]` · `11th create: 429` · **PASS**.
  - Sem `cache.clear()` global (bucket do throttle do usuário descartável deletado no início e no
    `finally`); vídeos **sem arquivo** → signal de duração retorna cedo e o `.delay` (on_commit) é
    descartado no rollback → **sem Celery, sem arquivos**, nada persistido.

## Testes adicionados (`apps/videos/tests/test_upload_throttle.py`)

- `test_upload_throttled_after_10_per_day` — 11º upload → 429.
- `test_upload_limit_isolated_from_other_authenticated_requests` — 15 GETs autenticados antes
  **não** consomem a cota; 10 uploads seguem disponíveis (prova o isolamento do bucket).
- `test_different_users_have_separate_limits` — contadores independentes por usuário.

## Done-criteria (`05`, #57)
- [x] upload (create) limitado a 10/day por usuário
- [x] bucket isolado do throttle global `user`
- [x] streaming (`video_stream`, #112) não colidido
- [x] validado em prod (2026-06-25)

## Notas
- Deploy foi só-de-código → `docker compose restart backend` (sem migração/rebuild/nginx).
- **Follow-up aberto (#136):** `PaymentIntentRateThrottle` (payments) tem o **mesmo defeito**
  latente (herda `scope="user"`, compartilha o bucket global). Fora do escopo do #57.
- Smoke scripts agora vivem no scratchpad da sessão, não na árvore do projeto
  (ver memória `feedback_smoke_script_location`).
- Próximo no Phase 2 views/throttling: **#88** (core: readiness endpoint `/health/ready/`) —
  **fecha o bloco views/throttling**.
