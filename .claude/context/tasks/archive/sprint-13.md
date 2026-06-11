# Sprint 13 — Video Upload UX e Manutenção de Infraestrutura

**Sprint:** 13
**Start Date:** 2026-05-29
**Branch:** fix/video-upload
**Status:** ✅ Concluída — 2026-06-01. Upload de vídeo 100–300MB funcional via subdomínio bypass do Cloudflare

---

## Objetivo

Resolver o problema de upload de vídeos no Django Admin com feedback visual adequado, e executar manutenção preventiva na infraestrutura de produção.

---

## Contexto

Durante investigação de produção (2026-05-29), identificou-se que o upload de vídeos grandes (~100MB+) via Django Admin aparecia como "carregamento infinito". O diagnóstico revelou dois problemas distintos:

1. **UX:** o Django Admin não exibe barra de progresso durante uploads — o spinner gira por minutos sem feedback, levando o usuário a cancelar antes do upload completar.
2. **Infraestrutura:** o `client_body_timeout` padrão do Nginx (60s) poderia derrubar conexões instáveis antes do arquivo terminar de subir para o servidor. Corrigido no PR #5.

Adicionalmente, o VPS apresenta sinais de pressão de recursos que requerem atenção:

- Swap em uso: 26% (baseline anterior era 0%)
- 18 atualizações pendentes, incluindo 1 security update e reinicialização de kernel obrigatória

---

## Fases

---

### Fase 1 — Nginx: client_body_timeout para /admin/ ✅

**Objetivo:** Prevenir drops de conexão em uploads lentos ou instáveis via Django Admin.

**Root cause identificado:** Com `proxy_request_buffering on` (padrão Nginx), o Gunicorn só recebe a requisição após o Nginx bufferizar o arquivo completo. Para 114.7MB em conexão doméstica (5–20Mbps), isso leva 45s a 3 minutos. O `client_body_timeout` padrão de 60s entre leituras consecutivas poderia derrubar a conexão antes disso.

- [x] Adicionar `location /admin/` com `client_body_timeout 300s` no bloco HTTP (porta 80)
- [x] Adicionar `location /admin/` com `client_body_timeout 300s` no bloco HTTPS (porta 443)
- [x] Manter `proxy_request_buffering on` — protege os workers síncronos do Gunicorn
- [x] CI passou (269 testes), PR #5 mergeado, `nginx -t` validado em produção

#### Critério de conclusão

> ✅ Nginx recarregado sem erros em produção. Confirmado com `nginx -t` em 2026-05-29.

---

### Fase 2 — Barra de Progresso no Django Admin ✅

**Objetivo:** Exibir feedback visual durante o upload de vídeos para eliminar a percepção de travamento.

#### Abordagem: override de template com XMLHttpRequest nativo

Sem dependências externas. O `VideoAdmin` recebe um template customizado `change_form.html` que intercepta o submit do formulário e usa `XMLHttpRequest.upload.onprogress` para exibir uma barra de progresso. Ao receber a resposta do servidor, redireciona (302 sucesso) ou exibe erros (200 validação).

**Descartado:**

- Pacotes como `django-admin-resumable`: baixa manutenção, risco de incompatibilidade com Django 5.2
- TUS chunked upload: correto para longo prazo, mas escopo desproporcional para a necessidade atual

#### 2.1 — Template

