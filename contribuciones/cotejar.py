# -*- coding: utf-8 -*-
"""
Coteja los envíos de "Ayuda a mejorar Arlequin" con ArlequinGameDB.yaml y
genera, en esta carpeta:

  - rutas_aprendidas.json : rutas propuestas por los usuarios, agrupadas por
    juego y plantilla, con cuántos equipos distintos la confirman y si la
    base de datos ya la tiene.
  - juegos_sin_ruta.json  : juegos instalados sin ruta conocida, con cuántos
    equipos los tienen (para priorizar qué investigar).
  - INFORME.md            : resumen legible.

Los identificadores de instalación NUNCA se guardan en el repositorio: solo
se usan aquí para contar equipos distintos.

Uso:  python contribuciones/cotejar.py envios.json ArlequinGameDB.yaml
"""

import sys
import re
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

CARPETA = Path(__file__).resolve().parent
MIN_CONFIRMACIONES = 2   # equipos distintos para considerar una ruta "confirmada"


def norm(texto):
    texto = (texto or "").lower()
    for ch in "'’´`":
        texto = texto.replace(ch, "")
    texto = re.sub(r"[^\w]+", " ", texto, flags=re.UNICODE)
    return " ".join(texto.split())


def norm_plantilla(p):
    p = re.sub(r"\s*\[[^\]]*\]\s*$", "", str(p or "")).replace("\\", "/").rstrip("/")
    return p.lower()


def cargar_bd(ruta):
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or []
    fichas = datos if isinstance(datos, list) else list((datos or {}).values())
    por_nombre, por_steam = {}, {}
    for ficha in fichas:
        if not isinstance(ficha, dict):
            continue
        nombres = [ficha.get("name") or ""]
        nombres += [a.strip() for a in str(ficha.get("acronyms") or "").split(",") if a.strip()]
        for n in nombres:
            if norm(n):
                por_nombre.setdefault(norm(n), ficha)
        ids = ficha.get("ids") or {}
        for sid in [ids.get("steam")] + list(ids.get("steamExtra") or []):
            if sid:
                por_steam.setdefault(str(sid), ficha)
    return por_nombre, por_steam


def buscar(ficha_por_nombre, ficha_por_steam, juego, launcher, id_tienda):
    if str(launcher).lower() == "steam" and str(id_tienda) in ficha_por_steam:
        return ficha_por_steam[str(id_tienda)]
    return ficha_por_nombre.get(norm(juego))


