# Slice: fix broken venv console-script shebangs (#183)

**Data:** 2026-07-08
**Branch:** nenhuma — `venv/` é gitignored, sem diff de repositório possível.
**Layer:** nenhuma (ambiente de dev local, fora do mapa de camadas da auditoria)
**Status:** **RESOLVIDO LOCALMENTE + FECHADO NO GITHUB** (comentário de evidência, sem PR).

## Contexto

Os console-scripts da venv (`venv/bin/flake8`, `black`, `isort`, `pytest`, entre outros) tinham
um shebang antigo apontando pra `/home/bruno_teixeira/wss-backend-v0/venv/bin/python3` — caminho
que não existe mais desde que o projeto foi movido pra `~/projects/wss-backend-v0`. Rodar as
ferramentas diretamente (`flake8 apps/`) falhava; o workaround usado a sessão toda (e em toda a
remediação desta auditoria) foi `python -m <tool>`. Impacto era só ergonomia de dev local — CI
não era afetado (instala seu próprio ambiente).

## Por que não há PR

`venv/` está no `.gitignore` (confirmado). Não existe nenhum arquivo rastreado pelo git afetado
por este fix — é inteiramente uma correção da máquina local do Bruno, sem branch/commit/PR/deploy
possível. Segue o mesmo padrão de fechamento por evidência já usado pra #59/#33.

## Fix

Reinstalados 18 pacotes via `pip install --force-reinstall --no-deps`, cada um pinado
**exatamente** na versão já instalada (cross-checado contra `backend/requirements.txt` antes —
zero drift de versão): `black==24.8.0`, `celery==5.4.0`, `chardet==7.1.0`, `coverage==7.13.4`,
`Django==5.2`, `Faker==40.4.0`, `flake8==7.1.1`, `gunicorn==23.0.0`, `isort==5.13.2`,
`jsonschema==4.26.0`, `charset-normalizer==3.4.7`, `pip==22.0.2`, `pycodestyle==2.12.1`,
`pyflakes==3.2.0`, `pytest==8.3.2`, `python-slugify==8.0.4`, `sqlparse==0.5.5`,
`jmespath==1.1.0`.

O mapeamento script→pacote foi construído via `importlib.metadata` (varrendo `entry_points` de
todas as distribuições instaladas em busca de cada `console_scripts` quebrado), rodado através do
interpretador da venv (`venv/bin/python3`, que nunca foi afetado — só os wrapper scripts tinham o
shebang quebrado, não o próprio `python3`, que é um symlink pro `/usr/bin/python3`).

`--no-deps` garantiu que nenhuma dependência transitiva fosse tocada; `--force-reinstall` só
regenerou os wrapper scripts com o shebang correto, sem mudar nenhuma versão.

## Verificação

- Shebangs confirmados corrigidos: `#!/home/bruno_teixeira/projects/wss-backend-v0/venv/bin/python3`
  (era `/home/bruno_teixeira/wss-backend-v0/...`, caminho antigo).
- `flake8`, `black --check`, `isort --check` rodados **diretamente** (sem `python -m`) em
  `apps/ config/`: limpos.
- `pytest` rodado **diretamente**: suíte completa, **596 passed** (~3m27s).
- Nenhuma versão de pacote mudou (confirmado contra `requirements.txt` antes de reinstalar).

## Deploy

N/A — mudança de ambiente de dev local, sem nenhum artefato de repositório, sem impacto em
prod/CI.

## Notas

- **🎉 Fecha os Minor restantes da auditoria original 2026-06: 1 → 0.** Todos os 81 findings
  originais (18 Blocking + 42 Major + os Minor rastreados) estão resolvidos, deployados e
  validados (ou fechados como decisão documentada). Restam só os 2 achados de follow-up
  (#220, #223), que nunca fizeram parte da contagem original — ver `00-plan.md`.
- O workaround `python -m <tool>` não é mais necessário localmente; os comandos do `CLAUDE.md`
  (`flake8 apps/ && black apps/ && isort apps/`) voltam a funcionar como escrito.
