# -*- coding: utf-8 -*-
"""
Base de datos propia de Arlequin (la que usa Arlequin GameHub), hecha solo con
lo que aportan los usuarios con "Ayuda a mejorar Arlequin": rutas de partidas
con comodines (<winDocuments>/My Games/Juego...), sin datos de terceros.

Una ruta entra en la base cuando:
  - la añadió alguien a mano o GameHub vio al juego escribir en ella ("manual",
    "observada"): basta 1 equipo, son muy fiables;
  - la encontró GameHub por el nombre del juego ("candidata"): hacen falta
    MIN_CANDIDATA equipos distintos, salvo si la envía un probador (con código
    de licencia de Arlequin: "probador" en el campo app), que vale con 1.

Genera arlequin_bd.json:
  { "version": 1, "generado": "...", "juegos": [
      { "tienda": "steam", "id": "12110", "nombre": "...", "rutas": ["<winDocuments>/..."] } ] }

Los identificadores de instalación NUNCA se guardan en el repositorio.

Uso:  python contribuciones/bd_arlequin.py envios.json
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
MIN_CANDIDATA = 2
FIABLES = {"manual", "observada"}
COMODIN = re.compile(r"^<(home|root|base|winAppData|winLocalAppData|winDocuments|winPublic|winProgramData|winDir|osUserName|storeUserId)>")


def norm(texto):
    return re.sub(r"[^0-9a-z]+", "", str(texto or "").lower())


def main(archivo_envios):
    envios = json.loads(Path(archivo_envios).read_text(encoding="utf-8"))
    filas = envios.get("filas", envios) if isinstance(envios, dict) else envios
    # (clave juego, plantilla normalizada) -> datos
    rutas = {}
    for f in filas:
        if f.get("tipo") != "ruta":
            continue
        plantilla = str(f.get("plantilla") or "").replace("\\", "/").rstrip("/")
        if not COMODIN.match(plantilla) or re.search(r"[a-z]:/", plantilla, re.I):
            continue
        tienda = str(f.get("launcher") or "").strip().lower()
        id_tienda = str(f.get("id_tienda") or "").strip()
        nombre = str(f.get("juego") or "").strip()
        if not nombre:
            continue
        clave_juego = f"{tienda}:{id_tienda}" if tienda and id_tienda else f"nombre:{norm(nombre)}"
        r = rutas.setdefault((clave_juego, plantilla.lower()), {
            "tienda": tienda if id_tienda else "", "id": id_tienda, "nombre": nombre,
            "plantilla": plantilla, "fiable": set(), "candidata": set()})
        origen = str(f.get("origen") or "")
        instalacion = str(f.get("instalacion") or "")
        # Los probadores (código de licencia de Arlequin) son de confianza: basta 1 equipo.
        probador = "probador" in str(f.get("app") or "").lower()
        (r["fiable"] if origen in FIABLES or probador else r["candidata"]).add(instalacion)

    juegos = {}
    for (clave_juego, _), r in rutas.items():
        equipos = r["fiable"] | r["candidata"]
        if not (r["fiable"] or len(r["candidata"]) >= MIN_CANDIDATA):
            continue
        j = juegos.setdefault(clave_juego, {"tienda": r["tienda"], "id": r["id"], "nombre": r["nombre"], "rutas": [], "_equipos": {}})
        j["rutas"].append(r["plantilla"])
        j["_equipos"][r["plantilla"]] = len(equipos)
    salida = []
    for j in juegos.values():
        # Primero las rutas que confirman más equipos.
        j["rutas"].sort(key=lambda p: -j["_equipos"][p])
        del j["_equipos"]
        salida.append(j)
    salida.sort(key=lambda j: j["nombre"].lower())
    datos = {"version": 1, "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "juegos": salida}
    (CARPETA / "arlequin_bd.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Base de Arlequin: {len(salida)} juegos, {sum(len(j['rutas']) for j in salida)} rutas")


if __name__ == "__main__":
    main(sys.argv[1])