- [x] Criar `backend/templates/admin/videos/video/change_form.html` estendendo `admin/change_form.html` (PR #8)
- [x] Injetar JS com `XMLHttpRequest` + handler `upload.onprogress`
- [x] Barra de progresso exibida apenas quando o formulário contém campo `file`

#### 2.2 — Comportamento esperado

- [x] Submit: botão "Salvar" desabilitado, barra de progresso visível com percentual e MB transferidos
- [x] Resposta 302 (sucesso): redirecionar via `xhr.responseURL`
- [x] Resposta 200 (erro de validação): renderizar o HTML de resposta com os erros Django visíveis
- [x] Botão de cancelamento durante o upload

#### Bugs encontrados e corrigidos em produção

1. **Template não carregava (resolvido):** confirmado via `get_template` que o Django encontrava o arquivo; o problema real era o bug 2.
2. **`insertBefore` NotFoundError (PR #9):** a `.submit-row` está aninhada num `<div>` intermediário, não é filho direto do form. `form.insertBefore()` lançava exceção e abortava o script antes de criar o container — o form caía no submit padrão (spinner infinito). Corrigido inserindo via `submitRow.parentNode`.
   - **Lição:** o teste local não pegou porque o upload em localhost é instantâneo (loopback) — `onprogress` não dispara e o redirect acontece antes de qualquer falha visível. Bugs de UI de upload só aparecem com latência real.

#### Critério de conclusão

> ✅ Barra de progresso funcional em produção (PR #8 + #9). Confirmada via DevTools: container criado, `onprogress` disparando, percentual avançando.

---

### Fase 2.5 — Bloqueio do Cloudflare (descoberta em produção) 🔴

Após a barra de progresso funcionar, o upload do arquivo de 109.4MB terminou em **`413 Payload Too Large`** — página servida pelo **Cloudflare**, não pelo Nginx (confirmado: nenhum POST com 413 nos logs do Nginx).

**Causa raiz:** O plano **Cloudflare Free limita o corpo de requisição a 100MB**. Os vídeos do projeto têm tipicamente 100–300MB, então o caminho do browser via `api.nousflow.com.br` (que passa pelo proxy do Cloudflare) está **permanentemente inviável** para uploads reais.

Isso também explica retroativamente por que o `client_max_body_size 500M` do Nginx nunca foi o gargalo — a requisição morria no Cloudflare antes de chegar ao Nginx.

---

### Fase 3 — Bypass do Cloudflare via subdomínio DNS-only (Opção A) ✅

**Objetivo:** Remover permanentemente o teto de 100MB para uploads, mantendo a barra de progresso e o acesso pelo browser.

**Decisão arquitetural:** O Cloudflare aplica proxy (e o limite) por hostname, não por path. A solução é um subdomínio dedicado **sem proxy do Cloudflare** (nuvem cinza / DNS-only), usado apenas para o admin.

```
api.nousflow.com.br    → Cloudflare (proxy, limite 100MB) → Nginx → Django   [API + frontend]
upload.nousflow.com.br → direto no VPS (sem Cloudflare)    → Nginx → Django   [admin/upload, sem limite]
```

**Custo financeiro: zero.** DNS Cloudflare gratuito, SSL via Let's Encrypt (já em uso), mesma infra.

**Custo de segurança (aceitável):** o subdomínio perde proteção do Cloudflare (WAF, DDoS, ocultação de IP). Como serve apenas o admin autenticado e só é usado para upload, o risco é baixo e controlado.

#### 3.1 — DNS (Cloudflare) ✅

- [x] Criar registro A: `upload` → `<VPS_IP>`, **Proxy status: DNS only (nuvem cinza)**
- [x] Confirmado via `dig +short upload.nousflow.com.br` → retorna o IP direto do VPS

#### 3.2 — Certificado SSL (no VPS) ✅

> Certbot **standalone** no host (não `--nginx`, Docker ocupa porta 80). Emissão exige parar o Nginx (~1min de downtime — feito em manutenção).

- [x] `docker compose stop nginx` → `sudo certbot certonly --standalone -d upload.nousflow.com.br` → `docker compose start nginx`
- [x] Cert em `/etc/letsencrypt/live/upload.nousflow.com.br/` (expira 2026-08-30, auto-renova)

#### 3.3 — Nginx (`nginx/nginx.conf`) ✅ (PR #10)

- [x] Server block HTTPS para `upload.nousflow.com.br` com `client_max_body_size 500M`, static/media/admin/fallback
- [x] `location /admin/` com `client_body_timeout 300s`

#### 3.4 — Django (`config/settings/production.py`) ✅ (PR #10)

- [x] `CSRF_TRUSTED_ORIGINS` derivado de `ALLOWED_HOSTS` (mantém sincronia via única mudança no `.env`)
- [x] `upload.nousflow.com.br` adicionado ao `ALLOWED_HOSTS` no `.env` do VPS

#### 3.5 — Validação ✅

- [x] Upload de vídeo via `https://upload.nousflow.com.br/admin/` com barra de progresso até 100%, **sem erro 413**
- [x] `api.nousflow.com.br` (API + frontend) intacto, ainda via Cloudflare (HTTP/2)

#### Gotcha de deploy encontrado

**Bind mount de arquivo único com inode trocado:** após `git pull`, o `nginx -t` e `nginx -s reload` continuavam lendo a config **antiga** dentro do container. O `nginx.conf` é montado como arquivo único; o `git pull` substitui o arquivo (inode novo), mas o bind mount aponta para o inode antigo. Sintoma: cert errado servido (`SSL: no alternative certificate subject name matches`). **Fix:** `docker compose up -d --force-recreate nginx`. Registrado na memória do projeto.

#### Critério de conclusão

> ✅ Upload de vídeo 100–300MB conclui via browser pelo subdomínio, sem erro 413, com barra de progresso funcional.

---

## Decisões Tomadas

| Opção | Decisão | Justificativa |
|-------|---------|---------------|
| **A — Subdomínio DNS-only** | ✅ **Escolhida (agora)** | Custo zero, esforço baixo, remove o teto de 100MB permanentemente, mantém a barra de progresso e o upload pelo browser para qualquer usuário do admin |
| **B — SCP + Django shell** | 🔵 Rede de segurança | Segura e sólida como ponte, mas inadequada como método permanente: processo manual via SSH a cada vídeo, não escala para usuários não-técnicos, bypassa os validators do modelo (`full_clean` não roda no `save`) |
| **C — Upload direto a R2/S3 (presigned)** | 📋 **Backlog** (futuro) | Solução profissional definitiva, mas é sprint de 2-3 semanas com decisões em aberto (validação MIME, signed URLs, admin vs frontend). Ver [backlog.md](backlog.md) |

---
