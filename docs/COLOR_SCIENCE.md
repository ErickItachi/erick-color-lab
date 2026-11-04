# COLOR SCIENCE — ERICK COLOR LAB / CINÉRA VOL. 01

Este documento descreve exatamente o que o motor faz, com as fórmulas, as fontes de cada constante técnica e como cada etapa foi verificada.

## 1. Princípio: técnico ≠ criativo

| Camada | Onde | Natureza | Pode mudar por look? |
|---|---|---|---|
| **Entrada técnica** | `transforms/profiles.py`, `profiles/*/*.json` | decodificação Log, primárias, compressão de gamut | não |
| **Criativa** | `creative/operators.py`, `looks/*/*.json` | o look | sim — é o look |
| **Rendering técnico** | `transforms/rendering.py`, `profiles/output/*.json` | cena → display Rec.709 | não (compartilhado por todos os looks) |

Nenhuma transformação técnica é aplicada duas vezes. Cada arquivo exportado declara entrada e saída no cabeçalho.

```
camera_log      sinal ─decode─► gamut da câmera ─CAT02─► AP1 ─RGC─► cena AP1 ─LOOK─► rendering ─► Rec.709 BT.1886
display_rec709  Rec.709 ─rendering⁻¹ (exato)─► cena AP1 ─LOOK─► rendering ─► Rec.709 BT.1886
working_space   ACEScct ─decode─► cena AP1 ─LOOK─► encode ─► ACEScct       (Creative Only / LMT)
```

## 2. Espaços e constantes técnicas (nada inventado)

| Item | Fonte | Implementação | Verificação |
|---|---|---|---|
| S-Log3 | Sony, *Technical Summary for S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3* | colour-science | 0/18/90 % → 95/420/598 CV; câmera→ACES vs OpenColorIO `SONY_SLOG3-SGAMUT3(.CINE)_to_ACES2065-1` (erro rel. < 2e-3, arredondamento das matrizes publicadas) |
| S-Gamut3, S-Gamut3.Cine | idem | colour-science | idem |
| Canon Log 3 (v1.2) | Canon, *Canon Log Gamma Curves* (constantes v1.2) | colour-science | curva vs OCIO `CURVE - CANON_CLOG3_to_LINEAR`; câmera→ACES vs `CANON_CLOG3-CGAMUT_to_ACES2065-1` (< 5e-4) |
| Cinema Gamut | Canon | colour-science | idem |
| Apple Log | Apple, *Apple Log Profile White Paper* (2023) | colour-science | curva vs OCIO `CURVE - APPLE_LOG_to_LINEAR`; câmera→ACES vs `APPLE_LOG_to_ACES2065-1` (< 1e-4) |
| BT.2020 | ITU-R BT.2020-2 | colour-science | via Apple Log acima |
| ACEScct / AP1 (ACEScg) | Academy S-2016-001 / S-2014-004 | colour-science | vs OCIO `CURVE - ACEScct-LOG_to_LINEAR` |
| Rec.709 + BT.1886 (γ 2.4, Lb = 0) | ITU-R BT.709-6, BT.1886 | `transfer.py` | vs OCIO `DISPLAY - CIE-XYZ-D65_to_REC.1886-REC.709` (< 2e-5) |
| Reference Gamut Compression | Academy, ACES 1.3 RGC (limiares 0.815/0.803/0.880, limites 1.147/1.264/1.312, potência 1.2) | `gamut/compression.py` | vs OCIO `ACES-LMT - ACES 1.3 Reference Gamut Compression` (< 2e-6); inversa analítica (< 1e-9) |
| Oklab | B. Ottosson (2020), matrizes publicadas | `colorspaces.py` | vs `colour.XYZ_to_Oklab` |
| ColorChecker 24 (2014) | X-Rite, dados em colour-science | `imaging/synthetic.py` | patch neutro 5 com Y ≈ 0.19 |

**Adaptação cromática.** Câmeras e Rec.709 são D65; AP1 usa o branco ACES. O motor usa CAT02 nas duas direções (D65→ACES e ACES→D65), então a adaptação se cancela para neutros em todo caminho câmera→Rec.709 (testado: 18 % cinza de cada câmera → mesmo cinza neutro no display). As matrizes publicadas de Sony e Canon correspondem a CAT02 e as da Apple a Bradford; os testes comparam cada câmera com a adaptação correspondente.

**Faixa de sinal (data levels).** As fórmulas Log são definidas sobre code values em escala cheia (CV/1023). Resolve (clip Data Levels = Auto/Video) e Premiere entregam ao LUT o sinal de vídeo normalizado (CV 64 → 0.0, CV 940 → 1.0). Os perfis de câmera usam `"range": "video"`: `CV/1023 = (64 + 876·v)/1023`. O modo `"full"` existe no motor para clips interpretados como Full. Ver `COMPATIBILITY.md`.

