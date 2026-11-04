# Instalação — CINÉRA VOL. 01

## Qual arquivo usar?

```
Seu clip está em Log da câmera?
├── Sim, e quero o resultado direto em Rec.709 → pasta da câmera (sony-slog3 / apple-log / canon-log3), formato Camera to Rec.709
├── Sim, e trabalho com gerenciamento de cor ACES (ACEScct) → creative-only (ACEScct → ACEScct)
└── Não, o clip já está em Rec.709 → rec709
```

- **65** (65³): máxima precisão, recomendado para finalização.
- **33** (33³): arquivos menores, compatíveis com hosts e hardware que limitam o tamanho do LUT.

Variações: **SOFT** (mais suave), **STANDARD** (principal), **RICH** (mais contraste e separação).

## DaVinci Resolve

1. *Project Settings → Color Management → Lookup Tables → Open LUT Folder*.
2. Copie a pasta `CINERA VOL 01` para dentro dela.
3. Clique em *Update Lists* (ou reinicie o Resolve).
4. Clip de câmera: confirme *Clip Attributes → Data Levels = Auto/Video*.
5. Na página Color, botão direito no nó → *LUT → CINERA VOL 01 → …*. Ajustes de exposição e balanço vêm **antes** do nó do LUT.
6. Creative Only: em um projeto *ACEScct* (ou entre CSTs para ACEScct), aplique o LUT `ACESCCT_TO_ACESCCT` antes da transformada de saída.

## Adobe Premiere Pro

1. Painel *Lumetri Color → Creative → Look → Browse…* e escolha o `.cube`
   (ou *Basic Correction → Input LUT* para os arquivos Camera to Rec.709).
2. Para deixar os LUTs disponíveis no menu, copie os arquivos para a pasta de Lumetri LUTs da sua versão (o caminho varia por versão e sistema; consulte a documentação da Adobe).
3. Não use o LUT de câmera junto com a conversão automática Log do Premiere (*Settings → Color → Log Color Management / auto tone map*) ativada para o mesmo clip, pois isso duplica a conversão.

## Final Cut Pro

Efeito *Custom LUT* → escolha o `.cube`. Para Log, desative a conversão automática de Log do FCP no clip quando usar o LUT Camera to Rec.709.

## Boas práticas

- Exponha corretamente: os looks foram desenhados com cinza 18 % no nível de referência de cada câmera.
- Faça o balanço de branco antes do LUT.
- Pele: os looks protegem a pele, mas iluminação muito mista exige correção secundária.

> Status: o formato `.cube` segue a especificação lida pelo Resolve e pelo Premiere, mas a abertura nesses programas ainda não foi testada nesta fase (ver `COMPATIBILITY.md`).
