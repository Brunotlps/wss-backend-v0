# Slice: Playback intermitente — throttle anônimo no streaming por Range (#112)

**Data:** 2026-06-22
**Branch:** `fix/video-streaming-scoped-throttle-112` → **PR #120** (squash → `main`)
**Milestone:** #2 Production Stabilization (NÃO é finding do audit)
**Status:** mergeado, **deployado e validado em prod 2026-06-22**. Issue fechada via merge.

## Bug

`<video src=".../api/videos/{id}/file/?sig=...">` dispara **muitas** requisições
HTTP Range por sessão (buffer progressivo + cada seek), e cada uma bate no
`VideoFileView` (valida o `sig`, devolve X-Accel-Redirect). Como o `<video>` não
manda `Authorization`, todas são **anônimas** → `AnonRateThrottle` (100/hora por IP)
→ ao passar de 100 numa sessão, **429** no meio do playback. Sintoma: playback
intermitente que "recupera depois" (quando a janela de 1h reseta).

Diagnóstico em prod: os logs mostravam `206` saudáveis (uso ficou < 100/h por sorte),
mas uma única sessão já gerava ~60 reqs em 2 min → risco iminente. Latente desde o
deploy de protected-media (#54/streaming assinado, 06-17), exposto ao usar de verdade.

## Fix (throttle scoped generoso — não isenção total)

Primeira ideia foi `throttle_classes = []`; trocado (a pedido + sugestão do review)
por um **scope dedicado**, que absorve sessão real E ainda limita abuso:
- `apps/videos/views.py` — `VideoFileView`: `throttle_classes = [ScopedRateThrottle]`
  + `throttle_scope = "video_stream"` (substitui o anon/user global só nesta view).
- `config/settings/base.py` — `DEFAULT_THROTTLE_RATES['video_stream'] = '2000/hour'`.
- `apps/videos/tests/test_streaming_throttle.py` (novo) — 2 testes via
  `patch.dict(SimpleRateThrottle.THROTTLE_RATES, ...)` (override_settings NÃO alcança
  a `THROTTLE_RATES` vinculada no import): (1) anon=2/h → 5 reqs sem 429 (imune ao anon);
  (2) video_stream=2/h → 3ª req = 429 (o scope ainda limita).

Segurança intacta: acesso segue gated por `sig` (escopo 1 vídeo, ~2h) ou `IsEnrolled`;
keying per-user (autenticado) / per-IP real via CF+NUM_PROXIES=1 (anônimo).

## Verificação
- `pytest apps/videos/`: **97 passed**; flake8/black/isort limpos (`apps/`).
- code-reviewer: **APPROVE**, 0 Blocking/Major (rodado sobre o diff final da versão scoped).
- **Prod (2026-06-22):**
  - Teste decisivo: 120 requisições Range ao `/file/` (cache-buster p/ furar CF) →
    **120× 206, ZERO 429** (código antigo daria 429 na ~100ª).
  - Uso real (seeks no player): **231× 206, ZERO 429**, sem travar.

## Done-criteria (#112)
- [x] Streaming não sofre o anon throttle (sem 429 no playback)
- [x] Teto defensivo mantido (scoped 2000/h)
- [x] Sem bypass de auth
- [x] Validado em prod

## Notas
- Deploy foi só-de-código → `docker compose restart backend` (sem rebuild/nginx).
- Caveat conhecido: múltiplos viewers **anônimos** atrás de um mesmo NAT compartilham o
  bucket `video_stream` (improvável incomodar a 2000/h; maioria é autenticada).
