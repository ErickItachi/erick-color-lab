"""Product / tool identity constants.

ERICK COLOR LAB = software (this engine).  CINÉRA = LUT product line.
Keep every user-facing string here so future collections (VOL. 02, ...) only
need a new collection entry, not code changes.
"""

ENGINE_NAME = "ERICK COLOR LAB"
ENGINE_VERSION = "0.1.0"

BRAND = {
    "product_line": "CINÉRA",
    "product_line_ascii": "CINERA",
    "tagline": "The Cinematic Color Collection",
    "signature": "By Erick Filmes",
    "category": "Cinematic LUT Collection",
    "company": "Erick Filmes",
}

# One entry per published collection. New volumes are added here.
COLLECTIONS = {
    "cinera-vol-01": {
        "id": "cinera-vol-01",
        "name": "CINÉRA VOL. 01",
        "name_ascii": "CINERA VOL. 01",
        "file_prefix": "CINERA",
        "version": "1.0.0",
        "looks": [
            "01-signature",
            "02-golden",
            "03-olive",
            "04-blue-hour",
            "05-romance",
        ],
        "variants": ["standard", "soft", "rich"],
    }
}