## 3. CINÉRA Neutral Rendering v1 (técnico)

`profiles/output/cinera_neutral_rendering_rec709.json`

1. **Tone scale** por canal (forma inspirada no tonescale aberto do ACES 2.0 de D. Siragusano; parâmetros próprios):

   ```
   h(x) = (x / (x + s0))^p          p = 1.18 (contraste)
   t(h) = h² / (h + toe)            toe = 0.012 (pretos ricos sem clip duro)
   f(x) = min(t(h(x)) / t(h(W)), 1) W = 0.18·2^6.5 (+6.5 stops → branco do display)
   s0 resolvido para f(0.18) = 0.115 (cinza 18 % → 0.406 codificado)
   ```
   Aplicado de forma ímpar, f(−x) = −f(x). Inversa em forma fechada. O highlight roll-off é intrínseco (inclinação → 0 em W).
2. **AP1 → Rec.709** (linear, CAT02).
3. **Compressão de gamut no display** (mesmo algoritmo do RGC). Para fontes de câmera/working space, os limites são derivados das matrizes de modo que a fronteira AP1 inteira caia dentro do Rec.709 (limiar 0.85). Para fontes Rec.709 é usado um par suave (limiar 0.95, limite 1.05) cuja inversa é exata e bem condicionada.
4. Clip [0, 1] e **BT.1886 inversa** (γ 1/2.4).

Para o perfil Rec.709, `rendering.inverse` mapeia o vídeo Rec.709 de volta para a cena; com um look neutro, o LUT Rec.709 é a identidade (erro máximo 3e-7, testado).

## 4. Operadores criativos (parâmetros dos arquivos de look)

Entrada e saída: cena linear AP1. Ordem fixa.

### A. Linear (AP1)
| Parâmetro | Matemática |
|---|---|
| `exposure` | `x·2^e` |
| `white_balance.warmth / tint` | ganhos `(2^(w/2), 2^tint, 2^(−w/2))` normalizados para luminância unitária (não altera exposição) |
| `black_offset` < 0 | densidade de luminância: `Y' = Y²/(Y+d)`, aplicada como escala comum `k = Y'/Y` (preserva matiz e saturação) |
| `black_offset` > 0 | lift neutro (matte) `x + o` |
| `color_matrix` | 3×3 em AP1 linear; linhas devem somar 1 (neutros preservados — validado ao carregar) |

### B. ACEScct (log)
| Parâmetro | Matemática |
|---|---|
| `contrast.amount / pivot` | `y = pivot + (x − pivot)·amount` (pivot 0.4136 = cinza 18 %) |
| `contrast.hue_preservation` | mistura entre contraste por canal (0) e contraste de luminância com razões RGB constantes (1) |
| `lift_gamma_gain` | `v = (x−b)/(w−b)`, `y = gain·(v + lift·(1−v))`, `y^(1/gamma)`; b = ACEScct(0), w = ACEScct(0.18·2^6.5) |
| `tonal_balance` | offsets RGB por faixa (sombras/médios/altas, máscaras smoothstep em stops relativos ao cinza); `preserve_luma` remove o componente de luminância; atenuado na pele por `skin.protect`; some suavemente no preto (−10…−6 stops) — sombras tingidas, preto neutro |
| `curves` | curvas monotônicas Fritsch–Carlson (sem overshoot/reversão); fora do intervalo: inclinação 1 |
| `highlight_compression` | ombro no canal máximo em ACEScct: `m' = t + (m−t)/(1 + s·(m−t))`, aplicado como escala comum (preserva matiz) |

### C. Oklab (perceptual)
| Parâmetro | Matemática |
|---|---|
| `color_separation` | `Δh = −A·sin(2(h − eixo))` — puxa matizes para o eixo quente/frio |
| `hue_vs_hue / sat / lum` | curvas periódicas Catmull-Rom sobre o matiz Oklab; lum é multiplicador de luminância relativa (`L' = L·m^(1/3)`) |
| `saturation` | multiplicadores global / sombras / altas (máscaras em stops); limite suave de croma em `C/L` com ombro `tanh` (`chroma_knee` → `chroma_limit`) |
| `skin.protect` | máscara de pele (gaussiana em matiz centrada em `hue_center`, banda em C/L) reduz hue/sat/lum e tonal balance sobre a pele |
| `skin.pull` | puxa o matiz da pele para `hue_center` (consistência entre iluminações) |

Referência de pele: os patches *dark skin* e *light skin* do ColorChecker têm matiz Oklab 38–42°, C/L ≈ 0.10–0.12.

