# CINÉRA VOL. 01
**The Cinematic Color Collection — By Erick Filmes**

Obrigado por adquirir a CINÉRA VOL. 01.

A CINÉRA trata a cor como linguagem narrativa: atmosferas cinematográficas que preservam a naturalidade da imagem, com atenção especial à pele, às altas luzes e à profundidade dos pretos.

## O que vem na coleção

- **5 looks:** 01 SIGNATURE · 02 GOLDEN · 03 OLIVE · 04 BLUE HOUR · 05 ROMANCE
- **3 variações por look:** SOFT (mais suave) · STANDARD (principal) · RICH (mais contraste e separação de cores)
- **6 perfis de entrada**, cada um em duas resoluções (**33** e **65**). São 180 LUTs `.cube` no total.

| Pasta | Para quem | Entrada → saída |
|---|---|---|
| **Rec709** | footage gravado ou já convertido em Rec.709 | Rec.709 → Rec.709 |
| **Sony S-Log3** | Sony em S-Log3 (S-Gamut3.Cine ou S-Gamut3) | Log da câmera → Rec.709 |
| **Apple Log** | iPhone 15 Pro e posteriores gravando em Apple Log | Apple Log → Rec.709 |
| **Canon Log 3** | Canon em Canon Log 3 / Cinema Gamut | Log da câmera → Rec.709 |
| **Creative Only (ACEScct)** | coloristas em fluxo gerenciado ACEScct | ACEScct → ACEScct (somente o look) |

## Qual arquivo escolher

1. **Pela pasta:** o perfil da sua câmera, ou Rec709 se o vídeo já está em Rec.709.
2. **Pelo look e pela variação:** comece pelo STANDARD.
3. **Pela resolução:** **65** para finalização (máxima precisão); **33** para programas ou equipamentos que limitam o tamanho do LUT.

Os nomes dos arquivos dizem exatamente a entrada e a saída:

```
CINERA_01_SIGNATURE_STANDARD_SLOG3_SGAMUT3CINE_TO_REC709_65.cube
        look      variação   entrada            saída  resolução
```

## Três regras de ouro

1. **Exposição e balanço de branco antes do LUT.** Os looks foram desenhados com o cinza 18 % no nível de referência de cada câmera.
2. **Uma conversão por vez.** Um LUT de câmera (Log → Rec.709) já faz a conversão técnica; não o combine com outra conversão da mesma câmera.
3. **Data Levels em Auto/Video** para clips de câmera (padrão do DaVinci Resolve e do Premiere Pro).

Instruções completas: **Guia de Instalação**. Descrição de cada look: **Catálogo dos Looks**.

## Integridade dos arquivos

Cada pasta de LUTs traz um `MANIFEST.json` com a assinatura SHA-256 de cada arquivo, para conferir que nenhum arquivo foi corrompido no download.

---
© Erick Filmes. Todos os direitos reservados. O uso está sujeito à **Licença de Uso**.
