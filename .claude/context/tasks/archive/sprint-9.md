# Sprint 9 — Business Logic Completion

**Sprint:** 9  
**Start Date:** 2026-04-14  
**Branch:** claude-edits  
**Status:** ✅ Completo  
**Merge em main:** `1986378` (2026-04-14)

---

## Objetivo

Fechar as lacunas de negócio deixadas pelo Sprint 8:
- O sistema de pagamentos existe mas não é aplicado na criação de matrículas
- Alunos podem concluir todas as aulas sem que o curso seja marcado como concluído
- Celery está configurado mas desativado, deixando a geração de PDF síncrona

---

## Tarefas

### P0 — Críticas

#### Task 1: Validação de pagamento na matrícula [ ]

**Arquivo:** `apps/enrollments/views.py`  
**Método:** Override de `create()` em `EnrollmentViewSet`

**Lógica:**
```
POST /api/enrollments/
  → serializer.is_valid()
  → course = serializer.validated_data["course"]
  → se course.price > 0:
      → Payment.objects.filter(user, course, status=SUCCEEDED).exists()?
      → não: return HTTP 402
  → perform_create() → salva matrícula normalmente
```

**Status HTTP correto:** `402 Payment Required` (não 400 nem 403)
- 400 = dado inválido (não é o caso)
- 403 = sem permissão (não é o caso — qualquer um pode se matricular se pagar)
- 402 = ação requer pagamento

**Por que `create()` e não `perform_create()`:**  
`perform_create()` não retorna Response — lança exceptions. `ValidationError` retornaria 400 (semântica errada).
Overridar `create()` permite retornar `Response(status=HTTP_402)` diretamente e claramente.

**Por que não no serializer:**  
Serializer não tem acesso ao `request.user` sem contexto extra. Lógica de autorização pertence à view.

**Testes a escrever (TDD — RED primeiro):**
- `test_create_enrollment_free_course_returns_201` — cursos gratuitos sempre passam
- `test_create_enrollment_paid_course_without_payment_returns_402` — bloqueio correto
- `test_create_enrollment_paid_course_with_succeeded_payment_returns_201` — fluxo feliz
- `test_create_enrollment_paid_course_with_pending_payment_returns_402` — pagamento pendente não conta
- `test_create_enrollment_paid_course_with_failed_payment_returns_402` — pagamento falho não conta

**Teste existente que vai quebrar:**
- `test_create_enrollment_sets_user_to_current`: usa `CourseFactory()` que gera preço > 0 por padrão.
  **Correção:** trocar para `CourseFactory(free=True)`.

---

#### Task 2: Signal de conclusão automática de curso [ ]

**Arquivos a criar:**
- `apps/enrollments/signals.py`
- `apps/enrollments/apps.py`

**Arquivo a atualizar:**
- `apps/enrollments/__init__.py` → `default_app_config`

**Lógica do signal:**
```python
@receiver(post_save, sender=LessonProgress)
def check_course_completion(sender, instance, **kwargs):
    if not instance.completed:
        return                          # lição não foi concluída, ignora
    enrollment = instance.enrollment
    if enrollment.completed:
        return                          # já concluído, evita re-trigger
    total_lessons = enrollment.course.lessons.count()
    if total_lessons == 0:
        return                          # curso sem aulas não auto-completa
    completed_count = enrollment.lesson_progress.filter(completed=True).count()
    if completed_count >= total_lessons:
        enrollment.mark_as_completed()  # dispara → Enrollment.post_save → Certificate criado
```

**Cadeia de eventos após o signal:**
```
LessonProgress saved (completed=True)
  → check_course_completion (novo signal)
    → enrollment.mark_as_completed()
      → Enrollment.save() 
        → create_certificate_on_completion (já existe em certificates/signals.py)
          → Certificate criado + PDF gerado
```

**Por que signal e não lógica no serializer `update()`:**
- Signal cobre qualquer save do ORM (API, shell, fixtures, scripts de migração)
- Serializer só cobre updates via API — menos robusto
- Padrão já estabelecido no projeto (certificates usa o mesmo padrão)

**Testes a escrever (novo arquivo `test_signals.py`):**
- `test_completing_last_lesson_auto_completes_enrollment` — caminho feliz completo
- `test_completing_partial_lessons_does_not_complete_enrollment` — não dispara cedo demais
- `test_already_completed_enrollment_not_re_triggered` — idempotência
- `test_course_with_no_lessons_not_auto_completed` — edge case curso vazio
- `test_mark_as_completed_sets_completed_at_timestamp` — campo populated corretamente

**Observação sobre mocking:**  
Os testes de signal vão disparar o `create_certificate_on_completion`. É preciso mockar
`apps.certificates.signals.generate_certificate_pdf` para evitar erro em testes
(padrão já usado em `apps/certificates/tests/test_signals.py`).

---

### P1 — Importantes

#### Task 3: `AppConfig` para apps sem ela [ ]

