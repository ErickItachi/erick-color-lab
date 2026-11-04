# ERICK COLOR LAB

**Motor de color science e ferramenta de criação de LUTs da Erick Filmes.**
Com ele é produzida a linha de produtos **CINÉRA — The Cinematic Color Collection** (By Erick Filmes).

| | |
|---|---|
| **ERICK COLOR LAB** | o software: motor de cor, arquivos editáveis dos looks, baking de `.cube`, validação, prévias |
| **CINÉRA** | a marca dos LUTs. Primeira edição: **CINÉRA VOL. 01** |

> Fase 01: núcleo de color science + coleção CINÉRA VOL. 01. O aplicativo ERICK COLOR LAB (interface) ainda **não** existe — ele será construído sobre estes mesmos arquivos de parâmetros.

---

## Status da Fase 01

| Item | Estado |
|---|---|
| Motor de color science (Python) | ✅ implementado — `color-engine/erick_color_lab/` |
| 5 looks × 3 variações (Standard / Soft / Rich) = 15 variantes editáveis | ✅ `looks/*/{standard,soft,rich}.json` |
| Perfis: Rec.709, S-Log3/S-Gamut3.Cine, S-Log3/S-Gamut3, Apple Log/BT.2020, Canon Log 3/Cinema Gamut, ACEScct (Creative Only) | ✅ `profiles/` |
| Exportação `.cube` 33³ e 65³ — 180 arquivos | ✅ gerados por `scripts/build_luts.py` (checksums em `exports/cinera-vol-01/MANIFEST.json`) |
| Validação por reimportação de cada arquivo | ✅ **180/180 aprovados** — `previews/reports/validation_report.md` |
| Testes automatizados (curvas Log e câmeras vs OpenColorIO, identidades, formato `.cube`) | ✅ 62 testes — `pytest` |
| Prévias (antes/depois, Soft/Standard/Rich, curvas, histogramas, clipping, página HTML) | ✅ `previews/` (cenas sintéticas) |
| Teste em DaVinci Resolve / Premiere Pro reais | ⏳ **pendente** — não executado neste ambiente (ver `docs/COMPATIBILITY.md`) |
| Teste com footage real de câmera | ⏳ **pendente** — use `scripts/generate_previews.py --media` com material próprio |

## Início rápido

```bash
pip install -e ".[dev]"        # numpy, colour-science, Pillow, matplotlib, OpenColorIO, pytest
```

```bash
python -m pytest               # 62 testes de color science e formato
```

```bash
python scripts/build_luts.py   # gera os 180 .cube em exports/cinera-vol-01/
```

```bash
python scripts/validate_luts.py    # reimporta e valida cada arquivo
```

```bash
python scripts/generate_previews.py   # prévias + previews/index.html
```

```bash
python scripts/package_collection.py --zip   # monta o pacote comercial local (não publica nada)
```

## Estrutura

```
erick-color-lab/
├── color-engine/erick_color_lab/   motor (pacote Python)
│   ├── transforms/    funções de transferência, espaços de cor, perfis, rendering
│   ├── curves/        curvas monotônicas, curvas periódicas de matiz, tone scale
│   ├── gamut/         compressão de gamut (ACES 1.3 RGC)
│   ├── creative/      operadores criativos + leitura dos arquivos de look
│   ├── interpolation/ interpolação trilinear e tetraédrica
│   ├── lut_baking/    escrita/leitura .cube
│   ├── validation/    verificações técnicas
│   └── imaging/       cenas de teste sintéticas
├── looks/              01-signature … 05-romance  (standard/soft/rich .json — EDITÁVEIS)
├── profiles/           rec709, sony, apple, canon, aces, output (rendering)
├── exports/cinera-vol-01/   rec709, sony-slog3, apple-log, canon-log3, creative-only (+ MANIFEST.json)
├── previews/           before-after, contact-sheets, curves, reports, index.html
├── tests/              color-science, lut-validation, image-tests
├── scripts/            build_luts.py, validate_luts.py, generate_previews.py, package_collection.py
└── docs/               COLOR_SCIENCE, LOOKS, COMPATIBILITY, INSTALLATION, DEVELOPMENT, REFERENCE_STUDY
```

Adaptação da estrutura pedida: `color-engine/` contém o pacote importável `erick_color_lab` (nomes com hífen não são importáveis em Python); `lut-baking` virou `lut_baking`; foram acrescentados `creative/`, `validation/` e `imaging/`.

## Nomenclatura dos arquivos

```
CINERA_<NN>_<LOOK>_<VARIAÇÃO>_<ENTRADA>_TO_<SAÍDA>_<TAMANHO>.cube
CINERA_01_SIGNATURE_STANDARD_SLOG3_SGAMUT3CINE_TO_REC709_65.cube
```

O sufixo `_33` / `_65` evita colisão de nomes entre as duas resoluções.

## Documentação

- [`docs/COLOR_SCIENCE.md`](docs/COLOR_SCIENCE.md) — pipeline, matemática de cada operador, referências, validação e tolerâncias
- [`docs/LOOKS.md`](docs/LOOKS.md) — os cinco looks, variações e parâmetros
- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) — entrada/saída exata de cada arquivo, o que foi e o que não foi verificado
- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) — DaVinci Resolve, Premiere Pro, Final Cut Pro
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — como editar looks, adicionar perfis, reproduzir builds
- [`docs/REFERENCE_STUDY.md`](docs/REFERENCE_STUDY.md) — estudo de referência (organização de pacote/interoperabilidade; nenhum dado de terceiros)
- [`CHANGELOG.md`](CHANGELOG.md) · [`LICENSE.md`](LICENSE.md)

## Originalidade e material de terceiros

Todos os looks foram criados a partir de parâmetros matemáticos próprios (arquivos em `looks/`). Nenhuma tabela de LUT de terceiros foi lida, usada como ponto de partida ou aproximada. Pacotes de terceiros estudados como referência ficam fora do repositório (bloqueados em `.gitignore`) e fora dos pacotes comerciais (verificado por `scripts/package_collection.py`).

> ⚠️ Este repositório é **público**. Os arquivos `.cube` comerciais não são versionados (são reproduzíveis com `build_luts.py`), mas os parâmetros dos looks estão visíveis. Recomenda-se tornar o repositório privado antes da comercialização.
