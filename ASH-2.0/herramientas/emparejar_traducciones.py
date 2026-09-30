# -*- coding: utf-8 -*-
"""
Crea idiomas/en.json juntando:
  - idiomas/_catalogo.json (frases del motor, en orden) + idiomas/en_lista.json
    (sus traducciones, en el mismo orden),
  - idiomas/en_extra.json (frases de ash_web.py y demás, ya como clave -> valor).

Comprueba que cada traducción conserva los mismos marcadores {0}, {1:,}...
y el emoji inicial (el programa reconoce algunas copias por él).
"""

import re
import sys
import json
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / "idiomas"
MARCADOR = re.compile(r"(?<!\{)\{(\d+)([^{}]*)\}(?!\})")


def marcadores(texto):
    return sorted(MARCADOR.findall(texto))


def main():
    catalogo = list(json.loads((CARPETA / "_catalogo.json").read_text(encoding="utf-8")).keys())
    lista = json.loads((CARPETA / "en_lista.json").read_text(encoding="utf-8"))
    if len(catalogo) != len(lista):
        sys.exit(f"ERROR: el catálogo tiene {len(catalogo)} frases y la lista {len(lista)}")
    tabla = {}
    errores = []
    extra_ruta = CARPETA / "en_extra.json"
    extra = json.loads(extra_ruta.read_text(encoding="utf-8")) if extra_ruta.exists() else {}
    for es, en in list(zip(catalogo, lista)) + list(extra.items()):
        if not en:
            continue
        if marcadores(es) != marcadores(en):
            errores.append(f"marcadores distintos:\n  es: {es[:90]!r}\n  en: {en[:90]!r}")
        if es.startswith(("↩️", "🟢", "🗓️")) and es[:2] != en[:2]:
            errores.append(f"emoji inicial distinto: {es[:40]!r}")
        tabla[es] = en
    if errores:
        sys.exit("ERROR:\n" + "\n".join(errores))
    (CARPETA / "en.json").write_text(json.dumps(tabla, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"en.json: {len(tabla)} frases")


if __name__ == "__main__":
    main()
