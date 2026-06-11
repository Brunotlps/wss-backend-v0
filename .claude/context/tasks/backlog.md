# Backlog — Itens Futuros

Itens planejados mas ainda não agendados em sprint. Cada entrada tem contexto suficiente para virar uma sprint quando priorizada.

---

## Upload Direto a Object Storage (R2/S3) via Presigned URL

**Origem:** Sprint 13 (2026-06-01) — durante a resolução do upload de vídeos, identificada como a solução profissional definitiva. Adiada porque é uma sprint de 2-3 semanas e o bloqueio imediato foi resolvido pela Opção A (subdomínio bypass do Cloudflare).

**Trigger para priorizar:**
- Disco do VPS > 70% (vide `architecture.md` — gatilho de migração de storage)
- Necessidade de upload por usuários não-técnicos (instrutores da empresa) pelo frontend
- Volume de vídeos crescendo a ponto de a entrega via VPS+Nginx virar gargalo de banda (limite 2TB/mês DigitalOcean)

### Arquitetura

O arquivo nunca passa pelo servidor nem pelo Cloudflare — vai direto do browser para o object storage:

```
1. Browser → Backend: "quero subir aula1.mp4, 250MB"
2. Backend → Browser: presigned PUT URL (válida ~10min, com condições de tamanho/content-type)
3. Browser → R2 (direto): PUT do arquivo
4. Browser → Backend: "terminei, chave = videos/2026/06/aula1.mp4"
5. Backend: cria o registro Video apontando para a chave
6. Playback: vídeo servido pelo R2/CDN
```

### Escopo de trabalho (estimativa ~9-12 dias úteis / sprint 2-3 semanas)

| Bloco | Esforço | Notas |
|-------|---------|-------|
| Conta R2 + bucket + CORS | 0.5 dia | CORS no bucket é a causa nº 1 de falha em upload direto |
| `django-storages` + `boto3` | 1 dia | `production.py:107-125` já tem o bloco S3 comentado |
| Endpoint presigned URL | 1.5 dia | `APIView` restrita a instrutores, com condições embutidas |
| UI de upload (admin ou frontend) | 2-3 dias | **Parte mais difícil.** Django Admin não foi feito para upload direto. Lugar natural é o frontend React → vira feature de frontend |
| Estratégia de validação | 1 dia | ⚠️ Perde o `python-magic` (validators.py:63) — servidor nunca vê os bytes. Tamanho/content-type via presigned; MIME real só com worker pós-upload |
| Migração de arquivos existentes | 0.5 dia | Script move volume local → R2, atualiza campo `file` |
| Playback + controle de acesso | 1-2 dias | Decisão: bucket público (simples, sem gating) vs URLs assinadas (preserva `IsEnrolled`, mais trabalho) |
| Backup + testes E2E + staging | 1.5 dia | Estratégia de backup muda (hoje tar do volume → B2) |

### Custo financeiro

- R2: ~$0.015/GB/mês storage, **egress R$ 0** (vantagem sobre S3)
- Free tier: 10GB storage, 1M operações escrita, 10M leitura/mês
- Para a escala atual: provavelmente dentro do free tier ou centavos/mês
- **O obstáculo é tempo de implementação e nova dependência, não custo**

### Decisões em aberto (resolver no planejamento da sprint)

1. **Upload no Django Admin ou no frontend React?** — o frontend é o lugar natural, mas exige coordenação entre repos
2. **Validação MIME** — aceitar a perda do `python-magic` ou implementar worker Celery de validação pós-upload?
3. **Playback** — bucket público ou URLs assinadas com expiração (gating de matrícula)?

### Pistas de que o projeto já previa isso

- Campo `Video.is_processed` (models.py:87) — preparado para pipeline de processamento assíncrono
- Celery já ativo (geração de certificados) — infra de worker disponível
- `architecture.md` Fase 3 já documenta R2/S3 como evolução de storage
