# Log de execução — Bundle "Protected Content Delivery" (deploy único de nginx)

**Início:** 2026-06-17
**Issues no bundle:** #54, #55, #56 (Cycle 1) · #74 (Cycle 2) · #48 (Cycle 3)
**Branch:** `fix/protected-media-and-proxy-hardening`
**Estratégia:** todos os cycles tocam `nginx/nginx.conf` → commits por cycle, **um único deploy**
com `--force-recreate` ao fim (bind mount por inode — memory `infra_nginx_bind_mount_gotcha`).

## Causa-raiz compartilhada
Nginx servia `/media/` público (`expires 7d; Cache-Control public`) nos 3 server blocks. As
permissões DRF só protegiam o JSON; os bytes (vídeo pago, PDF com PII) eram fetcháveis por URL
adivinhável. Serializers ainda expunham `file` / `pdf_file` / `pdf_url` crus.

## Decisões de escopo (aprovadas por Bruno)
1. **#55/#56 entram no Cycle 1** — a view de mídia protegida precisa do `IsEnrolled` correto,
   senão o bypass só muda de endereço (playbook `01` § "Order / dependencies").
2. **Rename para UUID adiado** — fechar o bypass público (`internal` + view autenticada) já
   resolve o Blocking; mover arquivos existentes em prod (path não-adivinhável) vira follow-up
   próprio. Done-criteria "non-guessable path" fica deferido.
3. **nginx escopado por cycle** — Cycle 1 locka só `/media/videos/`; `/media/certificates/`
   fica intacto até o Cycle 2 (#74), pra nenhum cycle quebrar entrega antes do fix do serializer.

---

## ✅ Cycle 1 — vídeos: entrega protegida + gating (#54, #55, #56) — CONCLUÍDO
**Commit:** `ddd1787` — `fix(videos): gate video files behind X-Accel-Redirect and is_free_preview`

### Mudanças
- `apps/videos/permissions.py` — `IsEnrolled` deriva preview de `is_free_preview` (Lesson) /
  `obj.lesson.is_free_preview` (Video) via helper `_is_free_preview`; elimina `order==1` (#56).
- `apps/videos/views.py` — nova `VideoFileView(APIView)` (`IsEnrolled` + `X-Accel-Redirect` →
  `/protected/<file.name>`); `VideoViewSet` recebe `IsEnrolled` + `get_queryset()` que escopa
  **apenas a ação `list`** (instrutor segue gerindo vídeos órfãos via ações de objeto) (#54/#55).
- `apps/videos/serializers.py` — `file` vira `write_only`; novo `stream_url` gated
  (`_video_stream_url`) em `VideoSerializer` e `VideoListSerializer` (#54/#55).
- `apps/videos/urls.py` — rota `GET /api/videos/<pk>/file/` (`name="video-file"`).
- `nginx/nginx.conf` (3 server blocks) — `location /media/videos/ { internal; }` +
  `location /protected/ { internal; alias /app/media/; }`; thumbnails públicos por prefixo mais
  longo (`/media/videos/thumbnails/`); `/media/` (certificados etc.) mantido público.

### TDD
- RED: 9 falhas (endpoint inexistente, `file` cru exposto, `order==1` concedendo acesso, retrieve
  público). Testes que afirmavam comportamento inseguro foram **reescritos**, não duplicados.
- GREEN: `apps/videos/` **74 passed**; full suite **367 passed** (sem regressão).
- Coverage dos arquivos tocados: `views.py` 99% · `permissions.py`/`urls.py` 100% ·
  `serializers.py` 81% (faltantes são branches pré-existentes de serializers de Lesson).
- Linters: flake8 / black / isort limpos.

### Gate code-reviewer (2 rodadas)
- 1ª rodada: **1 Blocking** (list de `VideoViewSet` com `Video.objects.all()` vazava metadados de
  todos os vídeos a anônimos) + **1 Major** (lockdown global de `/media/` quebraria PDF de
  certificado antes do #74).
- Correções: `get_queryset()` escopando só o `list`; nginx reescopado para `/media/videos/`;
  + nits (docstring do `IsEnrolled`, `del response["Content-Type"]`).
- 2ª rodada: **APPROVE, sem Blocking.**

### Done-criteria
- [x] GET de arquivo por anônimo/não-matriculado → 401/403 (não os bytes)
- [x] Nenhum `/media/videos/...` público; bytes só via view autenticada
- [x] Serializers não retornam URL de mídia fetchável
- [x] Preview deriva de `is_free_preview`, não `order`
- [x] Allow+deny tests (owner/other/anon/enrolled/preview)
- [ ] *(deferido)* path UUID não-adivinhável

---

## ⏳ Cycle 2 — certificados: PDF protegido (#74) — PENDENTE
- `certificates/serializers.py`: parar de expor `pdf_file` e `pdf_url`.
- `certificates/views.py`: action `download` → `X-Accel-Redirect` (hoje `FileResponse`).
- `nginx.conf`: adicionar `location /media/certificates/ { internal; }` (o `/protected/` já existe
  do Cycle 1).
- Deny-test: certificado revogado/não-dono negado.

## ⏳ Cycle 3 — proxy hardening (#48) — PENDENTE
- Backlog detalhado: `.claude/context/backlog/2026-06-15-nginx-xff-num-proxies-48.md`.
- Bloco `api` (:443): `set_real_ip_from <faixas CF>` + `real_ip_header CF-Connecting-IP` +
  sobrescrever XFF; reconciliar `NUM_PROXIES` (2→1, validar bloco `upload`).

---

## Deploy final (após Cycle 3) — checklist
1. `nginx -t` no VPS (o teste local falha só por não resolver o upstream `wss_backend`).
2. `docker compose up -d --force-recreate nginx` (bind mount por inode).
3. Smoke: `GET /media/videos/<x>.mp4` direto → 404/403; `GET /api/videos/<id>/file/` matriculado
   → 200 + arquivo; thumbnail público → 200; PDF de certificado só via download autenticado.
4. Confirmar chave de throttle = IP real do cliente (CF-Connecting-IP).
