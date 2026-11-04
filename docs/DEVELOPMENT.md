# Desenvolvimento — ERICK COLOR LAB

## Ambiente

```bash
python -m pip install -e ".[dev]"
```

Python ≥ 3.10. Dependências: numpy, colour-science, Pillow, matplotlib; para validação/testes: OpenColorIO ≥ 2.3 e pytest.

## Fluxo de trabalho

| Tarefa | Comando |
|---|---|
| Testes | `python -m pytest` |
| Gerar todos os LUTs | `python scripts/build_luts.py` |
| Gerar um look/perfil | `python scripts/build_luts.py --looks 01-signature --profiles slog3_sgamut3cine --sizes 65` |
| Validar | `python scripts/validate_luts.py` (aceita os mesmos filtros) |
| Prévias + página HTML | `python scripts/generate_previews.py` |
| Testar com material próprio | `python scripts/generate_previews.py --media test-media/` (resultado em `test-media/_renders`, nunca versionado) |
| Pacote comercial local | `python scripts/package_collection.py --zip` (cria `release/`, ignorado pelo git; não publica nada) |

## Editar um look (fluxo não destrutivo)

1. Edite `looks/<look>/<variação>.json`. Chaves desconhecidas são rejeitadas (sem erro silencioso de digitação); valores omitidos assumem o neutro (`NEUTRAL_PARAMETERS` em `creative/look.py`, com a unidade e o significado de cada parâmetro).
2. Suba `version` (semver) do arquivo.
3. Rode `build_luts.py`, depois `validate_luts.py`, depois `generate_previews.py`.
4. Faça commit do JSON, do `MANIFEST.json`, dos relatórios e das prévias.

O futuro aplicativo ERICK COLOR LAB lerá e escreverá estes mesmos arquivos. O schema é `erick-color-lab/look@1`.

## Novo look ou nova coleção

- Novo look: crie `looks/06-<nome>/standard.json` (copie um existente) e adicione o id em `brand.py → COLLECTIONS`.
- Nova coleção (por exemplo CINÉRA VOL. 02): nova entrada em `COLLECTIONS` com o próprio `id`, `name`, `version` e lista de looks. A pasta de export é `exports/<id>/`.

## Novo perfil de câmera

Ver `COMPATIBILITY.md → Arquitetura para novos perfis`. Regra: nenhum perfil entra sem um teste contra uma referência independente ou valores publicados.

## Regras de engenharia

- Constantes técnicas só de fonte publicada, via colour-science quando disponível; parâmetros de design ficam documentados como tal.
- Separação técnico/criativo: a entrada técnica fica no perfil, o look no JSON, o rendering compartilhado em `profiles/output/`.
- Problema encontrado pela validação se resolve no motor ou no look, nunca afrouxando tolerância. Uma revisão de critério precisa ser justificada e registrada em `COLOR_SCIENCE.md §6`.
- Material de terceiros nunca entra no repositório (`.gitignore` bloqueia `private/`, `*FJR*`, `*La Creme*`, `.drx`, `.xmp`, `.dng`).
- Os `.cube` são artefatos de build (ignorados). O `MANIFEST.json` garante reprodutibilidade bit a bit.

## Branches

O desenvolvimento desta fase foi feito na branch `claude/confident-ptolemy-z0wu1k` (branch obrigatória do ambiente de execução). A branch `feat/erick-color-vol-01` pedida originalmente pode ser criada a partir dela.
