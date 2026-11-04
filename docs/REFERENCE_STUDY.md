# Estudo de referência — organização de pacote e interoperabilidade

> Documento de desenvolvimento. **Não faz parte de nenhum pacote comercial CINÉRA** (o `package_collection.py` o exclui e bloqueia qualquer menção a terceiros no pacote).

## Escopo e método

- Material estudado: um pacote comercial de LUTs de terceiros, disponível no Google Drive conectado (pasta "FJR Looks - La Creme"), usado **só como referência de organização e acabamento**.
- Acesso **somente leitura** pela integração do Google Drive: listagem de pastas e metadados (nome, tipo, tamanho, datas). Nada foi renomeado, movido, alterado ou baixado.
- **Não** foram lidas as tabelas RGB de nenhum LUT, nem usadas como ponto de partida, nem aproximadas. Do único arquivo de texto (preset do Resolve) foi visto apenas o cabeçalho XML devolvido pela busca do Drive.
- Nenhum arquivo de terceiros foi copiado para este repositório (bloqueado em `.gitignore`).
- Existem duas pastas com o mesmo nome no Drive: a original compartilhada e uma cópia criada em 2026-11-04, com a mesma estrutura de primeiro nível.

## Organização observada

```
<pacote>/
├── Cameras/
│   ├── ARRI/Log-C/                       4 .cube
│   ├── Apple/iPhone 15 - Apple Log/      4 .cube
│   ├── Blackmagic/Film Gen 4/            4 .cube (nomes dizem "Film-Gen5")
│   ├── Blackmagic/Film Gen 5/            4 .cube
│   ├── DJI/Ronin 4D/                     4 .cube (D-Log)
│   ├── Panasonic/S1, S1H, S5/            4 .cube (V-Log)
│   └── Panasonic/S5ii/                   4 .cube (V-Log)
├── Rec709/                                4 looks × [33] e [65] .cube
├── Powergrades/                           5 .drx (stills do DaVinci Resolve 18.6.6: 4 looks + 1 "LUT")
└── LR Profiles/
    ├── [XMP]/                             4 perfis Lightroom/ACR
    └── [DNG]/                             4 imagens .dng de amostra
```

- 4 looks por perfil, com nomes temáticos curtos.
- Arquivos de câmera com ~0.93–0.96 MB, compatíveis com 33³ a 6 casas decimais (**inferido pelo tamanho; os arquivos não foram abertos**). Rec.709 com ~0.96 MB ([33]) e ~7.3 MB ([65]).
- **Não havia** documentação, instruções ou notas de espaço de cor/faixa de sinal no pacote.
- **Não havia** perfis Sony S-Log3 nem Canon Log 3.

## Lições aplicadas à CINÉRA

| Observação no pacote de referência | Decisão na CINÉRA |
|---|---|
| Nome do arquivo cita a curva, mas não o gamut ("Log-C", "V-Log") | o token de entrada sempre inclui curva **e** gamut (`SLOG3_SGAMUT3CINE`) e a saída (`_TO_REC709`) |
| Pasta "Film Gen 4" com arquivos chamados "Gen5" | nomes gerados automaticamente a partir do perfil (`collection.py`), sem edição manual |
| Resolução indicada só nos arquivos Rec.709 | sufixo `_33` / `_65` em todos os arquivos |
| Sem documentação de entrada/saída | cabeçalho de cada `.cube` + `COMPATIBILITY.md` com entrada, saída e faixa de sinal exatas |
| Sem verificação/checksum | `MANIFEST.json` com SHA-256 + relatório de validação por arquivo |
| Ecossistema multi-host (LUT + PowerGrade + perfil Lightroom) | arquitetura preparada (parâmetros em JSON); PowerGrades/perfis Lightroom ficam para fases futuras |
| Só variantes "camera → Rec.709" | adicionado **Creative Only** (ACEScct → ACEScct) para pipelines gerenciados |

A estética da CINÉRA foi definida de forma independente (ver `LOOKS.md`).
