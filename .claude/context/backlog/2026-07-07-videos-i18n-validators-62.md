# Slice: fix i18n-broken validator messages (#62)

**Data:** 2026-07-07
**Branch:** `fix/videos-i18n-validators-62` (a partir de `main`) → **PR #226 (squash → `main`, commit `0533fb0`)**
**Layer:** `02-models.md`
**Status:** mergeado + **DEPLOYADO + VALIDADO EM PROD (2026-07-07)**.

## Contexto

`apps/videos/validators.py` construía mensagens de erro interpolando f-strings *antes* de passar
pro `gettext_lazy` (`_()`), o que anula a tradução lazy (o catálogo nunca vê um msgid estável, só o
texto em inglês já resolvido com os valores em runtime embutidos). Duas mensagens também perdiam o
separador por concatenação implícita de literais adjacentes:
- `"...file type." "Make sure..."` → renderizava `"...file type.Make sure..."` (sem espaço).
- `f"Invalid file extension" f'Allowed extensions: ...'` → renderizava
  `"Invalid file extensionAllowed extensions: ..."` (sem separador nenhum).

## Fix (#62)

- `validate_video_size` — template estático `"Very large file: %(current_size)sMB. Maximum size
  allowed: %(max_size)sMB (2GB)."` + valores via `ValidationError(..., params={...})`.
- `validate_video_mimetype` — espaço corrigido em `mime_detection_failed`; `invalid_mimetype`
  convertido pra `%(mime_type)s`/`%(allowed_types)s` + `params=`.
- `validate_video_extension` (`FileExtensionValidator`) — template estático `"Invalid file
  extension. Allowed extensions: %(allowed_extensions)s."`, reaproveitando o `params` que o
  próprio `FileExtensionValidator.__call__` do Django já injeta (`allowed_extensions` é a lista
  minúscula unida por vírgula).

## TDD

- **RED:** `test_mime_detection_failure_message_has_separator` e
  `test_invalid_extension_message_has_separator` falharam confirmando os dois bugs de texto
  (`"type.Make sure"` e `"extensionAllowed"`).
- **GREEN:** 5 testes novos/estendidos em `test_validators.py` (separadores + substituição real de
  `current_size`/`max_size`/`mime_type`/`allowed_types`/`allowed_extensions`), lendo
  `exc_info.value.messages[0]` (mensagem já substituída) em vez de `.message` (template bruto).

## Verificação

- `pytest apps/videos/`: **105 passed**. flake8/black/isort limpos.
- **Migração necessária** (inesperado no início): mudar o `message=` do `FileExtensionValidator`
  usado como validator do campo `Video.file` altera o estado serializado da migração — Django gerou
  `apps/videos/migrations/0007_alter_video_file.py`. `sqlmigrate videos 0007` confirmou **no-op**
  no schema (só metadado do validator, nenhuma coluna/constraint muda).
- CI pegou isso: o gate `makemigrations --check --dry-run` falhou no PR #226 antes da migração ser
  gerada e incluída (via `git commit --amend` + `git push --force-with-lease`, branch ainda não
  mergeada). Depois: lint+migration-drift `pass` (40s), suíte PostgreSQL `pass` (5m20s).
- **code-reviewer:** **APPROVE WITH NITS** — verificou a cadeia completa de substituição
  (`ValidationError.messages` faz `message %= params`; DRF's `get_error_detail` também substitui
  antes de chegar no end user; `FileExtensionValidator` do Django injeta `allowed_extensions`
  corretamente). 1 nit aplicado: teste de `validate_video_size` só provava o template bruto, não a
  substituição real — adicionado `test_error_message_substitutes_computed_sizes`.

## Deploy

- **Migração metadata-only** — precisou de `docker compose exec backend python manage.py migrate`
  + `restart backend`.
- **Validado em prod (2026-07-07):** `showmigrations videos` mostra `[X] 0007_alter_video_file`;
  health `200`; shell do container confirmou as 3 mensagens corrigidas rodando os validators
  diretamente contra inputs inválidos (extensão, tamanho, mimetype) — todas com separador e
  substituição corretos.

## Notas

- Minor residual da auditoria original baixa **5 → 4** (restam #24, #151, #180, #183).
- Gotcha novo: mudar o `message=` de um validator usado em `Field(validators=[...])` conta como
  mudança de estado de migração pro Django, mesmo sem alterar schema — vale lembrar antes de
  qualquer próximo fix de mensagem de validator.
