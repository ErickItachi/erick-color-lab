# CINÉRA VOL. 01 — Guia de Instalação

## DaVinci Resolve

1. Abra **Project Settings → Color Management → Lookup Tables → Open LUT Folder**.
2. Copie a pasta **LUTs** da CINÉRA para dentro dela (renomeie para `CINERA VOL 01`, se preferir).
3. Clique em **Update Lists** ou reinicie o Resolve.
4. Para clips de câmera, confira **Clip Attributes → Data Levels = Auto** (ou **Video**).
5. Na página **Color**, clique com o botão direito no nó → **LUT → CINERA VOL 01 →** escolha o arquivo.
6. Faça exposição e balanço de branco em um nó **anterior** ao nó do LUT.

**Creative Only (ACEScct):** em um projeto ACEScct, ou entre duas Color Space Transforms (câmera → ACEScct e ACEScct → Rec.709), aplique o LUT `..._ACESCCT_TO_ACESCCT_...` no meio, antes da transformada de saída.

## Adobe Premiere Pro

1. No painel **Lumetri Color**:
   - LUTs de câmera (Log → Rec.709): **Basic Correction → Input LUT → Browse…**
   - LUTs Rec709 e looks sobre material já convertido: **Creative → Look → Browse…**
2. Se o Premiere estiver convertendo o Log da câmera automaticamente para esse clip (gerenciamento de cor/tone mapping automático de Log), desative essa conversão ao usar um LUT de câmera, senão a conversão é aplicada duas vezes.

## Final Cut Pro

Use o efeito **Custom LUT** e escolha o arquivo `.cube`. Ao usar um LUT de câmera, desative a conversão automática de Log do próprio Final Cut para o clip.

## Dicas de uso

- **Comece pelo STANDARD.** Se ficar intenso demais, use o SOFT; para mais contraste e separação, o RICH.
- **Intensidade:** no Resolve, reduza a opacidade do nó (Key Output Gain) para suavizar o look.
- **Pele:** os looks protegem a pele, mas cenas com iluminação muito mista podem pedir um ajuste secundário.
- **Creative Only** é para coloristas em fluxo gerenciado; para uso direto, prefira os LUTs de câmera ou Rec709.
- **Monitoramento:** os LUTs entregam Rec.709 para monitores BT.1886 (gama 2.4), o padrão de finalização de vídeo.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Imagem muito contrastada / saturada | conversão Log aplicada duas vezes | desative a conversão automática do programa ou use o LUT Rec709 |
| Imagem lavada ou com preto "cinza" | Data Levels em Full | Clip Attributes → Data Levels = Auto/Video |
| Cor muito diferente do esperado | perfil errado (ex.: S-Gamut3 vs S-Gamut3.Cine) | confira o gamut de gravação na câmera |
| LUT não aparece na lista | lista não atualizada | Update Lists / reiniciar o programa |
