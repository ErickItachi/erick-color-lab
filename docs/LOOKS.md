# CINÉRA VOL. 01 — Os looks

*The Cinematic Color Collection — By Erick Filmes*

Cinco looks, três variações cada. Cada variação é um conjunto completo e independente de parâmetros reais em `looks/<look>/<variação>.json`, editável e versionado. A matemática de cada parâmetro está em `COLOR_SCIENCE.md` §4.

| Look | Intenção |
|---|---|
| **01 SIGNATURE** | A assinatura CINÉRA: contraste cinematográfico equilibrado, pele natural, pretos ricos mas abertos, altas delicadas e saturação contida. Separação quente/frio sutil, verdes levemente puxados para oliva e acalmados. |
| **02 GOLDEN** | Quente, nostálgico e romântico. Altas douradas, tons quentes naturais, sombras quentes com profundidade, transições suaves. Para golden hour e casamentos. |
| **03 OLIVE** | Orgânico e documental. Verdes oliva discretos, cores terrosas, amarelos controlados, contraste natural. |
| **04 BLUE HOUR** | Frio, dramático e elegante. Sombras azuladas, azuis profundos, altas relativamente neutras e pele preservada. |
| **05 ROMANCE** | Suave, delicado e sofisticado. Contraste moderado, altas macias, pele lisonjeira, saturação discreta e um leve matte. |

## Variações

| Variação | Regra de construção (aplicada uma vez; depois cada arquivo é editável à parte) |
|---|---|
| **STANDARD** | a versão principal |
| **SOFT** | ~metade do desvio de contraste −0.01, tintas tonais ×0.75, ombro de altas mais suave (força ×1.3, início −0.02), separação ×0.6, saturação global ×0.95, curvas hue-vs-sat ×0.8, leve matte (+0.0006) |
| **RICH** | desvio de contraste ×1.6 +0.02, pretos mais densos, tintas tonais ×1.3, separação ×1.6, saturação ×1.04, hue-vs-sat ×1.2, hue-vs-hue ×1.15, ombro ×0.85 |

## Parâmetros-chave (valores reais dos arquivos)

| Look | Variação | Contraste | Preserv. matiz | Black offset | Warmth / Tint | Sat. global | Sat. sombras / altas | Separação (°) | Ombro (início / força) | Pele protect / pull |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 Signature | soft | 1.025 | 0.6 | 0.0 | 0.04 / −0.01 | 0.912 | 0.868 / 0.862 | 2.4 | 0.60 / 2.6 | 0.7 / 0.25 |
| 01 Signature | standard | 1.07 | 0.6 | −0.0015 | 0.04 / −0.01 | 0.96 | 0.88 / 0.88 | 4.0 | 0.62 / 2.0 | 0.7 / 0.25 |
| 01 Signature | rich | 1.132 | 0.6 | −0.0032 | 0.04 / −0.01 | 0.998 | 0.88 / 0.88 | 6.4 | 0.62 / 1.7 | 0.7 / 0.25 |
| 02 Golden | soft | 1.015 | 0.85 | 0.0002 | 0.14 / −0.01 | 0.922 | 0.89 / 0.908 | 1.8 | 0.56 / 3.38 | 0.85 / 0.4 |
| 02 Golden | standard | 1.05 | 0.85 | −0.001 | 0.14 / −0.01 | 0.97 | 0.90 / 0.92 | 3.0 | 0.58 / 2.6 | 0.85 / 0.4 |
| 02 Golden | rich | 1.10 | 0.85 | −0.0024 | 0.14 / −0.01 | 1.009 | 0.90 / 0.92 | 4.8 | 0.58 / 2.21 | 0.85 / 0.4 |
| 03 Olive | soft | 1.005 | 0.5 | 0.0004 | 0.03 / 0.03 | 0.874 | 0.835 / 0.828 | 1.2 | 0.60 / 2.08 | 0.65 / 0.2 |
| 03 Olive | standard | 1.03 | 0.5 | −0.0005 | 0.03 / 0.03 | 0.92 | 0.85 / 0.85 | 2.0 | 0.62 / 1.6 | 0.65 / 0.2 |
| 03 Olive | rich | 1.068 | 0.5 | −0.0016 | 0.03 / 0.03 | 0.957 | 0.85 / 0.85 | 3.2 | 0.62 / 1.36 | 0.65 / 0.2 |
| 04 Blue Hour | soft | 1.04 | 0.6 | −0.0001 | −0.14 / 0.0 | 0.884 | 0.912 / 0.77 | 3.0 | 0.61 / 2.34 | 0.75 / 0.25 |
| 04 Blue Hour | standard | 1.10 | 0.6 | −0.0018 | −0.14 / 0.0 | 0.93 | 0.92 / 0.80 | 5.0 | 0.63 / 1.8 | 0.75 / 0.25 |
| 04 Blue Hour | rich | 1.18 | 0.6 | −0.0037 | −0.14 / 0.0 | 0.967 | 0.92 / 0.80 | 8.0 | 0.63 / 1.53 | 0.75 / 0.25 |
| 05 Romance | soft | 1.00 | 0.6 | 0.0008 | 0.06 / −0.03 | 0.855 | 0.835 / 0.828 | 0.9 | 0.54 / 3.9 | 0.6 / 0.3 |
| 05 Romance | standard | 1.02 | 0.6 | 0.0006 | 0.06 / −0.03 | 0.90 | 0.85 / 0.85 | 1.5 | 0.56 / 3.0 | 0.6 / 0.3 |
| 05 Romance | rich | 1.052 | 0.6 | 0.0002 | 0.06 / −0.03 | 0.936 | 0.85 / 0.85 | 2.4 | 0.56 / 2.55 | 0.6 / 0.3 |