def main(archivo_envios, archivo_bd):
    envios = json.loads(Path(archivo_envios).read_text(encoding="utf-8"))
    filas = envios.get("filas", envios) if isinstance(envios, dict) else envios
    por_nombre, por_steam = cargar_bd(archivo_bd)

    rutas = {}
    sin_ruta = {}
    for f in filas:
        tipo = f.get("tipo")
        juego = str(f.get("juego") or "").strip()
        if not juego:
            continue
        launcher, id_tienda = str(f.get("launcher") or ""), str(f.get("id_tienda") or "")
        instalacion = str(f.get("instalacion") or "")
        fecha = str(f.get("fecha") or "")[:10]
        clave_juego = f"steam:{id_tienda}" if launcher.lower() == "steam" and id_tienda else f"nombre:{norm(juego)}"
        if tipo == "ruta":
            plantilla = str(f.get("plantilla") or "").replace("\\", "/").rstrip("/")
            if not plantilla.startswith("<"):
                continue
            clave = (clave_juego, norm_plantilla(plantilla))
            r = rutas.setdefault(clave, {"juego": juego, "launcher": launcher, "id_tienda": id_tienda,
                                         "plantilla": plantilla, "origenes": set(), "equipos": set(),
                                         "primera": fecha, "ultima": fecha})
            r["origenes"].add(str(f.get("origen") or ""))
            r["equipos"].add(instalacion)
            r["primera"], r["ultima"] = min(r["primera"], fecha), max(r["ultima"], fecha)
        elif tipo == "sin_ruta":
            if str(f.get("estado") or "").startswith("marcado_"):
                continue  # marcas de "es / no es un juego": las cuenta clasificar.py
            s = sin_ruta.setdefault(clave_juego, {"juego": juego, "launcher": launcher, "id_tienda": id_tienda,
                                                  "equipos": set(), "ultima": fecha})
            s["equipos"].add(instalacion)
            s["ultima"] = max(s["ultima"], fecha)

    salida_rutas = []
    for r in rutas.values():
        ficha = buscar(por_nombre, por_steam, r["juego"], r["launcher"], r["id_tienda"])
        conocidas = {norm_plantilla(p) for p in (ficha or {}).get("save_locations") or []}
        salida_rutas.append({
            "juego": r["juego"], "launcher": r["launcher"], "id_tienda": r["id_tienda"],
            "plantilla": r["plantilla"], "origenes": sorted(o for o in r["origenes"] if o),
            "equipos": len(r["equipos"]), "confirmada": len(r["equipos"]) >= MIN_CONFIRMACIONES,
            "en_bd": bool(ficha), "bd_nombre": (ficha or {}).get("name"),
            "ya_en_bd": norm_plantilla(r["plantilla"]) in conocidas,
            "primera": r["primera"], "ultima": r["ultima"],
        })
    salida_rutas.sort(key=lambda x: (x["ya_en_bd"], -x["equipos"], x["juego"].lower()))

    salida_sin = []
    for s in sin_ruta.values():
        ficha = buscar(por_nombre, por_steam, s["juego"], s["launcher"], s["id_tienda"])
        propuestas = [r for r in salida_rutas if (r["id_tienda"] and r["id_tienda"] == s["id_tienda"]) or norm(r["juego"]) == norm(s["juego"])]
        salida_sin.append({
            "juego": s["juego"], "launcher": s["launcher"], "id_tienda": s["id_tienda"],
            "equipos": len(s["equipos"]), "en_bd": bool(ficha),
            "bd_tiene_ruta": bool((ficha or {}).get("save_locations")),
            "rutas_propuestas": len(propuestas), "ultima": s["ultima"],
        })
    salida_sin.sort(key=lambda x: (x["bd_tiene_ruta"], -x["equipos"], x["juego"].lower()))

    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (CARPETA / "rutas_aprendidas.json").write_text(
        json.dumps({"generado": ahora, "rutas": salida_rutas}, ensure_ascii=False, indent=1), encoding="utf-8")
    (CARPETA / "juegos_sin_ruta.json").write_text(
        json.dumps({"generado": ahora, "juegos": salida_sin}, ensure_ascii=False, indent=1), encoding="utf-8")

    def celda(t):
        return str(t).replace("|", "\\|")

    nuevas = [r for r in salida_rutas if not r["ya_en_bd"]]
    confirmadas = [r for r in nuevas if r["confirmada"]]
    pendientes = [s for s in salida_sin if not s["bd_tiene_ruta"]]
    lineas = [
        "# Informe de rutas aprendidas", "",
        f"Generado: {ahora}. Datos anónimos enviados por quienes activaron *Ayuda a mejorar Arlequin*.", "",
        f"- Rutas nuevas propuestas: **{len(nuevas)}** (confirmadas por {MIN_CONFIRMACIONES}+ equipos: **{len(confirmadas)}**)",
        f"- Juegos instalados sin ruta en la base de datos: **{len(pendientes)}**", "",
        f"## Rutas confirmadas por {MIN_CONFIRMACIONES} o más equipos (candidatas a entrar en la BD)", "",
        "| Juego | Tienda | Plantilla | Equipos | Origen | En la BD |", "|---|---|---|---|---|---|",
    ]
    for r in confirmadas[:200]:
        lineas.append(f"| {celda(r['juego'])} | {celda((r['launcher'] + ' ' + r['id_tienda']).strip())} | `{celda(r['plantilla'])}` "
                      f"| {r['equipos']} | {', '.join(r['origenes'])} | {'sí' if r['en_bd'] else 'no'} |")
    if not confirmadas:
        lineas.append("| — | | | | | |")
    lineas += ["", "## Rutas propuestas por un solo equipo", "",
               "| Juego | Tienda | Plantilla | Origen |", "|---|---|---|---|"]
    for r in [x for x in nuevas if not x["confirmada"]][:300]:
        lineas.append(f"| {celda(r['juego'])} | {celda((r['launcher'] + ' ' + r['id_tienda']).strip())} | `{celda(r['plantilla'])}` | {', '.join(r['origenes'])} |")
    lineas += ["", "## Juegos sin ruta más comunes", "",
               "| Juego | Tienda | Equipos | En la BD | Rutas propuestas |", "|---|---|---|---|---|"]
    for s in pendientes[:300]:
        lineas.append(f"| {celda(s['juego'])} | {celda((s['launcher'] + ' ' + s['id_tienda']).strip())} | {s['equipos']} "
                      f"| {'sí' if s['en_bd'] else 'no'} | {s['rutas_propuestas']} |")
    (CARPETA / "INFORME.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"{len(salida_rutas)} rutas, {len(salida_sin)} juegos sin ruta")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
