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

## ✅ Cycle 2 — certificados: PDF protegido (#74) — CONCLUÍDO
**Commit:** `f9977dd` — `fix(certificates): serve PDF via X-Accel-Redirect, drop public media URL`

### Mudanças
- `certificates/serializers.py` — remove `pdf_file` e `pdf_url`; adiciona `download_url` gated
  (aponta para a action, `None` se sem PDF).
- `certificates/views.py` — action `download`: `FileResponse` → `X-Accel-Redirect` para
  `/protected/<pdf_file.name>` + `Content-Disposition: attachment`; mantém `IsCertificateOwner`.
- `nginx.conf` (3 blocks) — `location /media/certificates/ { internal; }`.

### TDD
- RED: 4 falhas (serializer expondo `pdf_file`/`pdf_url`, sem `download_url`, download via
  `FileResponse`); 2 já passavam (non-owner 404, anônimo 401).
- GREEN: `apps/certificates/` **40 passed** · full suite **375 passed** (zero regressão).
- Coverage: `views.py` 100% · `serializers.py` 95% · linters limpos.
- code-reviewer: **APPROVE, sem Blocking.**

### Done-criteria
- [x] GET de PDF por anônimo/não-dono → 401/404
- [x] Nenhum `/media/certificates/...` público
- [x] Serializer não retorna URL de mídia fetchável
- [ ] *(deferido)* path UUID desacoplado do `certificate_code`
- [ ] *(deferido → #81)* download de certificado revogado negado (não é leak: dono = titular do PII)

## ✅ Cycle 3 — proxy hardening (#48) — CONCLUÍDO
**Commit:** `ae0d9ca` — `fix(users): trust Cloudflare real IP and reconcile NUM_PROXIES`
Backlog detalhado: `.claude/context/backlog/2026-06-15-nginx-xff-num-proxies-48.md`.

### Mudanças
- `config/settings/base.py` — `NUM_PROXIES` default 2 → 1.
- `nginx.conf` (http) — faixas CF `set_real_ip_from` + `real_ip_header CF-Connecting-IP` +
  `real_ip_recursive on`.
- `nginx.conf` (6 locations) — `X-Forwarded-For` → `$remote_addr` (descarta XFF forjado).
- `users/tests/test_throttling.py` — `TestProxyXForwardedForHandling` (NUM_PROXIES=1, anti-spoof,
  caso 1-entry do upload).

### TDD
- RED: 2 falhas (`NUM_PROXIES==1`; com 2 o prefixo forjado em `addrs[-2]` viraria a chave).
- GREEN: `TestProxyXForwardedForHandling` 3 passed · users **97 passed** · full suite **377 passed**.
- code-reviewer: **APPROVE, sem Blocking** (threat model validado nos 3 caminhos).

### Done-criteria
- [x] Chave de throttle = IP real do cliente em todos os caminhos
- [x] XFF forjado não burla o rate-limit
- [x] `upload` (sem CF) não confia em `CF-Connecting-IP`

---

## 🚀 PRONTO PARA DEPLOY ÚNICO — bundle completo (Cycles 1+2+3)
Commits no branch `fix/protected-media-and-proxy-hardening`: `ddd1787`, `f9977dd`, `ae0d9ca`
(+ docs). Suíte completa **377 passed**. **Ainda não deployado / não pushed.**

---

## Deploy final (após Cycle 3) — checklist
0. **`.env` do VPS:** remover a linha `NUM_PROXIES` (ou setar `=1`). Se ficar `=2`, o override do
   env anula o default novo e o fix do #48 fica inerte. (Major do code-reviewer.)
1. `nginx -t` no VPS (o teste local falha só por não resolver o upstream `wss_backend`).
2. `docker compose up -d --force-recreate nginx` **e** o serviço backend (para recarregar settings).
   Bind mount por inode → `--force-recreate` é obrigatório no nginx.
3. Smoke:
   - `GET /media/videos/<x>.mp4` e `GET /media/certificates/<code>.pdf` diretos → 404 (internal).
   - `GET /api/videos/<id>/file/` matriculado → 200 + bytes; não-matriculado → 403.
   - Download de certificado só via `/api/certificates/<id>/download/` autenticado (dono).
   - Thumbnail (`/media/videos/thumbnails/...`) público → 200.
4. Confirmar chave de throttle = IP real do cliente (ex.: `wss:1:throttle_register_<IP-público>`).
