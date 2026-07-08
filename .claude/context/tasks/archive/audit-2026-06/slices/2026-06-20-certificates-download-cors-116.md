# Slice: Download de certificado bloqueado por CORS (X-Accel derruba ACAO) (#116)

**Data:** 2026-06-20
**Branch:** `fix/cert-download-cors-116` → **PR #117** (squash → `2bbccff` em `main`)
**Milestone:** #2 Production Stabilization (NÃO é finding do audit)
**Status:** mergeado, **deployado e validado em prod 2026-06-20**. Issue fechada via merge.

## Bug

A action `download` devolvia `X-Accel-Redirect` p/ a location interna `/protected/` do nginx (#74).
O nginx, ao servir da location interna, **não propaga o `Access-Control-Allow-Origin`** que o
`corsheaders` adicionou na resposta do Django → o `fetch`/XHR autenticado do front era bloqueado por
CORS (preflight `OPTIONS` 200 OK, mas `GET` 200 **sem** ACAO → `net::ERR_FAILED`). Vídeo não sofre
(carrega via `<video src>` com URL assinada, sem header `Authorization`, sem CORS). Latente desde o
deploy de protected-media (#74, 06-17); só exposto agora que existem PDFs (pós-#110).

## Fix (FileResponse direto do Django)

`apps/certificates/views.py` — `download` agora retorna
`FileResponse(pdf_file.open("rb"), as_attachment=True, filename=..., content_type="application/pdf")`
em vez de X-Accel. Assim a resposta sai do Django (nginx não a substitui) e o `corsheaders` aplica o
ACAO normalmente. Certificados são ~5KB → offload do nginx era desnecessário. `HttpResponse`→
`FileResponse` no import.
- `apps/certificates/serializers.py` — docstring do `get_download_url` atualizada.
- `apps/certificates/tests/test_protected_media.py` — reescrito o teste do owner (assere corpo do
  PDF + ausência de `X-Accel-Redirect`); novo helper `_cert_with_real_pdf`.

**Segurança do #74 preservada:** continua atrás de `IsCertificateOwner` + filtro de queryset
(não-owner→404, anon→401); `/media/certificates/` segue `internal`; serializer não expõe
`pdf_file`/`pdf_url`. Sem path traversal (filename fixo). Sem leak de handle (Django fecha o
FileResponse).

## Verificação
- `pytest apps/certificates/`: **49 passed**; flake8/black/isort limpos; sem migration drift.
- code-reviewer: **APPROVE**, 0 Blocking/Major (Minor de docstring aplicado).
- **Prod:** download funcionou no front **após `docker compose restart backend`** (ver gotcha abaixo).

## ⚠️ Gotcha de deploy (custou um ciclo)
`docker compose up -d backend` **não recarregou** o gunicorn: o backend usa bind mount
(`./backend:/app`) e o gunicorn não tem auto-reload em prod → workers seguiram com o código antigo
(X-Accel) em memória mesmo após `git pull`. **Sempre `docker compose restart backend`** (ou
`--force-recreate`) em deploy só-de-código. Ver memória [[infra-deploy-restart-gotcha]].

## Follow-ups
- Validar e2e do front nos demais fluxos de certificado.