**Proteções de domínio** (constantes de engenharia, documentadas no código):
- `L_FLOOR` = L Oklab de −6 stops — mantém a razão C/L bem condicionada perto do preto.
- `DEEP_SHADOW_FADE` (−9 … −4.5 stops) — operações perceptuais desaparecem suavemente no ruído do preto (luminância monotônica).
- `HUE_CHROMA_FADE` (C 0 … 0.03) — operações chaveadas por matiz somem quando o matiz não é definido.
- máscara de validade LMS — perto da borda do domínio de cones (cores não físicas) as operações perceptuais desligam.
- RGC aplicado na entrada de câmera — os operadores criativos nunca recebem excursões de gamut extremas.

Um look neutro é exatamente a identidade (testado).

## 5. Baking

- Lattice 33³ e 65³, ordem `.cube` com vermelho variando mais rápido, `DOMAIN_MIN 0 0 0` / `DOMAIN_MAX 1 1 1`, 6 casas decimais, cabeçalho ASCII.
- Saída limitada a [0, 1].
- Cada arquivo leva no cabeçalho: coleção, look, versão, fingerprint SHA-256 dos parâmetros, formato, entrada, saída e rendering.
- Reprodutível bit a bit: o `MANIFEST.json` guarda o SHA-256 de cada arquivo.

## 6. Validação e tolerâncias

`scripts/validate_luts.py` reimporta cada arquivo do disco (leitor estrito) e compara com o pipeline analítico.

| Verificação | Critério |
|---|---|
| Integridade | tamanho, nº de linhas, valores finitos em [0, 1], domínio 0..1 |
| Precisão nos nós | erro máx. ≤ 1e-6 (quantização 6 casas = 5e-7) |
| Interpolação (tetraédrica; trilinear reportada) | CIEDE2000 no display: média ≤ 0.50 / p99 ≤ 2.0 (33³); média ≤ 0.20 / p99 ≤ 1.0 (65³) — 20 000 pontos aleatórios + 5 000 centros de célula |
| Continuidade | resposta neutra monotônica (0 reversões) |
| Banding | rampas construídas na cena (neutra, pele, céu; −9…+7 stops): ganho local ≤ 6 codes/code, 0 reversões. Creative Only medido no próprio domínio ACEScct |
| Clipping | % de nós em 0/1 (informativo) + relatório em cenas |
| Gamut | % fora de [0, 1] antes do clip final (informativo) |
| Pele | estabilidade de matiz do pipeline exato em −2/0/+2 EV ≤ 8°; fidelidade LUT vs pipeline nos patches de pele ≤ 2.0 ΔE00 (33³) / ≤ 1.0 (65³) |
| Manifesto | SHA-256 igual ao do build |

**Resultado atual: 180/180 aprovados.** Pior caso por resolução: média ΔE00 0.069 / p99 0.63 (33³) e 0.019 / 0.21 (65³). O ΔE máximo (até ~22) ocorre apenas em cantos extremos e não físicos do cubo (por exemplo, sinal S-Log3 com azul muito alto e vermelho/verde muito baixos).

**Histórico honesto das revisões de critério nesta fase**
1. A verificação de pele começou como "espalhamento de matiz no LUT ≤ 8°". O ângulo de matiz é mal condicionado para patches de baixo croma, então passou a ser avaliada no pipeline exato (propriedade do look). A fidelidade do arquivo passou a ser medida por ΔE00 LUT vs pipeline (propriedade do arquivo).
2. O limite de ΔE de pele foi introduzido em 1.0 para todos os tamanhos; até o look neutro chega a 0.90 em Canon Log 3 33³ (o toe linear longo do Canon Log 3 deixa uma célula 33³ cobrindo ~3 stops de sombra). Foi alinhado às tolerâncias de interpolação por tamanho (2.0 em 33³, 1.0 em 65³).
3. As rampas de banding iniciais escalavam code values Log (cores não físicas) e foram substituídas por rampas construídas na cena.

Os demais limites não foram alterados. Os problemas encontrados pela validação foram corrigidos no motor ou nos looks (ver `CHANGELOG.md`), não com tolerâncias mais frouxas.

## 7. Limitações conhecidas

- Não há teste em host real (Resolve/Premiere) nem com footage real de câmera neste ambiente.
- Convenção de faixa do Apple Log: tratada como CV/1023 (cinza 18 % ≈ CV 500), consistente com a curva publicada e com tabelas de code values de terceiros. Falta confirmar com o texto do white paper e com arquivos reais do iPhone.
- O tone scale por canal desloca levemente o matiz com a exposição (comportamento "filme"); a pele fica ≤ 8° em ±2 EV (medido).
- Valores de câmera acima de CV 940 (super-white) são cortados pelo domínio 0..1 do `.cube`.
