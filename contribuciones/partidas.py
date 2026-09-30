"""FPS de los juegos según el hardware y los ajustes gráficos (datos de Arlequin GameHub).

Lee la hoja "Partidas" del Apps Script (una fila por partida medida con PresentMon) y
escribe contribuciones/fps.json y contribuciones/FPS.md: por juego, gráfica, resolución
y calidad, la mediana de los FPS medios y del 1 % bajo. Nunca sale el identificador de
instalación, solo cuántos equipos distintos hay detrás de cada cifra.

Se descartan las partidas limitadas (límite de FPS o VSync al tope de la pantalla), porque
no dicen cuánto da el equipo, y la generación de fotogramas va aparte.

Uso: python partidas.py partidas.json
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

AQUI = Path(__file__).parent


def numero(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def clave_juego(f):
    if f.get("launcher") and f.get("id_tienda"):
        return f"{f['launcher']}:{f['id_tienda']}"
    return "nombre:" + re.sub(r"[^a-z0-9]", "", str(f.get("juego", "")).lower())


def limitada(f):
    fps = numero(f.get("fps_media")) or 0
    limite = numero(f.get("limite_fps")) or 0
    # Hz de la pantalla en la que se jugó ("2560x1440@360 Philips 27M2N8500"); si no, la principal.
    m = re.search(r"@(\d+)", str(f.get("monitor") or ""))
    hz = float(m.group(1)) if m else (numero(f.get("pantalla_hz")) or 0)
    if limite > 0 and fps >= limite * 0.9:
        return True
    return f.get("vsync") == "si" and hz > 0 and fps >= hz * 0.9


def main():
    datos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not datos.get("ok"):
        print("Sin hoja de partidas todavía:", datos.get("error"))
        return
    filas = [f for f in datos.get("filas", []) if (numero(f.get("fps_media")) or 0) > 0 and (numero(f.get("minutos")) or 0) >= 1]
    validas = [f for f in filas if not limitada(f)]

    juegos = defaultdict(list)
    for f in validas:
        juegos[clave_juego(f)].append(f)

    salida = []
    for clave, lista in juegos.items():
        grupos = defaultdict(list)
        for f in lista:
            grupos[(f.get("gpu") or "?", f.get("resolucion") or "?", f.get("calidad") or "?", f.get("generacion") == "si")].append(f)
        resumen = []
        for (gpu, res, calidad, generacion), g in grupos.items():
            resumen.append({
                "gpu": gpu, "resolucion": res, "calidad": calidad, "generacion_fotogramas": generacion,
                "escalado": Counter(x.get("escalado") or "" for x in g).most_common(1)[0][0] or None,
                "cpu": Counter(x.get("cpu") or "" for x in g).most_common(1)[0][0] or None,
                "partidas": len(g), "equipos": len({x.get("instalacion") for x in g}),
                "fps_media": round(median(numero(x["fps_media"]) for x in g), 1),
                "fps_1_bajo": round(median(numero(x.get("fps_1_bajo")) or 0 for x in g), 1),
                "minutos": int(sum(numero(x.get("minutos")) or 0 for x in g)),
            })
        resumen.sort(key=lambda r: (-r["equipos"], -r["partidas"]))
        salida.append({
            "juego": Counter(f.get("juego") for f in lista).most_common(1)[0][0],
            "clave": clave,
            "partidas": len(lista),
            "equipos": len({f.get("instalacion") for f in lista}),
            "grupos": resumen,
        })
    salida.sort(key=lambda j: (-j["equipos"], -j["partidas"], j["juego"] or ""))

    total = {"partidas": len(filas), "validas": len(validas), "limitadas": len(filas) - len(validas),
             "equipos": len({f.get("instalacion") for f in filas}),
             "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "juegos": salida}
    (AQUI / "fps.json").write_text(json.dumps(total, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    md = ["# FPS de los juegos con Arlequin GameHub\n",
          f"{total['partidas']} partidas medidas en {total['equipos']} equipos ({total['limitadas']} limitadas por VSync o "
          f"límite de FPS, que no cuentan). Actualizado el {total['actualizado']}. Mediana de los FPS medios y del 1 % bajo; "
          "ningún dato identifica a nadie.\n"]
    for j in salida:
        md.append(f"\n## {j['juego']}\n\n| Gráfica | Resolución | Calidad | Escalado | FPS | 1 % bajo | Partidas | Equipos |\n|---|---|---|---|---:|---:|---:|---:|")
        for r in j["grupos"]:
            gen = " + gen. fotogramas" if r["generacion_fotogramas"] else ""
            md.append(f"| {r['gpu']} | {r['resolucion']} | {r['calidad']} | {(r['escalado'] or '—') + gen} | {r['fps_media']} | {r['fps_1_bajo']} | {r['partidas']} | {r['equipos']} |")
    (AQUI / "FPS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(total["partidas"], "partidas,", len(salida), "juegos")


if __name__ == "__main__":
    main()
