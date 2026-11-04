# Histórico de versões

## ERICK COLOR LAB 0.1.0 / CINÉRA VOL. 01 1.0.0 — 2026-11-04 (Fase 01, não publicado)

### Coleção
- 5 looks (Signature, Golden, Olive, Blue Hour, Romance) × 3 variações (Standard, Soft, Rich) = 15 variantes, todas com look v1.0.0.
- 6 perfis de entrada: Rec.709/BT.1886, S-Log3/S-Gamut3.Cine, S-Log3/S-Gamut3, Apple Log/BT.2020, Canon Log 3/Cinema Gamut, ACEScct (Creative Only).
- 180 arquivos `.cube` (33³ e 65³), 180/180 aprovados na validação por reimportação.

### Motor
- Funções de transferência e gamuts de fontes publicadas (colour-science), conferidos com OpenColorIO 2.6.
- CINÉRA Neutral Rendering v1 (tone scale invertível, compressão de gamut no display, BT.1886).
- ACES 1.3 Reference Gamut Compression na entrada de câmera.
- Operadores criativos: exposição, balanço, densidade de pretos, matriz, contraste/pivot (com preservação de matiz), lift/gamma/gain, tonal balance, curvas RGB monotônicas, compressão de altas, separação cromática, hue vs hue/sat/lum, mapeamento de saturação, proteção e alinhamento de pele.
- Baking `.cube`, leitor estrito, interpolação trilinear/tetraédrica, validação completa, cenas sintéticas, prévias e página HTML local.

### Correções encontradas pela própria validação durante a fase
- RGC movido do rendering para a entrada de câmera (operadores criativos instáveis em excursões de gamut extremas).
- Máscara de validade LMS, piso de C/L, fade de sombras profundas e fade por croma absoluto (curvatura e reversões perto do preto).
- Densidade de pretos passou a atuar na luminância (preserva matiz).
- Tintas tonais atenuadas na pele e neutras no preto absoluto.
- `contrast.hue_preservation` para estabilidade de pele com a exposição (Golden 0.85; demais 0.5–0.6).
- Rendering inverso exato e bem condicionado para fontes Rec.709.
- Máscaras de pele mais largas em Blue Hour e Olive (fidelidade do LUT em Canon Log 3).

### Pendente
- Teste de aceitação no DaVinci Resolve e no Premiere Pro.
- Teste com footage real de cada câmera e com material próprio (pessoas, casamentos, natureza, interiores, noite).
- Confirmação da convenção de faixa do Apple Log com arquivo real.
- Revisão jurídica do contrato de licença do usuário final.
