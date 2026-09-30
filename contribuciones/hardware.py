"""Estadísticas de hardware de los usuarios de Arlequin GameHub (como la encuesta de Steam).

Lee la hoja "Hardware" del Apps Script (una fila por instalación) y escribe
contribuciones/hardware.json y contribuciones/HARDWARE.md solo con porcentajes:
nunca sale del Apps Script el identificador de cada instalación.

Uso: python hardware.py hardware.json
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).parent
DIAS_ACTIVO = 180
TOP = 15


def numero(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tramo(v, cortes, unidad):
    """Agrupa un número en tramos: tramo(12, [4, 8, 16], 'GB') -> '8-16 GB'."""
    if v is None:
        return None
    anterior = 0
    for c in cortes:
        if v <= c:
            return f"{anterior:g}-{c:g} {unidad}" if anterior else f"≤{c:g} {unidad}"
        anterior = c
    return f">{cortes[-1]:g} {unidad}"


def ram_tramo(gb):
    if gb is None:
        return None
    for c in (4, 8, 12, 16, 24, 32, 48, 64, 96, 128):
        if gb <= c:
            return f"{c} GB"
    return ">128 GB"


def hz_tramo(hz):
    if not hz:
        return None
    for c in (60, 75, 100, 120, 144, 165, 180, 240, 280, 360, 500):
        if hz <= c + 2:
            return f"{c} Hz"
    return ">500 Hz"


def tb(gb):
    if not gb:
        return "Ninguno"
    return tramo(gb / 1000, [0.25, 0.5, 1, 2, 4, 8, 16], "TB")


def so_corto(so):
    so = str(so or "")
    for v in ("Windows 11", "Windows 10", "Windows 8", "Windows 7"):
        if v in so:
            return v
    if "Linux" in so or "SteamOS" in so:
        return "Linux / SteamOS"
    return so or None


def monitores(f):
    try:
        v = json.loads(f.get("monitores") or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def primero(texto):
    """Del "Razer Huntsman Elite + Logitech K120" se queda el primero."""
    return str(texto or "").split(" + ")[0].strip() or None


def marca(texto):
    p = primero(texto)
    return p.split()[0] if p else None


def reparto(valores, top=None):
    c = Counter(v for v in valores if v not in (None, ""))
    total = sum(c.values())
    if not total:
        return []
    filas = c.most_common()
    if top and len(filas) > top:
        resto = sum(n for _, n in filas[top:])
        filas = filas[:top] + [("Otros", resto)]
    return [{"valor": str(v), "equipos": n, "porcentaje": round(100 * n / total, 1)} for v, n in filas]


def main():
    datos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not datos.get("ok"):
        print("Sin hoja de hardware todavía:", datos.get("error"))
        return
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_ACTIVO)
    filas = []
    for f in datos.get("filas", []):
        try:
            fecha = datetime.fromisoformat(str(f.get("fecha")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if fecha >= limite:
            filas.append(f)

    portatiles_nvidia = [f for f in filas if f.get("portatil") == "si" and f.get("gpu_marca") == "NVIDIA" and numero(f.get("gpu_w"))]
    categorias = {
        "Procesador (marca)": reparto(f.get("cpu_marca") for f in filas),
        "Procesador (modelo)": reparto((f.get("cpu_modelo") for f in filas), TOP),
        "Núcleos": reparto(f"{int(numero(f.get('cpu_nucleos')))} núcleos" for f in filas if numero(f.get("cpu_nucleos"))),
        "Gráfica (marca)": reparto(f.get("gpu_marca") for f in filas),
        "Gráfica (modelo)": reparto((f.get("gpu_modelo") for f in filas), TOP),
        "Memoria de la gráfica": reparto(ram_tramo(round(numero(f.get("gpu_vram_gb")) or 0)) for f in filas if numero(f.get("gpu_vram_gb"))),
        "Vatios de gráficas NVIDIA de portátil": reparto(tramo(numero(f.get("gpu_w")), [35, 60, 80, 100, 115, 140, 175], "W") for f in portatiles_nvidia),
        "RAM": reparto(ram_tramo(numero(f.get("ram_gb"))) for f in filas),
        "Tipo de RAM": reparto(f.get("ram_tipo") for f in filas),
        "Velocidad de RAM": reparto(f"{int(numero(f.get('ram_mts')))} MT/s" for f in filas if numero(f.get("ram_mts"))),
        "Latencia CL de la RAM": reparto(f"CL{int(numero(f.get('ram_cl')))}" for f in filas if numero(f.get("ram_cl"))),
        "Sistema operativo": reparto(so_corto(f.get("so")) for f in filas),
        "Discos NVMe (M.2)": reparto(f"{int(numero(f.get('nvme_n')) or 0)}" for f in filas),
        "Espacio NVMe total": reparto(tb(numero(f.get("nvme_gb"))) for f in filas),
        "Discos SSD SATA": reparto(f"{int(numero(f.get('ssd_n')) or 0)}" for f in filas),
        "Espacio SSD SATA total": reparto(tb(numero(f.get("ssd_gb"))) for f in filas),
        "Discos duros (HDD)": reparto(f"{int(numero(f.get('hdd_n')) or 0)}" for f in filas),
        "Espacio HDD total": reparto(tb(numero(f.get("hdd_gb"))) for f in filas),
        "Tipo de equipo": reparto(("Steam Deck" if f.get("steam_deck") == "si" else "Portátil" if f.get("portatil") == "si" else "Sobremesa") for f in filas),
        "Resolución (pantalla principal)": reparto((f.get("pantalla") for f in filas), TOP),
        "Frecuencia (pantalla principal)": reparto(hz_tramo(numero(f.get("pantalla_hz"))) for f in filas),
        "Monitor principal (modelo)": reparto((f.get("pantalla_modelo") for f in filas), TOP),
        "Pulgadas (monitor principal)": reparto(f"{numero(f.get('pantalla_pulgadas')):g}\"" for f in filas if numero(f.get("pantalla_pulgadas"))),
        "Tipo de panel (monitor principal)": reparto(f.get("pantalla_panel") for f in filas),
        "Tipo de panel (todos los monitores)": reparto(m.get("panel") for f in filas for m in monitores(f)),
        "Teclado (marca)": reparto(marca(f.get("teclado")) for f in filas),
        "Teclado (modelo)": reparto((primero(f.get("teclado")) for f in filas), TOP),
        "Ratón (marca)": reparto(marca(f.get("raton")) for f in filas),
        "Ratón (modelo)": reparto((primero(f.get("raton")) for f in filas), TOP),
        "Conexión a internet": reparto(f.get("red_tipo") for f in filas),
        "Velocidad de bajada": reparto(tramo(numero(f.get("red_bajada_mbps")), [10, 50, 100, 300, 600, 1000, 2500], "Mb/s") for f in filas),
        "Velocidad de subida": reparto(tramo(numero(f.get("red_subida_mbps")), [5, 20, 50, 100, 300, 600, 1000], "Mb/s") for f in filas),
        "Ping": reparto(tramo(numero(f.get("red_ping_ms")), [10, 20, 40, 60, 100, 150], "ms") for f in filas),
        "Memoria virtual": reparto(("Desactivada" if (numero(f.get("memoria_virtual_gb")) or 0) == 0 else "Automática" if f.get("memoria_virtual_auto") == "si" else "Manual") for f in filas if f.get("memoria_virtual_gb") not in (None, "")),
        "País": reparto((f.get("pais") for f in filas), 30),
        "Número de pantallas": reparto(str(len([p for p in str(f.get("pantallas") or "").split(",") if p.strip()])) for f in filas if f.get("pantallas")),
    }
    salida = {"equipos": len(filas), "dias": DIAS_ACTIVO, "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "categorias": categorias}
    (AQUI / "hardware.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    md = [f"# Hardware de los usuarios de Arlequin GameHub\n",
          f"{len(filas)} equipos con \"Ayuda a mejorar Arlequin\" activado (últimos {DIAS_ACTIVO} días). "
          f"Actualizado el {salida['actualizado']}. Solo porcentajes: ningún dato identifica a nadie.\n"]
    for nombre, lista in categorias.items():
        if not lista:
            continue
        md.append(f"\n## {nombre}\n\n| | % | Equipos |\n|---|---:|---:|")
        md += [f"| {x['valor']} | {x['porcentaje']} % | {x['equipos']} |" for x in lista]
    (AQUI / "HARDWARE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(len(filas), "equipos")


if __name__ == "__main__":
    main()
