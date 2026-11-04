# Compatibilidade — CINÉRA VOL. 01

## Formatos de uso

| Formato | Pasta | O arquivo faz | Use quando |
|---|---|---|---|
| **Camera to Rec.709** | `sony-slog3/`, `apple-log/`, `canon-log3/` | conversão técnica da câmera + look + rendering para Rec.709 | o clip está no Log da câmera e você quer o resultado final em Rec.709 em um passo |
| **Rec.709** | `rec709/` | look aplicado a vídeo já em Rec.709 (inversa exata do rendering neutro → look → rendering) | footage gravado em Rec.709 ou já convertido para Rec.709 |
| **Creative Only** | `creative-only/` | só o look, em ACEScct → ACEScct (LMT estilo ACES); **nenhuma** conversão técnica | pipeline gerenciado: CST/IDT da câmera → ACEScct → **LUT** → transformada de saída ACEScct → Rec.709 |

Nunca empilhe um LUT Camera to Rec.709 com outra conversão da câmera (duplicaria a transformação técnica).

## Entrada e saída exatas de cada arquivo

| Token | Entrada | Faixa de sinal esperada | Saída |
|---|---|---|---|
| `REC709_TO_REC709` | Rec.709 primárias, BT.1886 (γ 2.4), D65 | sinal nominal 0..1 (vídeo 64–940) | Rec.709 / BT.1886 / D65, display-referred |
| `SLOG3_SGAMUT3CINE_TO_REC709` | Sony S-Log3 / S-Gamut3.Cine | **vídeo** (CV 64–940 → 0..1); cinza 18 % = CV 420 | idem |
| `SLOG3_SGAMUT3_TO_REC709` | Sony S-Log3 / S-Gamut3 | vídeo | idem |
| `APPLELOG_BT2020_TO_REC709` | Apple Log / BT.2020 (iPhone 15 Pro e posteriores) | vídeo | idem |
| `CLOG3_CINEMAGAMUT_TO_REC709` | Canon Log 3 / Cinema Gamut | vídeo | idem |
| `ACESCCT_TO_ACESCCT` | ACEScct (AP1), ponto flutuante | sem remapeamento | ACEScct (AP1), scene-referred |

Todos os arquivos: `.cube` 3D, `LUT_3D_SIZE` 33 ou 65, `DOMAIN_MIN 0 0 0`, `DOMAIN_MAX 1 1 1`, ASCII, saída em [0, 1]. Cada arquivo traz entrada e saída no cabeçalho.

### Data levels (importante)
Os LUTs de câmera assumem que o host entrega o sinal em **faixa de vídeo** normalizada, o padrão para arquivos de câmera:
- **DaVinci Resolve**: Clip Attributes → Data Levels = **Auto** ou **Video**.
- **Premiere Pro**: padrão para arquivos de câmera.

Se o clip for interpretado como **Full**, a exposição e o contraste ficam levemente errados. O motor gera variantes "full" sob demanda (`"range": "full"` no perfil + `build_luts.py`), mas elas não fazem parte da VOL. 01.

## O que foi verificado

| Verificação | Status |
|---|---|
| Curvas Log e matrizes de câmera vs implementações independentes (OpenColorIO 2.6 builtins) e valores publicados | ✅ testado (`tests/color-science/`) |
| Estrutura dos 180 `.cube` (leitor estrito, tamanho, contagem, finitos, domínio, ASCII) | ✅ testado |
| Fidelidade de cada arquivo reimportado vs pipeline (CIEDE2000, interpolação tetraédrica e trilinear) | ✅ 180/180 |
| Identidade do perfil Rec.709 e do Creative Only com look neutro | ✅ testado |
| Cinza 18 % de cada câmera → mesmo cinza neutro | ✅ testado |
| **Abertura e aparência no DaVinci Resolve** | ⏳ **não testado** — nenhum host disponível neste ambiente |
| **Abertura e aparência no Adobe Premiere Pro (Lumetri)** | ⏳ **não testado** |
| **Footage real de cada câmera (Sony, iPhone, Canon)** | ⏳ **não testado** |
| Convenção de faixa do Apple Log (P como CV/1023) | ⚠️ coerente com a curva e com tabelas de code values publicadas por terceiros; confirmar com arquivo real do iPhone |

Os arquivos seguem o formato `.cube` lido por Resolve e Premiere (Adobe Cube LUT Specification 1.0). Compatibilidade **validada no host** só pode ser declarada depois do teste de aceitação abaixo.

### Teste de aceitação sugerido (antes da venda)
1. Resolve: Data Levels = Auto; aplicar `CINERA_01_SIGNATURE_STANDARD_SLOG3_SGAMUT3CINE_TO_REC709_65.cube` em um clip S-Log3 com cartela cinza 18 %. No waveform, o cinza deve ficar em ≈ 40–41 % (0.406 codificado).
2. Repetir com o equivalente 33³ (o resultado deve ser visualmente idêntico).
3. Premiere: Lumetri → Creative → Look → Browse, mesmo arquivo; comparar com o Resolve.
4. Repetir 1–3 para Apple Log e Canon Log 3.
5. Creative Only: projeto ACEScct no Resolve, aplicar `..._ACESCCT_TO_ACESCCT_65.cube` em um nó; comparar com o arquivo Camera to Rec.709 do mesmo look (a aparência só coincide se a transformada de saída for a CINÉRA Neutral Rendering; com a ODT ACES a aparência difere, como em qualquer LMT).

## Arquitetura para novos perfis

Perfis são arquivos JSON em `profiles/<fabricante>/`. Para adicionar uma câmera:
1. Registrar a função de transferência em `transforms/transfer.py` (somente de fonte publicada; preferir colour-science) e o gamut em `transforms/colorspaces.py`.
2. Criar o JSON do perfil (entrada, faixa de sinal, referências).
3. Adicionar teste contra uma implementação independente (OCIO builtin) ou contra valores publicados. **Sem teste verificável, o perfil não entra.**

Candidatos com implementação independente disponível (colour-science + OCIO): ARRI LogC3 / LogC4, Panasonic V-Log/V-Gamut, Blackmagic Film Gen 5, DJI D-Log, Fujifilm F-Log/F-Log2, RED Log3G10. Nenhum foi implementado nesta fase.
