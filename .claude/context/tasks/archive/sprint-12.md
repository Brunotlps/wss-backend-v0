# Sprint 12 — Preparação para MVP Real

**Sprint:** 12
**Start Date:** 2026-04-27
**Branch:** claude-edits
**Status:** ⏸️ Pausado/superado — arquivado em 2026-07-04, nunca concluído

---

**Nota de arquivamento (2026-07-04):** este sprint foi pausado antes da Fase 1 (Stripe live)
rodar — a prioridade do projeto virou a remediação da auditoria 2026-06 (Blocking → Major → Minor),
que consumiu todo o ciclo de 2026-06-18 a 2026-07-04 e foi feita direto em `main` via branches
`fix/*`/`docs/*`, não na branch `claude-edits` referenciada aqui. Nenhuma fase deste sprint foi
concluída: Fase 1 (Stripe live) e Fase 2 (limpeza de dados de teste) nunca rodaram; Fase 3 ficou
parcial (3.2 e 3.5 feitas, **3.4 staging tem trabalho real não mergeado na branch `claude-edits`**
— `docker-compose.staging.yml`/`.env.staging.example`/`nginx.staging.conf` — mantida, não apagada
na limpeza de branches de 2026-07-04). Retomar quando a ativação do Stripe live voltar a ser
prioridade.

---

## Objetivo

Habilitar o backend para receber dinheiro real, limpar os dados de teste acumulados e preparar a infraestrutura para o ciclo de desenvolvimento pós-MVP (staging, logs, observabilidade).

---

## Contexto

O fluxo de pagamentos já foi validado em test mode com usuários e transações fictícias. Não há usuários reais no banco — todos os dados são de teste. O frontend ainda está funcionando, em fase de consolidação.

---

## Preparação e esclarescimentos

Antes de executar o sprint, tivemos um ajuste na dinâmica. Quero cadastrar a conta referente às transações reais sendo ela no CNPJ e banco de recebimento da empresa que estou prestando o serviço. Portanto isto é de extrema importância para o contexto e orientação no momento de realizar o cadastro na stripe.

Tenho a seguinte dúvida: Posso cadastrar os dados da conta em questão no mesmo fluxo em que já estou trabalhando na Stripe? Me refiro a clicar em ativar conta de produção e então cadastrar a conta que iremos utilizar. Este é um fluxo seguro?

## Fases

---

### Fase 1 — Stripe Live: Transação Real ✅/🔄

**Objetivo:** Ativar as live keys do Stripe e confirmar que o fluxo completo funciona com dinheiro real.

#### 1.1 — Preparação no Stripe Dashboard

- [ ] Ativar conta Stripe para pagamentos reais (verificação de identidade/empresa, se pendente)
- [ ] Criar endpoint de webhook live no Stripe Dashboard apontando para `https://api.nousflow.com.br/api/webhooks/stripe/`
- [ ] Selecionar evento: `payment_intent.succeeded`
- [ ] Copiar o novo `STRIPE_WEBHOOK_SECRET` (começa com `whsec_live_...`)
- [ ] Copiar `STRIPE_PUBLIC_KEY` e `STRIPE_SECRET_KEY` live

#### 1.2 — Atualizar produção

- [ ] Acessar VPS via SSH (`<VPS_USER>@<VPS_IP>`)
- [ ] Editar `.env` no servidor — atualizar as três variáveis Stripe para live
- [ ] Reiniciar containers: `docker compose up -d --build backend`
- [ ] Confirmar health check: `curl -I https://api.nousflow.com.br/api/health/`

#### 1.3 — Validação com transação real

- [ ] Criar um curso com preço simbólico (ex: R$ 1,00) via admin ou API
- [ ] Realizar a compra completa com cartão real
- [ ] Confirmar no Stripe Dashboard que a transação aparece em modo live
- [ ] Confirmar que o webhook foi recebido e processado (logs do container)
- [ ] Confirmar que a matrícula foi criada no banco
- [ ] Confirmar que o certificado foi gerado (se aplicável ao curso)

#### 1.4 — Teste de falha

- [ ] Tentar compra com cartão recusado — confirmar que nenhuma matrícula é criada
- [ ] Confirmar que reembolso via Stripe Dashboard não quebra nada no backend

#### Critério de conclusão

> Uma transação real processada, matrícula criada, sem erros no Sentry.

---

### Fase 2 — Limpeza de Dados de Teste

**Objetivo:** Zerar os dados de teste do banco, deixando o ambiente pronto para usuários reais.

