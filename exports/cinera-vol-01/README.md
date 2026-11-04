# exports/cinera-vol-01 — CINÉRA VOL. 01

Destino dos 180 arquivos `.cube` gerados por `scripts/build_luts.py`:

| Pasta | Conteúdo | Formato |
|---|---|---|
| `rec709/` | 15 variantes × 33/65 | Rec.709 → Rec.709 |
| `sony-slog3/` | 15 × 2 gamuts (S-Gamut3.Cine, S-Gamut3) × 33/65 | Camera to Rec.709 |
| `apple-log/` | 15 × 33/65 | Camera to Rec.709 |
| `canon-log3/` | 15 × 33/65 | Camera to Rec.709 |
| `creative-only/` | 15 × 33/65 | ACEScct → ACEScct |

Os `.cube` **não são versionados** (repositório público, e eles são o produto comercial). São reproduzíveis bit a bit:

```bash
python scripts/build_luts.py && python scripts/validate_luts.py
```

`MANIFEST.json` (versionado) guarda SHA-256, entrada, saída, faixa de sinal e fingerprint dos parâmetros de cada arquivo. `validate_luts.py` confere cada arquivo contra ele.
