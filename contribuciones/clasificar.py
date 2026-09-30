# -*- coding: utf-8 -*-
"""
Lista de la comunidad de "esto no es un juego" (y "esto sí es un juego").

En Arlequin GameHub, al quitar una entrada de la biblioteca hay que decir si es
un juego o no. Con "Ayuda a mejorar Arlequin" esa marca llega como una fila
sin_ruta con estado "marcado_no_juego" o "marcado_juego". Aquí se cuentan los
votos por entrada (tienda:id), un voto por instalación (el más reciente), y se
genera clasificacion.json:

  - no_juegos: entradas con MIN_VOTOS o más instalaciones distintas diciendo que
    NO es un juego y al menos el MAYORIA de los votos. GameHub las oculta solo.
  - juegos:    lo mismo, pero diciendo que SÍ es un juego (para no ocultarlas nunca).

Mientras una entrada no llegue al mínimo, GameHub no decide nada por su cuenta.
Los identificadores de instalación NUNCA se guardan en el repositorio.

Uso:  python contribuciones/clasificar.py envios.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
MIN_VOTOS = 3        # instalaciones distintas
MAYORIA = 0.75       # parte de los votos que tiene que estar de acuerdo


def main(archivo_envios):
    envios = json.loads(Path(archivo_envios).read_text(encoding="utf-8"))
    filas = envios.get("filas", envios) if isinstance(envios, dict) else envios
    # (tienda:id) -> instalación -> (fecha, es_juego)
    votos, nombres = {}, {}
    for f in filas:
        estado = str(f.get("estado") or "")
        if f.get("tipo") != "sin_ruta" or estado not in ("marcado_juego", "marcado_no_juego"):
            continue
        tienda, id_tienda = str(f.get("launcher") or "").strip().lower(), str(f.get("id_tienda") or "").strip()
        instalacion = str(f.get("instalacion") or "")
        if not tienda or not id_tienda or not instalacion:
            continue
        clave = f"{tienda}:{id_tienda}"
        fecha = str(f.get("fecha") or "")
        anterior = votos.setdefault(clave, {}).get(instalacion)
        if anterior is None or fecha >= anterior[0]:
            votos[clave][instalacion] = (fecha, estado == "marcado_juego")
        nombres[clave] = str(f.get("juego") or "")

    no_juegos, juegos, detalle = [], [], []
    for clave, por_instalacion in votos.items():
        si = sum(1 for _, es in por_instalacion.values() if es)
        no = len(por_instalacion) - si
        total = si + no
        decision = ""
        if no >= MIN_VOTOS and no >= MAYORIA * total:
            no_juegos.append(clave)
            decision = "no_juego"
        elif si >= MIN_VOTOS and si >= MAYORIA * total:
            juegos.append(clave)
            decision = "juego"
        detalle.append({"id": clave, "nombre": nombres.get(clave, ""), "si_juego": si, "no_juego": no, "decision": decision})
    detalle.sort(key=lambda d: (-(d["si_juego"] + d["no_juego"]), d["nombre"].lower()))

    salida = {
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "min_votos": MIN_VOTOS, "mayoria": MAYORIA,
        "no_juegos": sorted(no_juegos), "juegos": sorted(juegos), "detalle": detalle,
    }
    (CARPETA / "clasificacion.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(detalle)} entradas votadas: {len(no_juegos)} no son juegos, {len(juegos)} sí")


if __name__ == "__main__":
    main(sys.argv[1])
