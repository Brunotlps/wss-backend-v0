# Pré-Sprint 13 — Manutenção de Infraestrutura

**Sprint:** -
**Start Date:** 2026-05-29
**Branch:** chore/vps-maintenance (deletada)
**Status:** ✅ Concluída em 2026-06-01

---

### Contexto

VPS apresenta sinais de pressão de recursos que requerem atenção:

- Swap em uso: 26% (baseline anterior era 0%)
- 18 atualizações pendentes, incluindo 1 security update e reinicialização de kernel obrigatória

### Manutenção do VPS ✅

**Objetivo:** Me orientar a realizar manutenção preventiva e corretiva. Resolver alertas de saúde identificados durante o diagnóstico de upload, e verificar pontos de otimização do VPS sem comprometer a segurança.

**VPS:** DigitalOcean NYC1 — Ubuntu 24.04.4 LTS — `<VPS_IP>`

#### 1 — Investigar uso de Swap (26%) ✅

Observado em 2026-05-29 16:20 UTC. Baseline anterior era 0%.

```
Memory usage: 46%
Swap usage:   26%
*** System restart required ***
```

- [x] Executar `docker stats --no-stream` para identificar qual container está pressionando a RAM
- [x] Verificar `free -h` — confirmar se swap cresce continuamente ou é estável
- [x] Se o backend container estiver próximo de 1GB: avaliar redução de workers Gunicorn de 3 para 2
- [x] Registrar baseline pós-investigação para comparação futura

**Achados (2026-05-29):**

- `available: 1.1Gi` — RAM não estava sob pressão ativa no momento da investigação
- Swap de 339MB era **residual**: páginas do Celery worker movidas para disco ao longo de dias sem reboot
- Causa principal identificada: **limites de memória do Celery não estavam sendo aplicados** — `docker inspect wss_celery` retornava `0` enquanto o backend retornava corretamente `1073741824`
- Containers Celery foram recriados com `docker compose up -d --force-recreate celery celery-beat`
- Pós-fix: `wss_celery` confirmado em `402653184` (384MB) ✅

**Baseline real pós-investigação:**

| Container | Uso | Limite | % |
|---|---|---|---|
| `wss_backend` | 352MB | 1GB | 35% |
| `wss_celery` | 201MB | 384MB | 52% |
| `wss_celery_beat` | 37MB | 128MB | 29% |

**Atenção:** Celery worker em 201MB de baseline deixa apenas 183MB de headroom. Considerar aumentar o limite para 512MB no próximo deploy (junto com o item 2).

#### 2 — Aplicar 18 updates pendentes (inclui 1 security update) ✅

Executado em 2026-06-01 durante janela de baixo tráfego (produto em manutenção).

- [x] `sudo apt update && sudo apt upgrade -y` — 17 pacotes atualizados (Docker 29.5.2, containerd 2.2.4, snapd, kernel)
- [x] `sudo reboot`
- [x] Kernel atualizado: `6.8.0-110-generic` → `6.8.0-117-generic`
- [x] Containers voltaram automaticamente via `restart: unless-stopped`
- [x] Health check confirmado: `{"status": "ok"}`

**Achados pós-reboot (2026-06-01):**

- **Nginx host conflict:** Nginx instalado via `apt` no Ubuntu host competia pela porta 80. Antes do reboot, o Docker Nginx subia primeiro e tomava a porta — o conflito ficava oculto. Resolvido com `systemctl disable nginx`. Risco: se o Nginx for reinstalado via `apt` no futuro, o problema pode voltar.
- **Celery worker limite corrigido:** aumentado de 384M para 512M (PR merged). Baseline real: ~200MB / 512MB (39%).
- **Celery beat limite corrigido:** aumentado de 128M para 256M após beat atingir 99.59% do limite antigo. Baseline pós-fix: ~27MB / 256MB (10%).

**Baseline final pós-manutenção:**

| Container | Uso | Limite | % |
|---|---|---|---|
| `wss_backend` | 352MB | 1GB | 35% |
| `wss_celery` | 199MB | 512MB | 39% |
| `wss_celery_beat` | 27MB | 256MB | 10% |
| `wss_nginx` | 4MB | — | — |
| `wss_postgres` | 47MB | — | — |
| `wss_redis` | 15MB | — | — |
| **Swap** | **83MB** | **1GB** | **8%** |

#### Critério de conclusão

> ✅ Swap em 8% (< 10%). Servidor atualizado com kernel 6.8.0-117. Todos os containers online e com limites de memória corretos.

---

## Resumo de Entregas

| Fase | Entrega                              | Status                            |
| ---- | ------------------------------------ | --------------------------------- |
| 1    | Nginx `client_body_timeout 300s`     | ✅ Deployado — PR #5 (2026-05-29) |
| 2    | Barra de progresso no Django Admin   | ⏳ Pendente                       |
| 3    | Manutenção VPS (swap + apt + reboot) | ✅ Concluída — 2026-06-01 |

---

## Riscos

| Risco                                                   | Mitigação                                                                       |
| ------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Template override quebra list/change view do VideoAdmin | Testar todas as views do VideoAdmin após implementação                          |
| Reboot do VPS deixa containers offline                  | `restart: unless-stopped` garante auto-start; monitorar UptimeRobot             |
| Swap crescendo continuamente pós-investigação           | Se > 50% constante: reduzir workers Gunicorn ou upgrade do droplet para 4GB RAM |

## Regras

1. Seguir a dinâmica de trabalho: Você é Engenheiro de Software Sênior me ensinando a trabalhar, sou eu quem devo fazer as alterações, e quem deve de fato entender os problemas e tradeoffs em questão. Priorize isso sempre.
2. Leia os commits anteriores para melhor contexto e siga a estrutura de commits já estabelecida no projeto, um commit por arquivo modificado
3. Não faça alterações em arquivos sem pedir permissão antes