Além disso cada arquivo traz `color_matrix`, `tonal_balance` (offsets por faixa), `curves`, `hue_vs_hue`, `hue_vs_sat`, `hue_vs_lum` e `skin.hue_center/hue_width`.

### Tratamento por cor (matiz Oklab: vermelho ≈ 23°, laranja/pele ≈ 40–55°, amarelo ≈ 95°, verde ≈ 140°, ciano ≈ 200°, azul ≈ 250–270°, magenta ≈ 330°)
- **Signature** — verdes −8° (para oliva) e sat ×0.82; amarelos −4°, sat ×0.95; azuis +3°.
- **Golden** — verdes −12° (para amarelo quente), azuis −4° e sat ×0.80; amarelos lum ×1.02.
- **Olive** — verdes −16° e sat ×0.70 (oliva), cianos −10° (para verde), vermelhos +6° (terrosos) e sat ×0.88, amarelos ×0.82.
- **Blue Hour** — verdes +14° (para teal) e sat ×0.75, azuis sat ×1.08 e lum ×0.86 (azuis profundos), magentas −6°.
- **Romance** — azuis +6° (levemente lavanda), rosas/magentas sat ×1.02 e lum ×1.02, verdes e amarelos discretos.

## Medições de comportamento (cenas sintéticas, 65³, S-Log3/S-Gamut3.Cine)

- **Estabilidade da pele** (pipeline exato, −2/0/+2 EV): ≤ 7.8° em todas as 15 variações. O rendering neutro sozinho dá 6.6°.
- **Consistência entre câmeras** (Signature Standard, mesma cena por cada entrada): ΔE00 médio vs S-Log3/S-Gamut3.Cine — S-Gamut3 0.01, Apple Log 0.02, Canon Log 3 0.03, ACEScct 0.04, Rec.709 0.31.
- **Clipping de pretos**: Blue Hour Standard e as variações Rich levam ao preto 2.9–4.5 % dos pixels das cenas sintéticas (que incluem patches a −4 EV). Isso é intencional (pretos profundos); as variações Soft não clipam. Detalhes: `previews/reports/clipping_report.md`.

Prévias: `previews/contact-sheets/`, `previews/before-after/`, `previews/curves/`, `previews/index.html`.

> As prévias usam cenas sintéticas (ColorChecker, proxies de pele, iluminações simuladas). Nenhum teste com fotos ou footage real foi feito nesta fase. Pessoas, casamentos, natureza e ambientes internos reais ainda precisam ser testados com material próprio via `generate_previews.py --media`.
