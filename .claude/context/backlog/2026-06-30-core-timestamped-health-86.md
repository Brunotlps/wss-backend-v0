# Slice: Core TimeStampedModel + health check coverage (#86)

**Data:** 2026-06-30
**Branch:** `test/core-timestamped-health-86` (a partir de `main`) → **PR #169 (squash → `main`)**
**Layer:** `07-tests.md` · **Phase 3 (hardening & hygiene)** · 5º slice da camada de testes (após #82, #50, #17, #34/#35) — **último Major de `07-tests`**
**Status:** mergeado em `main` (commit `79214e0`), **validado por CI**. Sem deploy (test-only).

## Contexto

`TimeStampedModel` é abstrato e herdado por **todo** model do projeto, mas nada exercitava seu
contrato — `models.py` mostrava "100%" só porque a declaração de campos roda no import. Uma regressão
trocando `auto_now_add`/`auto_now` corromperia timestamps em todo o sistema com o CI verde. Além disso
o `health_check` declara `@api_view(["GET","HEAD"])` mas só GET/`status=="ok"` eram testados (HEAD e as
chaves `message`/`version` sem asserção).

Mudança **test-only** — nenhum runtime alterado → **sem deploy e sem smoke de prod**; CI é a validação.

## Lacunas cobertas

- **`TimeStampedModel`** (`tests/test_models.py`, novo) — contrato via subclass concreto (Course/factory,
  pois o base é abstrato): timestamps setados no create; após `save()` posterior, `created_at`
  **imutável** e `updated_at` **avança** (`>` estrito). Determinístico: `django.utils.timezone.now`
  mockado em dois instantes distintos (create, depois update) — o avanço é assertado sem depender da
  resolução do relógio entre dois saves rápidos, **sem dependência nova** (só `unittest.mock`).
- **`health_check`** (`tests/test_views.py`) — método **HEAD** → 200 (lock real: método não permitido
  daria 405); contrato de shape: chaves == `{status, message, version}`, `status=="ok"`, `message`
  exato, `version` str não-vazia (não fixa `"1.0.0"` p/ não virar tripwire de bump de versão).

## Verificação

- **RED (baseline):** nenhum teste instanciava subclass concreto do `TimeStampedModel` (cobertura de
  `models.py` enganosa); HEAD e `message`/`version` do health sem asserção.
- **GREEN:** `pytest apps/core/`: **23 passed**. flake8/black/isort limpos. Migration drift: nenhum.
- **code-reviewer (diff final):** **APPROVE WITH NITS**, 0 Blocking / 0 Major. Confirmou: HEAD é lock
  comportamental real; Course é stand-in fiel (slug gen roda **antes** do `super().save()`, não toca os
  timestamps; `is_published=True` inócuo pois `save()` não chama `full_clean`); shape lock apropriado.
  O único nit acionável (garantia do `updated_at >` era temporal, não semântica — mediu ~39% de colisão
  de microssegundo entre dois `now()` adjacentes, mas o roundtrip do ORM salvava na prática, 30/30) foi
  **endurecido** para determinístico via mock de `timezone.now`.
- **CI (PR #169):** verde.

## Testes adicionados

- `tests/test_models.py` (novo): `TestTimeStampedModel`
  (`test_timestamps_populated_on_create`, `test_created_at_is_immutable_and_updated_at_advances_on_save`).
- `tests/test_views.py`: `test_health_check_head_returns_200`, `test_health_check_response_shape`.

## Done-criteria (`07-tests`)
- [x] teste comportamental do `TimeStampedModel` (created_at write-once, updated_at avança) via model
      concreto + factory-boy
- [x] HEAD no `health_check` + shape da resposta assertado
- [x] nenhum teste tautológico/afirmando comportamento errado
- [x] `pytest` verde sem depender de linhas só-de-import

## Notas

- Sem deploy: test-only, nenhum runtime alterado.
- **`07-tests` quase fechada:** restam só os dois **Minor** — **#26** (`reverse()` em tempo de definição
  de classe em `test_throttling.py` → `reverse_lazy`/fixture) e **#72** (`filter_is_free` true/false sem
  cobertura, courses; + ruído `is_published` no payload público da list). Dá pra fechar num slice rápido
  único. Depois: `08-lint-style` (batch, inclui dirt de `config/`) + videos #60.
