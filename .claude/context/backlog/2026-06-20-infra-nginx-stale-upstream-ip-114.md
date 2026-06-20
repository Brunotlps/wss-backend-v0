# Slice: nginx cacheia IP do backend no boot → 502 geral (#114) — ABERTA

**Data identificada:** 2026-06-20
**Branch/PR:** — (fix durável ainda não feito)
**Milestone:** #2 Production Stabilization (NÃO é finding do audit)
**Status:** **ABERTA**. Mitigada por workaround manual; fix durável pendente.

## Bug

O `nginx.conf` usa `proxy_pass http://backend:8000` (nome estático, sem `resolver`). O nginx
resolve `backend` **uma vez no start do worker** e cacheia o IP. Quando o backend troca de IP
(qualquer restart/recreate/deploy, ou reshuffle de rede ao recriar outros serviços) o nginx segue
batendo no IP morto → **502 (`connect() failed (111: Connection refused)`) em todas as rotas** —
queda total — mesmo com o backend saudável.

**Exposto em 2026-06-20** durante o deploy do #110 (`--force-recreate celery celery-beat`): site
caiu, backend vivo em `172.18.0.2` mas nginx cacheado em `172.18.0.4`.

## Mitigação aplicada (workaround manual)
`docker compose restart nginx` → re-resolve `backend` → site volta (200). Precisa repetir a cada
troca de IP do backend.

## Fix durável proposto (a implementar)
No `nginx.conf` (todos os 3 server blocks), usar o DNS embutido do Docker + proxy via variável:
```nginx
resolver 127.0.0.11 valid=30s;
set $backend_upstream http://backend:8000;
proxy_pass $backend_upstream;
```
Aplicar também às locations internas (X-Accel/protected) que apontam pro backend, se houver.

## Critérios de aceite
- [ ] nginx re-resolve o backend em runtime (resolver + `proxy_pass` via variável).
- [ ] Recriar o container do backend NÃO causa 502 (sem precisar reiniciar o nginx).
- [ ] `/api/health/` segue 200 através de um recreate do backend.
- [ ] Deployado e validado em prod.

## Notas
- Deploy de `nginx.conf` exige `docker compose up -d --force-recreate nginx` (bind mount por inode —
  [[infra-nginx-bind-mount-gotcha]]). Sugestão: juntar num deploy de borda com o **#112**.
- Memória: [[infra-nginx-stale-upstream-ip]].