> ⚠️ **Executar apenas após Fase 1 concluída e validada.**

#### 2.1 — Backup pré-limpeza

- [ ] Rodar `backup_db.sh` manualmente antes de qualquer limpeza
- [ ] Confirmar que o dump chegou no Backblaze B2
- [ ] Guardar o nome do arquivo de backup (referência para restauração de emergência)

#### 2.2 — Identificar dados de teste

Via `docker exec -it wss_postgres psql` ou Django admin, mapear:

- [ ] Usuários de teste (emails com `@test.com`, `@example.com`, etc.)
- [ ] Pagamentos / Payment Intents de teste
- [ ] Matrículas criadas com dados de teste
- [ ] Certificados gerados para matrículas de teste
- [ ] Vídeos e cursos de teste (manter apenas o conteúdo real do primeiro módulo)

#### 2.3 — Executar limpeza

- [ ] Criar script de limpeza seletiva via Django shell (para controle e auditoria)
- [ ] Executar com supervisão, tabela por tabela
- [ ] **Manter:** usuário instrutor real, cursos reais, vídeos do primeiro módulo

#### 2.4 — Verificação pós-limpeza

- [ ] Confirmar contagens no banco (usuários, cursos, vídeos, matrículas)
- [ ] Confirmar que o sistema segue funcional após limpeza
- [ ] Rodar `backup_db.sh` novamente — este é o "backup pré-MVP"

#### Critério de conclusão

> Banco com zero dados de teste. Apenas conteúdo real e usuário instrutor.

---

### Fase 3 — Preparar API para Produção Final

**Objetivo:** Infraestrutura e configurações prontas para receber o frontend e usuários reais.

#### 3.1 — CORS para o frontend

- [ ] Identificar o domínio final do frontend (ex: `nousflow.com.br`, `app.nousflow.com.br`)
- [ ] Atualizar `CORS_ALLOWED_ORIGINS` em `production.py` com o domínio real
- [ ] Deploy e testar preflight request do frontend

#### 3.2 — Logs estruturados de pagamento

- [x] Adicionar logging explícito no webhook handler:
  - Recebimento do evento
  - Payment Intent ID processado
  - Matrícula criada (user + course)
  - Erros com contexto completo
- [ ] Confirmar que logs aparecem em `docker compose logs -f backend`

#### 3.3 — Sentry — alertas de pagamento

- [ ] Criar alerta no Sentry para erros no webhook handler (`apps.payments`)
- [ ] Confirmar que falhas de pagamento geram notificação (email ou Slack)
- [ ] Testar disparando um erro manual

#### 3.4 — Ambiente de staging

- [x] Criar `docker-compose.staging.yml` baseado no de produção
- [x] Criar `.env.staging.example` com Stripe **test keys** (template commitável)
- [ ] Configurar subdomínio `staging.api.nousflow.com.br` no Cloudflare
- [ ] Deploy e confirmar que staging sobe sem interferir em produção
- [ ] Staging passa a ser o ambiente para desenvolvimento e testes futuros

#### 3.5 — Checklist de segurança pré-MVP

- [x] `DEBUG=False` confirmado em produção
- [x] `ALLOWED_HOSTS` contém apenas os domínios corretos
- [x] Nenhum `sk_test_` ou credencial hardcoded no repositório
- [x] Rate limiting ativo nos endpoints de auth e pagamento
- [x] Sentry capturando erros sem PII exposto

#### Critério de conclusão

> Frontend consegue consumir a API em produção. Staging isolado funcionando. Alertas de pagamento ativos.

---

## Resumo de Entregas

| Fase | Entrega              | Critério                             |
| ---- | -------------------- | ------------------------------------ |
| 1    | Stripe live ativo    | Transação real processada end-to-end |
| 2    | Banco limpo          | Zero dados de teste                  |
| 3    | API production-ready | CORS, logs, staging, alertas ativos  |

---

## Dependências Externas

- Conta Stripe verificada para live payments
- Domínio do frontend definido (para CORS)
- Cartão real para transação de validação

---

## Riscos

| Risco                            | Mitigação                                                 |
| -------------------------------- | --------------------------------------------------------- |
| Webhook live com secret errado   | Verificar `STRIPE_WEBHOOK_SECRET` no .env antes de testar |
| Limpeza acidental de dados reais | Backup obrigatório antes da Fase 2                        |
| CORS bloqueando frontend         | Testar preflight antes de considerar Fase 3 concluída     |
