# -*- coding: utf-8 -*-
"""
Lista las frases de la interfaz (frontend/src) que pasan por t('...') o por
props que los componentes traducen (texto=, titulo=, ayuda=...) y comprueba
cuáles faltan en frontend/src/idiomas/en.js.

Uso: python herramientas/claves_interfaz.py [--todas]
"""

import re
import sys
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "frontend" / "src"
PATRONES = [
    re.compile(r"\bt\(\s*'((?:[^'\\]|\\.)*)'"),
    re.compile(r"\b(?:texto|titulo|ayuda)=\"([^\"]+)\""),
    re.compile(r"texto: '([^']+)'"),
    re.compile(r"abrirSelector\('\w+', '([^']+)'\)"),
]


def claves():
    encontradas = {}
    for ruta in sorted(RAIZ.rglob("*.js*")):
        if ruta.name in ("simulada.js", "en.js"):
            continue
        texto = ruta.read_text(encoding="utf-8")
        for patron in PATRONES:
            for m in patron.finditer(texto):
                clave = m.group(1).replace("\\'", "'")
                encontradas.setdefault(clave, ruta.name)
    return encontradas


def traducidas():
    ruta = RAIZ / "idiomas" / "en.js"
    if not ruta.exists():
        return {}
    texto = ruta.read_text(encoding="utf-8")
    cuerpo = texto[texto.index("{"): texto.rindex("}") + 1]
    return json.loads(cuerpo)


def main():
    todas = claves()
    en = traducidas()
    faltan = {k: v for k, v in todas.items() if k not in en}
    if "--todas" in sys.argv:
        for k, v in todas.items():
            print(f"{v} | {k}")
    print(f"{len(todas)} frases en la interfaz; faltan {len(faltan)} en en.js")
    for k, v in faltan.items():
        print(f"  FALTA ({v}): {k}")
    return 1 if faltan else 0


if __name__ == "__main__":
    sys.exit(main())