**Apps afetados:** `enrollments`, `courses`, `videos`, `payments`, `core`

**Por que:** Sem `AppConfig`:
- Não é possível registrar signals via `ready()` de forma idiomática
- Admin fica sem `verbose_name` adequado
- Sem controle formal do lifecycle do app

**Nota:** `enrollments/apps.py` é criado obrigatoriamente pelo Task 2 (P0).
Para os demais apps, fazer junto na mesma sessão.

**Tradeoff:** Baixo risco. A única preocupação é garantir que `INSTALLED_APPS` em
`base.py` continua usando `"apps.enrollments"` (não `"apps.enrollments.apps.EnrollmentsConfig"`)
— o Django resolve automaticamente via `default_app_config` no `__init__.py`.

---

#### Task 4: Ativar Celery para geração assíncrona de PDF [ ]

**Problema atual:** Certificate PDF é gerado **de forma síncrona** dentro de um signal
`post_save`. Isso bloqueia o request por vários segundos em cada conclusão de curso.

**Arquivos a modificar:**
- `config/__init__.py` — descomentar `from .celery import app as celery_app`
- `apps/certificates/signals.py` — trocar chamada direta por `.delay()`
- Criar `apps/certificates/tasks.py` — task Celery para geração do PDF

**Fluxo atual (síncrono):**
```
enrollment.save() → signal → generate_certificate_pdf() → bloqueia 2-5s
```

**Fluxo após (assíncrono):**
```
enrollment.save() → signal → generate_certificate_pdf_async.delay() → retorna imediatamente
                                      ↓ (worker Celery)
                               PDF gerado em background
```

**Tradeoff importante:**  
Se o worker Celery não estiver rodando (ex: desenvolvimento sem `celery -A config worker`),
o PDF não é gerado. Precisamos de um fallback síncrono para desenvolvimento
ou documentar que o worker é obrigatório.

**Opção recomendada:** Usar `CELERY_TASK_ALWAYS_EAGER = True` no settings de
development — tasks executam de forma síncrona mas pelo mesmo código path.

---

### P2 — Desejáveis

#### Task 5: Rate limiting em endpoints sensíveis [ ]

**Endpoints críticos:**
- `POST /api/auth/token/` — brute-force de senhas
- `POST /api/payments/create-intent/` — abuso de Stripe (custos)

**Implementação:** `UserRateThrottle` / `AnonRateThrottle` do DRF.
Redis já está configurado — sem dependência extra.

---

#### Task 6: Validação de rating exige curso concluído [ ]

**Problema atual:** `EnrollmentUpdateSerializer` exige ao menos 1 aula concluída para review,
mas não exige que o curso esteja 100% concluído para dar rating.

**Regra de negócio correta:** Rating só disponível quando `enrollment.completed = True`.

---

## Progresso

| # | Task | Status | Commits |
|---|------|--------|---------|
| P0.1 | Validação de pagamento na matrícula | ✅ Done | `7c863db` |
| P0.2 | Signal de conclusão automática | ✅ Done | `c2656eb` |
| P1.3 | AppConfig para todos os apps | ✅ Done | `7dde9ff` |
| P1.4 | Ativar Celery + PDF assíncrono | ✅ Done | `3758693` |
| P2.5 | Rate limiting | ✅ Done | `bfcd961` |
| P2.6 | Validação de rating | ✅ Done | `f64ebe8` |

---

## Decisões Técnicas

### Por que não usar `perform_create()` para o check de pagamento?

`perform_create()` não tem como retornar uma Response customizada — só lança exceptions.
Lançar `PermissionDenied` retornaria 403 (semântica errada). Lançar `ValidationError` retornaria 400
(também errado). A única forma de retornar 402 de forma limpa é overridar `create()`.

### Por que signal para conclusão de curso e não lógica no serializer?

O serializer `LessonProgressSerializer.update()` só cobre updates via API.
Um signal cobre qualquer save via ORM — mais robusto para scripts, fixtures e testes.
Padrão já estabelecido no projeto: `certificates/signals.py` usa o mesmo approach.

### Por que não mover o check de pagamento para o webhook do Stripe?

O webhook já cria a matrícula automaticamente após `payment_intent.succeeded`.
O check na view previne criação manual via API (bypass do checkout).
Os dois mecanismos são complementares, não alternativos.

---

## Impacto em Testes Existentes

| Teste | Impacto | Ação |
|-------|---------|------|
| `test_create_enrollment_sets_user_to_current` | `CourseFactory()` gera preço > 0, vai retornar 402 | Trocar para `CourseFactory(free=True)` |
| `test_cannot_enroll_twice_in_same_course` | Usa `{"course": ...}` (campo inválido), retorna 400 por falha de serializer antes do check de pagamento | Sem mudança necessária |
| Todos os `EnrollmentFactory` direto no ORM | Não passam pela view, não são afetados | Nenhuma ação |
