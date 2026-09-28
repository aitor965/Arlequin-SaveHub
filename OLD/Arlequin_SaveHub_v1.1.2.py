# -*- coding: utf-8 -*-
"""
Arlequin SaveHub by nox.bat

Cambio principal respecto a la versión anterior:
  - Ya NO se escanean carpetas a ciegas ni se cruzan nombres con carpetas
    "habituales" (Documents, My Games, Saved Games, AppData...).
  - Se consultan las APIs/registros de Steam, Epic, GOG, Battle.net,
    Ubisoft, EA app/Origin, Amazon Games y Xbox/Microsoft Store (UWP)
    para saber qué juegos están INSTALADOS (y dónde).
  - Para cada juego instalado se consulta la base de datos propia del
    proyecto (id y ubicacion saves.yaml, repositorio Arlequin-SaveHub)
    para saber EXACTAMENTE dónde guarda sus partidas cada plataforma, y esa
    ruta se resuelve a una carpeta real del equipo.
  - Al arrancar, la app se abre primero (ventana visible) y SOLO DESPUÉS,
    en segundo plano, se descarga/actualiza la base de datos de Ludusavi.
"""

import os
import sys
import re
import json
import sqlite3
import time
import gzip
import glob
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
import webbrowser
import subprocess
import logging
import uuid
from datetime import datetime
from difflib import SequenceMatcher
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import messagebox as mb
from tkinter import filedialog as fd
from tkinter import simpledialog as sd

try:
    import winreg
    _ES_WINDOWS = True
except ImportError:
    _ES_WINDOWS = False  # por si se abre el archivo fuera de Windows

try:
    import yaml
except ImportError:
    try:
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "--quiet"])
        import yaml
    except Exception:
        yaml = None  # si no se puede instalar, el manifest no se podrá leer


DESKTOP_PATH = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop').replace("\\", "/")
if not os.path.exists(DESKTOP_PATH):
    DESKTOP_PATH = os.path.expanduser("~/Desktop").replace("\\", "/")

APP_GAMESAVES_DIR = os.path.join(os.getenv('LOCALAPPDATA') or os.path.expanduser("~"), 'APP GameSaves').replace("\\", "/")
if not os.path.exists(APP_GAMESAVES_DIR):
    os.makedirs(APP_GAMESAVES_DIR, exist_ok=True)

BKP = os.path.join(DESKTOP_PATH, 'Backup Saves').replace("\\", "/")
if not os.path.exists(BKP):
    os.makedirs(BKP, exist_ok=True)
UP = os.environ.get('USERPROFILE', os.path.expanduser('~')).replace("\\", "/")
M_O = os.path.join(APP_GAMESAVES_DIR, "juegos_ocultos.txt").replace("\\", "/")
M_M = os.path.join(APP_GAMESAVES_DIR, "juegos_manuales.txt").replace("\\", "/")
M_C = os.path.join(APP_GAMESAVES_DIR, "carpetas_sin_launcher.txt").replace("\\", "/")
# NUEVO: configuración general de la app (por ahora solo el máximo de copias
# históricas por juego, ver rotar_a_old / _purgar_backups_historicos_antiguos).
M_CFG = os.path.join(APP_GAMESAVES_DIR, "config.json").replace("\\", "/")
LOG_FILE = os.path.join(APP_GAMESAVES_DIR, "app.log").replace("\\", "/")

# ---------------------------------------------------------------------------
#  ICONO DE LA APLICACIÓN (barra de título + barra de tareas de Windows)
# ---------------------------------------------------------------------------
# getattr(sys, "_MEIPASS", ...) es la carpeta temporal donde PyInstaller
# descomprime los recursos cuando el programa se ejecuta como un .exe
# empaquetado con --onefile. Si no existe (ejecución normal del .py), se usa
# la carpeta donde vive este propio script. Así "icono.ico" se encuentra
# tanto en desarrollo como una vez compilado, sin tocar nada.
_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(_BASE_DIR, "icono.ico").replace("\\", "/")

# ---------------------------------------------------------------------------
#  BASE DE DATOS DE RUTAS DE SAVES (base propia de Arlequin-SaveHub)
# ---------------------------------------------------------------------------
# Formato: una LISTA de fichas (no un diccionario como el manifest.yaml
# original de Ludusavi). Cada ficha tiene:
#   name: "Nombre del juego"
#   ids:
#     steam: 12345          (opcional)
#     steamExtra: [111,222] (opcional, IDs de Steam adicionales del mismo juego)
#     gog: 67890             (opcional)
#     gogExtra: [333]        (opcional)
#     lutris: slug           (opcional, no se usa aquí)
#     flatpak: id            (opcional, no se usa aquí)
#   save_locations:
#     - "<plantilla>/de/ruta [os=windows, store=steam]"
#   acronyms: "alias1, alias2, ..."  (opcional, NUEVO: alias/acrónimos
#     alternativos del juego separados por comas, p. ej. "AoE2, AoE, AoEII".
#     Se indexan igual que "name" para mejorar la detección cuando el
#     launcher -EA app, Amazon Games, Xbox...- reporta el juego con un
#     nombre distinto al oficial.)
# Las condiciones entre corchetes al final de cada ruta son opcionales; si
# faltan, la ruta se considera válida siempre. Varios valores de la misma
# clave (p. ej. "os=windows, os=linux") son un OR; claves distintas dentro
# del mismo corchete son un AND.
MANIFEST_URL = ("https://raw.githubusercontent.com/loco965/Arlequin-SaveHub/refs/heads/main/ArlequinGameDB.yaml")
MANIFEST_CACHE = os.path.join(APP_GAMESAVES_DIR, "ArlequinGameDB.yaml").replace("\\", "/")
# NOTA: ya no hay un temporizador de "refrescar cada X días" a ciegas. En
# cada arranque se comprueba contra GitHub con ETag / If-None-Match (ver
# descargar_manifest): si el YAML no ha cambiado, la respuesta es un 304
# Not Modified de 0 bytes, así que comprobarlo siempre sale gratis.

# Caché del YAML ya parseado e indexado (manifest + los tres índices de
# construir_indices_manifest), para no tener que volver a hacer yaml.load()
# sobre el archivo completo (~84.000 líneas) en cada arranque. Solo se
# regenera cuando cambia la "firma" (tamaño + fecha de modificación) del
# YAML de origen, es decir, cuando se ha descargado una versión nueva.
MANIFEST_PARSED_CACHE = os.path.join(APP_GAMESAVES_DIR, "ArlequinGameDB_parsed.json").replace("\\", "/")

# ETag devuelto por GitHub en la última descarga correcta del YAML. Se manda
# de vuelta como cabecera If-None-Match en la siguiente comprobación: si el
# archivo remoto no ha cambiado, GitHub responde 304 Not Modified (0 bytes,
# prácticamente instantáneo) en vez de tener que volver a mandar el YAML
# entero (comprimido o no) solo para comprobar si hace falta actualizarlo.
MANIFEST_ETAG_CACHE = os.path.join(APP_GAMESAVES_DIR, "ArlequinGameDB.etag").replace("\\", "/")

# ---------------------------------------------------------------------------
#  VERSIÓN Y AUTOACTUALIZACIÓN (contra un version.json en el propio repo)
# ---------------------------------------------------------------------------

APP_VERSION = "1.1.2"

# Debe apuntar a un fichero "version.json" en la raíz del repo con este
# formato (el mismo que ya tienes preparado):
#   {
#     "version": "1.0.1",
#     "url_descarga": "https://github.com/loco965/Arlequin-SaveHub/releases/latest/download/Arlequin_SaveHub.exe",
#     "novedades": "Texto que se muestra al usuario"
#   }
VERSION_CHECK_URL = ("https://raw.githubusercontent.com/loco965/Arlequin-SaveHub/refs/heads/main/version.json")


def _version_a_tupla(texto_version):
    """Convierte '1.2.10' (o 'v1.2.10') en (1, 2, 10) para poder comparar
    versiones numéricamente en vez de como texto."""
    partes = []
    for trozo in str(texto_version).strip().lstrip("vV").split("."):
        num = "".join(c for c in trozo if c.isdigit())
        partes.append(int(num) if num else 0)
    return tuple(partes) or (0,)


def comprobar_actualizacion_disponible():
    """Consulta VERSION_CHECK_URL. Devuelve el dict remoto (version,
    url_descarga, novedades) si hay una versión más nueva que APP_VERSION,
    o None si no hay actualización o si algo falla (sin internet, etc.)."""
    try:
        peticion = urllib.request.Request(
            VERSION_CHECK_URL,
            headers={"User-Agent": "Arlequin-SaveHub-Updater", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(peticion, timeout=8) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        version_remota = str(datos.get("version", "0.0.0"))
        if _version_a_tupla(version_remota) > _version_a_tupla(APP_VERSION):
            return datos
    except Exception as e:
        logging.info(f"No se pudo comprobar si hay actualizaciones: {e}")
    return None


def descargar_y_aplicar_actualizacion(url_descarga):
    """Descarga el nuevo .exe indicado en el version.json y, si el programa
    se está ejecutando ya compilado (PyInstaller --onefile), deja preparado
    un script que sustituye el .exe actual por el nuevo y vuelve a abrirlo
    en cuanto este proceso termine. Devuelve True si hay que cerrar la app
    ahora mismo para que la actualización se complete."""
    if not getattr(sys, "frozen", False):
        # Ejecutándose como script .py (modo desarrollo): no hay .exe que
        # reemplazar, así que solo se abre la página de descarga.
        mb.showinfo(
            "Actualización",
            "Estás ejecutando el código fuente (.py), no el .exe compilado.\n"
            "Se abrirá el enlace de descarga en el navegador."
        )
        webbrowser.open(url_descarga)
        return False

    exe_actual = sys.executable
    carpeta = os.path.dirname(exe_actual)
    nombre_exe_actual = os.path.basename(exe_actual)
    nuevo_exe = os.path.join(carpeta, "_Arlequin_SaveHub_nuevo.exe")

    try:
        peticion = urllib.request.Request(
            url_descarga, headers={"User-Agent": "Arlequin-SaveHub-Updater"})
        with urllib.request.urlopen(peticion, timeout=60) as resp:
            with open(nuevo_exe, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as e:
        logging.error(f"Fallo al descargar la actualización: {e}")
        try:
            if os.path.exists(nuevo_exe):
                os.remove(nuevo_exe)
        except Exception:
            pass
        mb.showerror("Actualización", f"No se pudo descargar la actualización:\n{e}")
        return False

    # Script .bat de actualización. Espera al PID EXACTO de esta instancia
    # (no al nombre del EXE, para no quedarse bloqueado si hay otra instancia),
    # reemplaza el ejecutable y lo relanza a través de Explorer.
    bat_path = os.path.join(os.environ.get("TEMP", carpeta), "arlequin_update.bat")
    pid_actual = os.getpid()
    contenido_bat = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "VIEJO={exe_actual}"\r\n'
        f'set "NUEVO={nuevo_exe}"\r\n'
        f'set "PID_ASH={pid_actual}"\r\n'
        ":esperar\r\n"
        'tasklist /FI "PID eq %PID_ASH%" 2>NUL | find /I "%PID_ASH%" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >NUL\r\n"
        "    goto esperar\r\n"
        ")\r\n"
        ":reemplazar\r\n"
        'move /Y "%NUEVO%" "%VIEJO%" >NUL 2>NUL\r\n'
        'if exist "%NUEVO%" (\r\n'
        "    timeout /t 1 /nobreak >NUL\r\n"
        "    goto reemplazar\r\n"
        ")\r\n"
        'start "" explorer.exe "%VIEJO%"\r\n'
        'del "%~f0" >NUL 2>NUL\r\n'
    )
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(contenido_bat)
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        return True
    except Exception as e:
        logging.error(f"Fallo al preparar el relanzamiento automático: {e}")
        mb.showerror(
            "Actualización",
            f"La descarga terminó pero no se pudo reiniciar automáticamente:\n{e}\n\n"
            f"El nuevo .exe quedó en:\n{nuevo_exe}"
        )
        return False

# ---------------------------------------------------------------------------
#  HILOS DE ROBOCOPY (/MT): se calculan según el hardware, no un número fijo
# ---------------------------------------------------------------------------
def _calcular_hilos_robocopy():
    """Devuelve cuántos hilos usar en la copia de robocopy (opción /MT),
    calculados a partir de los núcleos/hilos lógicos del equipo, para que la
    app rinda bien tanto en un PC viejo de 1-2 núcleos como en una CPU
    moderna de 16-24 hilos, sin tener que tocar código a mano en cada caso.

    - os.cpu_count() ya consulta internamente NUMBER_OF_PROCESSORS en
      Windows; se deja igualmente esa variable de entorno como respaldo por
      si algún entorno restringido devolviera None.
    - Equipos con 1-2 hilos: se desactiva /MT (devuelve 0). En hardware tan
      limitado, copiar en paralelo compite por la misma CPU/disco que ya
      está usando el resto del sistema y no suele compensar.
    - Resto de equipos: se usa el doble de hilos lógicos disponibles, con un
      suelo de 4 (mínimo útil de /MT) y un techo de 32. El techo no es el
      límite técnico de robocopy (que admite hasta 128), sino que a partir
      de cierto punto el cuello de botella pasa a ser el disco, no la CPU:
      más hilos ahí solo generan más contención de E/S sin backup más
      rápido, sobre todo copiando muchos archivos pequeños (típico de saves).
    """
    try:
        hilos_cpu = os.cpu_count()
        if not hilos_cpu:
            hilos_cpu = int(os.environ.get("NUMBER_OF_PROCESSORS", "4") or "4")
    except Exception:
        hilos_cpu = 4

    if hilos_cpu <= 2:
        return 0  # equipo modesto: copia clásica de un solo hilo

    return min(32, max(4, hilos_cpu * 2))


# Se calcula una sola vez al arrancar (el hardware no cambia durante la
# ejecución), así run_cmd() no repite este cálculo en cada copia.
ROBOCOPY_HILOS_MT = _calcular_hilos_robocopy()


# Cómo se llama cada launcher dentro del campo "store" del manifest de Ludusavi
LAUNCHER_A_STORE = {
    "Steam": "steam",
    "Epic": "epic",
    "GOG": "gog",
    "Ubisoft": "uplay",
    "Battle.net": None,  # Ludusavi no distingue "battlenet" como store propio
    "Xbox": "microsoft",  # juegos UWP / Xbox Game Pass para PC
    "EA": None,     # EA app / Origin: el manifest no usa una etiqueta de
                    # store propia para ellos (las rutas de guardado no
                    # suelen depender de la tienda en este caso).
    "Amazon": None, # Amazon Games / Prime Gaming: mismo caso que EA.
}

# Nombre "bonito" para mostrar en la interfaz (la clave interna sigue siendo
# "Carpeta" para toda la lógica de detección/cruce con el manifest).
NOMBRE_VISUAL_LAUNCHER = {
    "Carpeta": "Juego sin Launcher",
    "Xbox": "Xbox / Microsoft Store",
    "EA": "EA app / Origin",
    "Amazon": "Amazon Games",
}

# Herramientas/componentes de sistema que algunos launchers (sobre todo
# Steam) reportan como si fueran "juegos instalados", pero que no tienen
# partidas guardadas propias: runtimes de compatibilidad, benchmarks, etc.
# Se comparan contra el nombre ya normalizado (_norm), así que basta con que
# el texto aparezca como subcadena, sin acentos ni mayúsculas.
EXCLUSIONES_SISTEMA = [
    "steam linux runtime",
    "proton",
    "lossless scaling",
    "3dmark",
]


def _es_exclusion_sistema(nombre_norm):
    return any(patron in nombre_norm for patron in EXCLUSIONES_SISTEMA)


# Juegos 100% online cuyo progreso (inventario, rango, base, personaje...)
# vive en el servidor o en la cuenta online del jugador, no en una carpeta de
# este PC. Cada uno de estos nombres se ha verificado contra el manifest de
# Ludusavi: SÍ tienen ficha propia, pero TODAS sus rutas 'files' para Windows
# están etiquetadas solo como 'config' (ajustes/keybinds/vídeo), nunca como
# 'save' — es decir, Ludusavi ya sabe que no hay partida real que respaldar
# ahí, así que en vez de mostrarlos como "sin datos de guardado" (que puede
# confundir con un fallo de la app) se omiten directamente, igual que
# EXCLUSIONES_SISTEMA. Se comparan por nombre normalizado exacto (ver _norm).
#
# OJO: esto NO es lo mismo que la categoría "ℹ️ SIN DATOS DE GUARDADO
# CONOCIDOS" del escaneo, que se deja SIN tocar para los demás casos: esa
# categoría sirve precisamente para detectar huecos reales del manifest
# (juegos que sí guardan partida pero Ludusavi aún no lo tiene bien mapeado,
# p. ej. "Darkest Dungeon" en este mismo manifest no tiene ninguna ruta
# 'files' registrada pese a que el juego sí guarda localmente). Solo se
# añaden aquí títulos multijugador online conocidos donde no existe partida
# local que perder. Añadir más es tan sencillo como incluir aquí el nombre
# normalizado del juego, idealmente tras comprobar su ficha en el manifest.
JUEGOS_SIN_SAVE_LOCAL_CONOCIDOS = [
    "dayz",                              # progreso vive en el servidor
    "rust",                              # progreso vive en el servidor
    "counter strike",                    # shooter competitivo, sin partida
    "counter strike 2",                  # shooter competitivo, sin partida
    "counter strike global offensive",   # mismo caso, nombre "clásico" de CS2
    "killing floor 2",                   # progreso ligado a la cuenta/server
    "valorant",                          # shooter competitivo, sin partida
    "apex legends",                      # battle royale, progreso en cuenta
    "overwatch 2",                       # shooter competitivo, sin partida
    "escape from tarkov",                # progreso vive en el servidor
    "league of legends",                 # progreso en la cuenta de Riot
    "dota 2",                            # progreso en la cuenta de Steam
    "peak",                              # co-op online, sin partida real
    "the finals",                        # shooter competitivo, sin partida
    "monopoly",                          # versión Ubisoft/Game Pass (UWP),
                                          # 100% online, sin partida local
]


def _es_online_sin_save_local(nombre_norm):
    return nombre_norm in JUEGOS_SIN_SAVE_LOCAL_CONOCIDOS


# ---------------------------------------------------------------------------
#  DETECCIÓN DE JUEGOS INSTALADOS VÍA LOS LAUNCHERS
# ---------------------------------------------------------------------------

def _norm(s):
    """Normaliza un nombre de juego para comparar (minúsculas, sin símbolos)."""
    s = (s or "").lower()
    # 1) apóstrofos/acentos: se ELIMINAN (Baldur's -> baldurs)
    for ch in "'’´`´":
        s = s.replace(ch, "")
    # 2) resto de símbolos: se convierten en espacio (Cyberpunk™: -> cyberpunk )
    for ch in "™®©\":;.,_-–—!?()[]{}&+~^|/\\":
        s = s.replace(ch, " ")
    return " ".join(s.split())


# Sufijos que identifican una edición/remaster de un mismo juego. Se usan
# únicamente para evitar que una carpeta vieja de la edición anterior sea
# tomada como instalación actual cuando el launcher sí tiene instalada otra
# edición del mismo título (p. ej. GTA V frente a GTA V Enhanced).
_SUFIJOS_EDICION_JUEGO = (
    " enhanced", " remastered", " definitive edition", " complete edition",
    " game of the year", " goty", " redux", " director's cut",
    " special edition", " ultimate edition", " anniversary edition",
)


def _es_edicion_derivada_del_mismo_juego(base_norm, instalado_norm):
    """True si instalado_norm parece una edición derivada de base_norm."""
    if not base_norm or not instalado_norm or base_norm == instalado_norm:
        return False
    if not instalado_norm.startswith(base_norm + " "):
        return False
    sufijo = instalado_norm[len(base_norm):]
    return any(sufijo == s or sufijo.startswith(s + " ") for s in _SUFIJOS_EDICION_JUEGO)


# ---------------------------------------------------------------------------
#  MANIFEST DE LUDUSAVI: descarga, índice y resolución de rutas de saves
# ---------------------------------------------------------------------------

def _leer_etag_guardado():
    """Devuelve el ETag guardado de la última descarga correcta del YAML, o
    None si no hay ninguno (primera vez, o se ha borrado la caché)."""
    try:
        with open(MANIFEST_ETAG_CACHE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def _guardar_etag(etag):
    """Guarda el ETag que ha devuelto GitHub junto con la última descarga
    correcta, para poder mandarlo como If-None-Match la próxima vez."""
    if not etag:
        return
    try:
        os.makedirs(os.path.dirname(MANIFEST_ETAG_CACHE), exist_ok=True)
        with open(MANIFEST_ETAG_CACHE, "w", encoding="utf-8") as f:
            f.write(etag)
    except Exception:
        pass


def _firma_archivo(ruta):
    """Firma barata (tamaño + fecha de modificación) del YAML en disco, para
    saber si ha cambiado desde la última vez que se parseó sin tener que
    leer ni procesar el archivo entero."""
    try:
        st = os.stat(ruta)
        return f"{st.st_size}-{int(st.st_mtime)}"
    except Exception:
        return None


def _cargar_cache_parseada(firma_actual):
    """Si existe una caché ya parseada e indexada y corresponde exactamente
    a la firma del YAML actual, la devuelve como
    (manifest, total_juegos, por_nombre, por_steam_id, por_gog_id).
    Si no hay caché válida (no existe, está corrupta o el YAML cambió),
    devuelve None."""
    try:
        with open(MANIFEST_PARSED_CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("firma") != firma_actual:
            return None
        manifest = cache.get("manifest") or {}
        total_juegos = cache.get("total_juegos", len(manifest))
        indices = cache.get("indices") or {}
        return (
            manifest,
            total_juegos,
            indices.get("por_nombre") or {},
            indices.get("por_steam_id") or {},
            indices.get("por_gog_id") or {},
        )
    except Exception:
        return None


def _guardar_cache_parseada(firma_actual, manifest, total_juegos, por_nombre, por_steam_id, por_gog_id):
    """Guarda en disco el manifest ya parseado junto a sus índices, para que
    el próximo arranque (mientras el YAML no cambie) no tenga que volver a
    parsear ni a indexar nada."""
    try:
        os.makedirs(os.path.dirname(MANIFEST_PARSED_CACHE), exist_ok=True)
        contenido = {
            "firma": firma_actual,
            "total_juegos": total_juegos,
            "manifest": manifest,
            "indices": {
                "por_nombre": por_nombre,
                "por_steam_id": por_steam_id,
                "por_gog_id": por_gog_id,
            },
        }
        temporal = MANIFEST_PARSED_CACHE + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False)
        os.replace(temporal, MANIFEST_PARSED_CACHE)
    except Exception:
        # Si no se puede escribir la caché no pasa nada grave: simplemente
        # el próximo arranque volverá a parsear el YAML.
        pass


def _normalizar_manifest(datos_yaml):
    """Convierte lo que ha devuelto yaml.load() (dict o lista de fichas) al
    diccionario {nombre_juego: ficha} con el que trabaja el resto de la app,
    junto con el número real de fichas de juego que contenía el YAML."""
    if isinstance(datos_yaml, dict):
        # Si el YAML viene como diccionario {nombre: ficha}, cada clave
        # representa una entrada de juego.
        return (datos_yaml or {}), len(datos_yaml or {})

    # El número mostrado en la interfaz debe corresponder a la cantidad
    # real de fichas de juegos que contiene el YAML, no a len(manifest).
    # Esto es importante porque el diccionario puede eliminar duplicados
    # de nombre al indexarlo.
    manifest = {}
    total_juegos = 0
    for ficha in datos_yaml or []:
        if not isinstance(ficha, dict):
            continue
        nombre_juego = ficha.get("name")
        if not nombre_juego:
            continue
        total_juegos += 1
        manifest[nombre_juego] = ficha
    return manifest, total_juegos


def descargar_manifest(forzar=False):
    """Descarga (o reutiliza la caché en disco) la base de datos de rutas de
    saves de Arlequin-SaveHub y la normaliza a un diccionario
    {nombre_juego: ficha}, que es el formato con el que trabaja el resto de
    la app (self.manifest). Devuelve también los tres índices de
    construir_indices_manifest, reutilizando una caché ya parseada e
    indexada en disco cuando el YAML no ha cambiado desde la última vez.

    forzar=True (botón "actualizar ahora") hace una descarga completa,
    ignorando el ETag guardado, para garantizar un YAML fresco de verdad.
    Con forzar=False (arranque normal) se comprueba igualmente contra
    GitHub en CADA arranque, pero mandando el ETag guardado como
    If-None-Match: si el YAML remoto no ha cambiado, la respuesta es un
    304 Not Modified de 0 bytes y prácticamente instantánea, así que
    comprobarlo siempre no penaliza el rendimiento y evita depender de un
    temporizador ciego de varios días para enterarse de cambios."""
    existe_cache_local = os.path.exists(MANIFEST_CACHE)
    try:
        # Se comprueba SIEMPRE contra GitHub, tanto si hay caché local como
        # si no, y tanto si se fuerza como si no: como es una petición
        # condicional (If-None-Match) cuando hay ETag guardado, si nada ha
        # cambiado cuesta 0 bytes de cuerpo y responde casi al instante, así
        # que no hace falta un temporizador de varios días para decidir si
        # merece la pena preguntar.
        # La URL debe apuntar al archivo real del repositorio. Descargamos
        # primero a un temporal y solo sustituimos la caché cuando la
        # descarga termina correctamente, para no dejar un YAML corrupto
        # si se corta la conexión.
        cabeceras = {
            "User-Agent": "Arlequin-SaveHub/1.0",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
            # Pedimos gzip explícitamente: urllib no lo hace por defecto
            # (a diferencia de un navegador o de "requests"), así que sin
            # esta cabecera GitHub siempre manda el YAML sin comprimir.
            "Accept-Encoding": "gzip",
        }
        # Si NO se ha forzado el refresco y ya tenemos una copia local
        # con su ETag de la última descarga correcta, se manda como
        # If-None-Match para poder recibir un 304 si no ha cambiado.
        # Con forzar=True se omite a propósito: el usuario quiere una
        # descarga completa de verdad, no una comprobación condicional.
        etag_guardado = _leer_etag_guardado() if not forzar else None
        if etag_guardado and existe_cache_local:
            cabeceras["If-None-Match"] = etag_guardado

        peticion = urllib.request.Request(MANIFEST_URL, headers=cabeceras)
        datos = None
        etag_nuevo = None
        try:
            with urllib.request.urlopen(peticion, timeout=60) as resp:
                datos = resp.read()
                if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                    # gzip.decompress() existe en la librería estándar
                    # desde Python 3.2 y descomprime directamente un
                    # bloque de bytes en memoria; no hace falta pasar
                    # por io.BytesIO + gzip.GzipFile a mano.
                    datos = gzip.decompress(datos)
                etag_nuevo = resp.headers.get("ETag")
        except urllib.error.HTTPError as http_err:
            if http_err.code == 304:
                # Sin cambios desde la última descarga: no hace falta
                # tocar el YAML local ni la caché ya parseada (que sigue
                # siendo válida, porque su firma -tamaño+fecha- no ha
                # cambiado). No se actualiza la fecha del archivo a
                # propósito, para no interferir con esa firma.
                datos = None
            else:
                raise

        if datos is not None:
            if not datos or len(datos) < 100:
                raise ValueError("GitHub devolvió un archivo vacío o incompleto")

            # Comprobación básica antes de reemplazar la caché: el archivo
            # debe parecer realmente un YAML de fichas con campo "name".
            if b"name:" not in datos:
                raise ValueError("La respuesta descargada no parece ser el YAML de juegos esperado")

            os.makedirs(os.path.dirname(MANIFEST_CACHE), exist_ok=True)
            temporal = MANIFEST_CACHE + ".tmp"
            with open(temporal, "wb") as f:
                f.write(datos)
            os.replace(temporal, MANIFEST_CACHE)
            _guardar_etag(etag_nuevo)
    except Exception:
        # Si falla la comprobación/descarga (sin internet, timeout, etc.) se
        # conserva la caché local tal cual estaba. Si no existe ninguna, la
        # función devolverá {}, 0 y la interfaz informará del fallo.
        try:
            if os.path.exists(MANIFEST_CACHE + ".tmp"):
                os.remove(MANIFEST_CACHE + ".tmp")
        except Exception:
            pass

    if yaml is None or not os.path.exists(MANIFEST_CACHE):
        return {}, 0, {}, {}, {}

    firma_actual = _firma_archivo(MANIFEST_CACHE)

    # 1) Intentar reutilizar la caché ya parseada e indexada: si el YAML no
    #    ha cambiado (firma igual: mismo tamaño y fecha), nos ahorramos
    #    yaml.load() y construir_indices_manifest() por completo. Como la
    #    comprobación contra GitHub de arriba normalmente responde 304 y no
    #    toca el archivo local, esto cubre la inmensa mayoría de arranques.
    if firma_actual is not None:
        cache_parseada = _cargar_cache_parseada(firma_actual)
        if cache_parseada is not None:
            return cache_parseada

    # 2) No hay caché parseada válida: hay que leer el YAML entero. Se usa
    #    CSafeLoader (basado en libyaml, en C) si está disponible, que puede
    #    ser de 10x a 100x más rápido que el SafeLoader puro-Python; si no
    #    está instalado libyaml, se cae automáticamente al loader normal.
    try:
        Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

        with open(MANIFEST_CACHE, "r", encoding="utf-8") as f:
            datos_yaml = yaml.load(f, Loader=Loader)
    except Exception:
        return {}, 0, {}, {}, {}

    manifest, total_juegos = _normalizar_manifest(datos_yaml)
    por_nombre, por_steam_id, por_gog_id = construir_indices_manifest(manifest)

    # 3) Guardar el resultado ya parseado e indexado para que, mientras el
    #    YAML no vuelva a cambiar, los próximos arranques no toquen el YAML.
    if firma_actual is not None:
        _guardar_cache_parseada(
            firma_actual, manifest, total_juegos, por_nombre, por_steam_id, por_gog_id)

    return manifest, total_juegos, por_nombre, por_steam_id, por_gog_id


def construir_indices_manifest(manifest):
    """Crea diccionarios de búsqueda rápida: por nombre normalizado (incluyendo
    los alias declarados en 'acronyms'), por ID de Steam y por ID de GOG, para
    poder localizar la ficha de cada juego."""
    por_nombre, por_steam_id, por_gog_id = {}, {}, {}
    for nombre_juego, datos in manifest.items():
        if not isinstance(datos, dict):
            continue
        clave = _norm(nombre_juego)
        if clave and clave not in por_nombre:
            por_nombre[clave] = nombre_juego
        # NUEVO: el YAML de Arlequin-SaveHub añade un campo opcional
        # "acronyms" con alias/acrónimos alternativos separados por comas
        # (p. ej. "AoE2, AoE, AoEII"). Se indexan igual que el nombre
        # principal para que un juego reportado por el launcher (EA app,
        # Amazon Games, Xbox...) con un nombre distinto al oficial también
        # se localice. setdefault evita pisar la clave si ya pertenece a
        # otro juego (por nombre real o por otro acrónimo), para no cruzar
        # fichas por una coincidencia de alias ambigua.
        acronimos = datos.get("acronyms")
        if acronimos:
            for alias in str(acronimos).split(","):
                clave_alias = _norm(alias)
                if clave_alias:
                    por_nombre.setdefault(clave_alias, nombre_juego)
        ids = datos.get("ids") or {}
        try:
            steam_id = ids.get("steam")
            if steam_id:
                por_steam_id.setdefault(str(steam_id), nombre_juego)
            for extra_id in ids.get("steamExtra") or []:
                por_steam_id.setdefault(str(extra_id), nombre_juego)
        except Exception:
            pass
        try:
            gog_id = ids.get("gog")
            if gog_id:
                por_gog_id.setdefault(str(gog_id), nombre_juego)
            for extra_id in ids.get("gogExtra") or []:
                por_gog_id.setdefault(str(extra_id), nombre_juego)
        except Exception:
            pass
    return por_nombre, por_steam_id, por_gog_id


def obtener_steam_path():
    """Ruta raíz de instalación de Steam (donde vive la carpeta userdata)."""
    if not _ES_WINDOWS:
        return None
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
        winreg.CloseKey(key)
        return steam_path.replace("\\", "/")
    except Exception:
        return None


def obtener_steam_user_ids(steam_path):
    """IDs numéricos (carpetas) de cuentas de Steam usadas localmente en este PC."""
    ids = []
    if not steam_path:
        return ids
    userdata = os.path.join(steam_path, "userdata")
    if os.path.isdir(userdata):
        for nombre in os.listdir(userdata):
            if nombre.isdigit():
                ids.append(nombre)
    return ids


def obtener_windows_documents():
    """Devuelve la carpeta real de Documentos de Windows.

    No se asume que sea %USERPROFILE%\\Documents: Windows permite redirigir
    las Known Folders (por ejemplo a OneDrive u otra unidad). Se usa
    SHGetKnownFolderPath cuando estamos en Windows y se mantiene un fallback
    sencillo para entornos donde la API no esté disponible.
    """
    fallback = os.path.join(UP, "Documents")
    if not _ES_WINDOWS:
        return fallback.replace("\\", "/")
    try:
        import ctypes
        from ctypes import wintypes
        # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD),
                        ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD),
                        ("Data4", wintypes.BYTE * 8)]

        guid = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                    (wintypes.BYTE * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        path_ptr = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))
        if hr == 0 and path_ptr.value:
            ruta = path_ptr.value
            ole32.CoTaskMemFree(path_ptr)
            if os.path.isdir(ruta):
                return ruta.replace("\\", "/")
            return ruta.replace("\\", "/")
    except Exception:
        pass
    return fallback.replace("\\", "/")


def _abrir_clave_ubisoft_launcher():
    """Abre la clave del launcher de Ubisoft probando las vistas de registro
    de 32 y 64 bits. Devuelve (key, root_key_name) o (None, None)."""
    if not _ES_WINDOWS:
        return None, None
    rutas = [r"SOFTWARE\Ubisoft\Launcher",
             r"SOFTWARE\WOW6432Node\Ubisoft\Launcher"]
    vistas = []
    try:
        vistas = [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]
    except AttributeError:
        vistas = [0]
    vistas = list(dict.fromkeys(vistas))
    for ruta in rutas:
        for vista in vistas:
            try:
                return winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta, 0,
                                      winreg.KEY_READ | vista), ruta
            except Exception:
                continue
    return None, None


def obtener_ubisoft_root():
    """Obtiene la carpeta de instalación de Ubisoft Connect, que es la raíz
    que usa el manifest para rutas del tipo <root>/savegames/... .
    No debe confundirse con la carpeta donde está instalado cada juego."""
    if not _ES_WINDOWS:
        return ""
    key, _ = _abrir_clave_ubisoft_launcher()
    if key is None:
        return ""
    try:
        for valor in ("InstallDir", "InstallPath", "Path"):
            try:
                ruta = winreg.QueryValueEx(key, valor)[0]
                if ruta:
                    ruta = os.path.abspath(str(ruta)).replace("\\", "/")
                    if os.path.isdir(ruta):
                        return ruta
            except Exception:
                continue
    finally:
        try:
            winreg.CloseKey(key)
        except Exception:
            pass
    return ""


def obtener_ubisoft_user_ids(ubisoft_root):
    """Enumera las carpetas de cuentas existentes bajo Ubisoft\\savegames.
    Ubisoft no necesita que asumamos que el identificador de usuario sea
    numérico, así que se conserva cualquier nombre de carpeta válido."""
    if not ubisoft_root:
        return []
    raiz = os.path.join(ubisoft_root, "savegames")
    try:
        return [e.name.replace("\\", "/") for e in os.scandir(raiz) if e.is_dir()]
    except Exception:
        return []


def entorno_windows_base():
    """Valores fijos de las carpetas estándar de Windows usadas como
    placeholders en las rutas del manifest de Ludusavi."""
    home = UP
    return {
        "home": home,
        "winAppData": (os.environ.get("APPDATA") or "").replace("\\", "/"),
        "winLocalAppData": (os.environ.get("LOCALAPPDATA") or "").replace("\\", "/"),
        "winDocuments": obtener_windows_documents(),
        "winPublic": (os.environ.get("PUBLIC") or "C:/Users/Public").replace("\\", "/"),
        "winProgramData": (os.environ.get("PROGRAMDATA") or "C:/ProgramData").replace("\\", "/"),
        "winDir": (os.environ.get("WINDIR") or "C:/Windows").replace("\\", "/"),
        "osUserName": os.environ.get("USERNAME") or "",
    }


def _sustituir_placeholders(plantilla, contexto):
    """Sustituye los placeholders (<base>, <home>, <winAppData>...) de una
    ruta del manifest por rutas reales del equipo, SIN recortar todavía
    ningún comodín. Devuelve una lista (porque <storeUserId> puede generar
    varias rutas candidatas, una por cuenta), con los "*"/"{...}" que
    tuviera la plantilla original tal cual, listos tanto para glob.glob()
    (ver _buscar_carpeta_real_por_comodin) como para recortar
    (ver resolver_plantilla_ruta)."""
    p = plantilla.replace("\\", "/")

    reemplazos_simples = {
        "<home>": contexto.get("home", ""),
        "<root>": contexto.get("root", ""),
        "<base>": contexto.get("base", ""),
        "<winAppData>": contexto.get("winAppData", ""),
        "<winLocalAppData>": contexto.get("winLocalAppData", ""),
        "<winDocuments>": contexto.get("winDocuments", ""),
        "<winPublic>": contexto.get("winPublic", ""),
        "<winProgramData>": contexto.get("winProgramData", ""),
        "<winDir>": contexto.get("winDir", ""),
        "<osUserName>": contexto.get("osUserName", ""),
    }
    for marcador, valor in reemplazos_simples.items():
        if valor and marcador in p:
            p = p.replace(marcador, valor)

    # placeholders de Linux/Mac que no pintan nada en un equipo Windows
    if "<xdgData>" in p or "<xdgConfig>" in p or "<xdgCache>" in p:
        return []

    candidatos = [p]
    if "<storeUserId>" in p:
        ids_posibles = contexto.get("storeUserIds") or []
        if ids_posibles:
            # Primero probamos las cuentas que el launcher conoce.
            candidatos = [p.replace("<storeUserId>", uid) for uid in ids_posibles]
            # IMPORTANTE: algunas rutas de guardado usan el SteamID64/ID de
            # cuenta aunque esa cuenta concreta ya no aparezca bajo
            # Steam\\userdata (por ejemplo, Steam se reinstaló, se cambió de
            # instalación o el save es de una cuenta usada anteriormente).
            # En ese caso hacemos un segundo intento mediante un comodín REAL.
            # El comodín solo será válido si existe la carpeta completa en
            # disco, así que NO se convierte nunca en la carpeta contenedora.
            candidatos.append(p.replace("<storeUserId>", "*"))
        else:
            # No conocemos el ID. Conservamos un comodín REAL para que
            # resolver_plantilla_ruta() lo busque en disco. No se recorta al
            # padre: solo una coincidencia existente y concreta puede validar
            # la ruta. Esto evita falsos positivos masivos en Steam/Ubisoft.
            candidatos = [p.replace("<storeUserId>", "*")]

    # Las rutas restantes deben estar totalmente resueltas (sin placeholders).
    candidatos = [c for c in candidatos if "<" not in c and ">" not in c]
    return candidatos


def resolver_plantilla_ruta(plantilla, contexto):
    """Resuelve una ruta del manifest contra el equipo real.

    Las rutas sin comodines se devuelven directamente. Las que contienen
    '*'/'{...}' se expanden con glob y SOLO se devuelven coincidencias que
    existen en disco. Si la coincidencia es un archivo, se devuelve su carpeta
    para que el backup siga trabajando a nivel de directorio.

    Es importante no recortar un comodín a su carpeta padre: hacerlo con
    '<root>/userdata/<storeUserId>/1346840/remote' produciría simplemente
    '.../userdata' y haría aparecer cientos de juegos que no están instalados.
    """
    resultado = []
    for c in _sustituir_placeholders(plantilla, contexto):
        c = c.replace("\\", "/")
        tiene_comodin = "*" in c or "{" in c
        if not tiene_comodin:
            if os.path.isdir(c) or os.path.isfile(c):
                ruta_final = c if os.path.isdir(c) else os.path.dirname(c)
                if ruta_final and ruta_final not in resultado:
                    resultado.append(ruta_final.rstrip("/"))
            else:
                # Se conserva la ruta aunque todavía no exista: el llamador
                # puede mostrarla como "prevista" cuando el juego sí está
                # instalado.
                if c.rstrip("/") and c.rstrip("/") not in resultado:
                    resultado.append(c.rstrip("/"))
            continue

        patron_glob = re.sub(r"\{[^}]*\}", "*", c)
        try:
            coincidencias = glob.glob(patron_glob)
        except Exception:
            coincidencias = []
        for coincidencia in coincidencias:
            coincidencia = coincidencia.replace("\\", "/")
            if os.path.isdir(coincidencia):
                ruta_final = coincidencia
            elif os.path.isfile(coincidencia):
                ruta_final = os.path.dirname(coincidencia)
            else:
                continue
            ruta_final = ruta_final.rstrip("/")
            if ruta_final and ruta_final not in resultado:
                resultado.append(ruta_final)
    return resultado


# ---------------------------------------------------------------------------
#  PROTECCIÓN CONTRA CARPETAS "CONTENEDORAS" COMPARTIDAS POR TODOS LOS JUEGOS
# ---------------------------------------------------------------------------
# Cuando una plantilla del manifest resuelve a una carpeta compartida por
# TODOS los juegos (Documents/My Games, AppData, o incluso el perfil entero
# del usuario con <home>), tratarla como "la carpeta de guardado de este
# juego" es siempre un error: o bien falta un trozo de ruta en la ficha del
# manifest (p. ej. un <home> suelto, sin subcarpeta), o bien un comodín
# parcial dentro de un nombre de carpeta (p. ej. "Super DX-Ball *") se ha
# recortado hasta el "My Games" de TODOS los juegos en vez de encontrar la
# carpeta real de ESTE juego. En ambos casos, usar esa carpeta compartida
# significaría respaldar/restaurar los saves de todos los demás juegos (o
# el perfil de Windows entero) en vez de los de un solo título.
def _carpetas_contenedoras_compartidas(entorno):
    """Devuelve, ya normalizadas, las carpetas "paraguas" que jamás deben
    aceptarse como la carpeta de guardado de un juego concreto."""
    home = entorno.get("home", "")
    documentos = entorno.get("winDocuments", "")
    app_data = entorno.get("winAppData", "")
    local_app_data = entorno.get("winLocalAppData", "")

    candidatas = [
        home,
        documentos,
        app_data,
        local_app_data,
        (local_app_data + "Low") if local_app_data else "",
        os.path.dirname(app_data) if app_data else "",  # .../AppData (Local+Roaming+LocalLow)
        os.path.join(documentos, "My Games") if documentos else "",
        os.path.join(home, "Saved Games") if home else "",
        os.path.join(home, "Desktop") if home else "",
        entorno.get("winPublic", ""),
        entorno.get("winProgramData", ""),
        entorno.get("winDir", ""),
        "C:/Program Files",
        "C:/Program Files (x86)",
        # Contenedores multi-juego usados por Steam y Ubisoft Connect.
        # Nunca deben aceptarse como el save de un título concreto.
        (os.path.join(entorno.get("root", ""), "userdata")
         if entorno.get("root") else ""),
        (os.path.join(entorno.get("root", ""), "savegames")
         if entorno.get("root") else ""),
        # IsolatedStorage (Local y Roaming): almacén genérico de .NET/
        # Silverlight/ClickOnce compartido por CUALQUIER programa que lo use,
        # no solo un juego concreto. Plantillas con varios comodines
        # seguidos justo después de "IsolatedStorage" (p. ej.
        # ".../IsolatedStorage/*/*/Url.*/.../<storeUserId>.xml") se recortan
        # aquí si no se encuentra una coincidencia real más específica.
        os.path.join(local_app_data, "IsolatedStorage") if local_app_data else "",
        os.path.join(app_data, "IsolatedStorage") if app_data else "",
        # Packages (UWP/Microsoft Store): carpeta contenedora de TODAS las
        # apps de la Microsoft Store instaladas en el equipo (Xbox Game
        # Pass, Windows Store...), no de un juego en concreto. Las rutas
        # del manifest para juegos de Xbox/Microsoft siempre incluyen un
        # comodín con el nombre del paquete (p. ej.
        # ".../Packages/Estudio.Juego_*/SystemAppData/wgs"); si ese
        # comodín no encuentra ya la carpeta real del paquete instalado
        # (ver _buscar_carpeta_real_por_comodin), quedarse con "Packages"
        # a secas detectaría CUALQUIER juego de Xbox como si estuviera
        # instalado con solo tener la Microsoft Store en el equipo.
        os.path.join(local_app_data, "Packages") if local_app_data else "",
        # Public/Documents/Steam: carpeta que Steam usa para el
        # almacenamiento local de "Steam Cloud" de varios juegos a la vez,
        # organizada por cuenta (<storeUserId>) y luego por appid. Cuando
        # no se conoce el <storeUserId> de la cuenta, el comodín se recorta
        # hasta aquí, y esta carpeta ya existe en cualquier PC donde algún
        # juego (el que sea) haya usado alguna vez este método de guardado:
        # aceptarla tal cual detectaría cualquier otro juego que también
        # use este mismo patrón como si tuviera guardado un save real.
        os.path.join(entorno.get("winPublic", ""), "Documents", "Steam")
        if entorno.get("winPublic") else "",
    ]
    # la raíz de la unidad donde vive el perfil del usuario (p. ej. "C:/")
    if home and len(home) >= 2 and home[1] == ":":
        candidatas.append(home[:2] + "/")

    normalizadas = set()
    for c in candidatas:
        if not c:
            continue
        c_norm = os.path.normpath(c).replace("\\", "/").rstrip("/").lower()
        if c_norm:
            normalizadas.add(c_norm)
    return normalizadas


def _ruta_es_contenedor_compartido(ruta, carpetas_peligrosas):
    if not ruta:
        return False
    r_norm = os.path.normpath(ruta).replace("\\", "/").rstrip("/").lower()
    return r_norm in carpetas_peligrosas


def _buscar_carpeta_real_por_comodin(plantilla, contexto):
    """Cuando el recorte de comodines de resolver_plantilla_ruta() deja una
    carpeta compartida (p. ej. una plantilla "My Games/Super DX-Ball *" se
    queda en "My Games" al quitar el trozo con el comodín), en vez de
    rendirse o aceptar esa carpeta compartida, se intenta encontrar la
    carpeta REAL ya creada en este equipo que encaje con el patrón completo
    (p. ej. "My Games/Super DX-Ball Reloaded", si es como se llama de
    verdad la instalación de este usuario).

    Devuelve esa carpeta si existe en disco, o None si no se encuentra
    ninguna coincidencia real (en cuyo caso es preferible no localizar el
    juego por esta ruta a arriesgarse a usar la carpeta compartida)."""
    try:
        candidatos_patron = _sustituir_placeholders(plantilla, contexto)
    except Exception:
        return None

    for patron in candidatos_patron:
        if "*" not in patron and "{" not in patron:
            continue  # sin comodín no hay nada que buscar: ya se habría usado tal cual
        # glob.glob no entiende las llaves de "{random}"; se tratan como un
        # comodín de un solo nivel, igual que "*".
        patron_glob = re.sub(r"\{[^}]*\}", "*", patron)
        try:
            coincidencias = glob.glob(patron_glob)
        except Exception:
            continue
        for coincidencia in coincidencias:
            coincidencia = coincidencia.replace("\\", "/")
            candidato_final = coincidencia if os.path.isdir(coincidencia) else os.path.dirname(coincidencia)
            if candidato_final and os.path.isdir(candidato_final):
                return candidato_final
    return None


_RE_CONDICIONES_RUTA = re.compile(r'^(.*?)\s*\[([^\]]*)\]\s*$', re.S)


def _parsear_entrada_save_location(entrada):
    """Separa una entrada de 'save_locations' (formato propio de
    Arlequin-SaveHub) en la plantilla de ruta y sus condiciones os=/store=
    entre corchetes, p. ej.:
        '<winAppData>/Foo/Bar [os=windows, store=steam]'
    -> ('<winAppData>/Foo/Bar', {'os': {'windows'}, 'store': {'steam'}})
    Sin corchetes al final, devuelve la ruta tal cual y condiciones vacías
    (aplica siempre)."""
    entrada = " ".join((entrada or "").split())  # normaliza el plegado de líneas de YAML
    m = _RE_CONDICIONES_RUTA.match(entrada)
    if not m:
        return entrada.strip(), {}
    plantilla = m.group(1).strip()
    condiciones = {}
    for parte in m.group(2).split(","):
        parte = parte.strip()
        if "=" not in parte:
            continue
        clave, valor = parte.split("=", 1)
        condiciones.setdefault(clave.strip(), set()).add(valor.strip())
    return plantilla, condiciones


def condicion_aplica_en_windows(condiciones, store_actual):
    """Formato propio de Arlequin-SaveHub: un único bloque de condiciones
    entre corchetes al final de la ruta (os=..., store=...). Varios valores
    de la misma clave son un OR ('os=windows, os=linux' = Windows O Linux);
    claves distintas dentro del mismo corchete son un AND (debe cumplir el
    SO Y, si se especifica, la tienda). Sin corchetes, aplica siempre."""
    if not condiciones:
        return True
    oses = condiciones.get("os")
    if oses and "windows" not in oses:
        return False
    stores = condiciones.get("store")
    if stores and store_actual and store_actual not in stores:
        return False
    return True


def _preferir_carpeta_por_acronym(ruta, datos_juego, carpetas_peligrosas, raices_protegidas=None):
    """Busca la carpeta raíz inequívoca del juego dentro de la ruta real.

    La idea es deliberadamente simple y global: primero se localiza una ruta
    de save que exista de verdad; después se recorre esa MISMA ruta hacia
    arriba y se compara cada carpeta, con coincidencia exacta normalizada,
    contra el nombre del juego y todos sus acrónimos/alias. En cuanto aparece
    una coincidencia inequívoca, esa carpeta pasa a ser la raíz del backup.

    Ejemplo:
        .../My Games/Borderlands 4/Saved/SaveGames/7656119...
              ^^^^^^^^^^^^^^^
              coincide con el nombre del juego

    Resultado:
        .../My Games/Borderlands 4

    De esta forma se conserva TODO lo que haya dentro de la carpeta del juego
    (Config, Logs, Profiling, SaveGames, etc.), no solo la subcarpeta exacta
    donde el manifest encontró los saves.

    Importante: NO exigimos que la carpeta tenga más de un elemento. Si el
    juego solo tiene un directorio de saves, sigue siendo una raíz válida.
    Tampoco usamos coincidencias parciales: 'Borderlands' no coincide con
    'Borderlands 4', ni 'BL' con 'BL4'.

    La subida se detiene antes de cualquier contenedor compartido protegido
    (Documents, My Games, AppData, Steam\\userdata, etc.), de modo que esta
    ampliación nunca convierte una ruta concreta en un backup masivo.
    """
    if not ruta or not os.path.isdir(ruta):
        return ruta

    alias = set()
    nombre_juego = (datos_juego or {}).get("name")
    if nombre_juego:
        n = _norm(nombre_juego)
        if n:
            alias.add(n)
    for a in str((datos_juego or {}).get("acronyms") or "").split(","):
        na = _norm(a)
        if na:
            alias.add(na)
    if not alias:
        return ruta

    # Una carpeta de instalación detectada por un launcher es un límite duro:
    # si la búsqueda por nombre/acrónimo llega exactamente a ella, NO puede
    # convertirse en la raíz del backup. Esto evita casos como Delta Force
    # clásico, cuya ficha histórica usa <base>/player*.ply: el resolver puede
    # encontrar ese archivo dentro de la instalación y la lógica de acrónimo
    # podría subir hasta ".../common/Delta Force", provocando un backup de
    # toda la instalación (cientos de GB) en lugar del save.
    raices_protegidas_norm = set()
    for rp in (raices_protegidas or []):
        if rp:
            raices_protegidas_norm.add(
                os.path.normpath(rp).replace("\\", "/").rstrip("/").lower()
            )

    # Se empieza en la propia carpeta resuelta y se sube por TODOS sus
    # antepasados hasta encontrar el alias exacto más cercano. No hay un
    # límite artificial de niveles: el único freno es llegar a un contenedor
    # compartido protegido.
    actual = os.path.normpath(ruta).replace("\\", "/").rstrip("/")
    while actual:
        if _norm(os.path.basename(actual)) in alias:
            if actual.lower() in raices_protegidas_norm:
                # No seguimos subiendo desde la instalación: devolver la ruta
                # original conserva la ubicación concreta que encontró el
                # manifest y evita que el backup se convierta en un backup de
                # toda la instalación.
                return ruta
            if not _ruta_es_contenedor_compartido(actual, carpetas_peligrosas):
                return actual

        padre = os.path.dirname(actual)
        if not padre or padre == actual:
            break
        # Si el padre ya es un contenedor compartido, NO lo inspeccionamos ni
        # seguimos subiendo: el juego ya no puede identificarse de forma
        # inequívoca más arriba.
        if _ruta_es_contenedor_compartido(padre, carpetas_peligrosas):
            break
        actual = padre

    return ruta


def obtener_rutas_guardado(datos_juego, contexto, store_actual, con_store_origen=False):
    """A partir de la ficha del juego en la base de datos de Arlequin-SaveHub,
    devuelve la lista de carpetas reales (ya resueltas) donde debería estar
    guardando la partida.

    Cualquier ruta que resuelva a una carpeta compartida por todos los
    juegos (ver _carpetas_contenedoras_compartidas) se descarta: si tenía un
    comodín parcial recortable (p. ej. "My Games/Nombre *"), antes se intenta
    encontrar la carpeta real de ESTE juego en disco
    (_buscar_carpeta_real_por_comodin); si no, se prescinde de esa ruta en
    vez de arriesgarse a tratar la carpeta compartida como si fuera suya.

    Si con_store_origen=True, en vez de una lista de rutas devuelve una
    lista de tuplas (ruta, store_de_la_entrada), donde store_de_la_entrada
    es el único valor de la condición "store=" de la entrada de
    save_locations que resolvió esa ruta (o None si la entrada no estaba
    restringida a una tienda concreta, o lo estaba a varias a la vez). Esto
    permite, cuando no se sabe de antemano en qué launcher está instalado
    el juego (rastreo por catálogo completo, sin partir de un launcher),
    inferir igualmente la tienda a partir de qué ruta fue la que
    efectivamente se encontró en disco.
    """
    rutas = []
    origenes = []
    entradas = (datos_juego or {}).get("save_locations") or []
    carpetas_peligrosas = _carpetas_contenedoras_compartidas(contexto)
    for entrada in entradas:
        plantilla, condiciones = _parsear_entrada_save_location(entrada)
        if not plantilla:
            continue
        if not condicion_aplica_en_windows(condiciones, store_actual):
            continue
        stores_entrada = condiciones.get("store") or set()
        store_origen = next(iter(stores_entrada)) if len(stores_entrada) == 1 else None
        for ruta in resolver_plantilla_ruta(plantilla, contexto):
            # <base> es la carpeta de instalación cuando el juego procede de
            # un launcher. Se protege durante la búsqueda por acrónimo para
            # que una ruta de save situada dentro de la instalación nunca
            # pueda escalar accidentalmente hasta la carpeta completa del
            # juego. El resto de rutas (Documents, AppData, etc.) no tienen
            # este límite porque no son instalaciones del launcher.
            raices_protegidas = []
            base_instalacion = (contexto.get("base") or "").replace("\\", "/").rstrip("/")
            if base_instalacion and "<base>" in plantilla:
                raices_protegidas.append(base_instalacion)
            ruta = _preferir_carpeta_por_acronym(
                ruta, datos_juego, carpetas_peligrosas, raices_protegidas=raices_protegidas
            )
            if _ruta_es_contenedor_compartido(ruta, carpetas_peligrosas):
                ruta_especifica = _buscar_carpeta_real_por_comodin(plantilla, contexto)
                if (ruta_especifica
                        and not _ruta_es_contenedor_compartido(ruta_especifica, carpetas_peligrosas)
                        and ruta_especifica not in rutas):
                    rutas.append(ruta_especifica)
                    origenes.append(store_origen)
                continue
            if ruta not in rutas:
                rutas.append(ruta)
                origenes.append(store_origen)
    if con_store_origen:
        return list(zip(rutas, origenes))
    return rutas


# Inverso de LAUNCHER_A_STORE (varias tiendas pueden apuntar a None, así que
# no se puede invertir con un simple dict comprehension sin perder alguna;
# se hace a mano y solo con las tiendas que sí tienen un launcher propio).
STORE_A_LAUNCHER = {
    "steam": "Steam",
    "epic": "Epic",
    "gog": "GOG",
    "uplay": "Ubisoft",
    "microsoft": "Xbox",
}


# ---------------------------------------------------------------------------
#  "INTUICIÓN" DE RUTAS PARA JUEGOS QUE EL MANIFEST NO CUBRE BIEN
# ---------------------------------------------------------------------------
# Algunas editoras usan siempre el mismo patrón de carpeta bajo Documentos
# (p. ej. Rockstar Games guarda TODOS sus juegos en "Documents/Rockstar
# Games/<Juego>", tanto en Steam como en Epic). Cuando el manifest de
# Ludusavi no tiene ficha para el juego, o la tiene pero no resuelve ninguna
# ruta real (por ejemplo, porque aún no existe la del reciente "GTA V
# Enhanced"), probamos a buscar una subcarpeta con un nombre parecido dentro
# de estas rutas "editora conocida" como último recurso, antes de darlo por
# no localizado. Añadir más editoras a esta lista es tan sencillo como
# incluir su nombre de carpeta tal cual aparece bajo Documentos.
CARPETAS_EDITORAS_CONOCIDAS = [
    "Rockstar Games",  # GTA V/IV, Red Dead Redemption 1/2, Max Payne 3, L.A. Noire, Bully...
]

# Los nombres de carpeta de guardado no siempre coinciden con el nombre del
# juego tal y como lo reporta Steam/Epic/etc. Rockstar es el caso típico:
# "Grand Theft Auto V" (o "... V Enhanced") en la tienda, pero la carpeta de
# saves real se llama simplemente "GTA V". Este diccionario cubre esos casos
# conocidos (clave y valor ya normalizados con _norm).
ALIAS_CARPETA_JUEGO = {
    "grand theft auto v": "gta v",
    "grand theft auto v enhanced": "gta v",
    "grand theft auto v legacy": "gta v",
    "grand theft auto v premium edition": "gta v",
    "grand theft auto iv": "gta iv",
    "grand theft auto iv complete edition": "gta iv",
    "grand theft auto iv the complete edition": "gta iv",
    "grand theft auto san andreas": "gta san andreas",
    "grand theft auto vice city": "gta vice city",
    "grand theft auto iii": "gta iii",
}


def intuir_rutas_por_editoras_conocidas(nombre_juego, entorno):
    """Último recurso cuando el manifest no localiza nada: recorre las
    carpetas de editoras conocidas (ver CARPETAS_EDITORAS_CONOCIDAS) dentro
    de Documentos y devuelve las subcarpetas cuyo nombre se parece al del
    juego detectado (cruce por nombre normalizado, con soporte para los
    alias conocidos de ALIAS_CARPETA_JUEGO cuando el nombre de la carpeta no
    se parece nada al nombre "oficial" del juego)."""
    candidatas = []
    n_juego = _norm(nombre_juego)
    if not n_juego:
        return candidatas
    n_juego_alias = ALIAS_CARPETA_JUEGO.get(n_juego)
    documentos = entorno.get("winDocuments", "")
    if not documentos:
        return candidatas
    for editora in CARPETAS_EDITORAS_CONOCIDAS:
        raiz_editora = os.path.join(documentos, editora).replace("\\", "/")
        if not os.path.isdir(raiz_editora):
            continue
        try:
            for sub in os.listdir(raiz_editora):
                ruta_sub = os.path.join(raiz_editora, sub).replace("\\", "/")
                if not os.path.isdir(ruta_sub):
                    continue
                n_sub = _norm(sub)
                if not n_sub or len(n_sub) < 3:
                    continue
                coincide = n_sub in n_juego or n_juego in n_sub or (
                    n_juego_alias and (n_sub == n_juego_alias or n_juego_alias in n_sub or n_sub in n_juego_alias))
                if coincide:
                    candidatas.append(ruta_sub)
        except Exception:
            continue
    return candidatas


def detectar_juegos_steam():
    """Lee las bibliotecas Steam y sus appmanifest_*.acf.

    Steam puede mantener libraryfolders.vdf en steamapps (formato clásico)
    o en config (formato usado por clientes recientes). Se comprueban ambos
    y también las rutas del registro como respaldo, para no clasificar una
    instalación Steam real como "sin launcher" cuando la biblioteca está en
    otra unidad.
    """
    juegos = []
    if not _ES_WINDOWS:
        return juegos

    steam_paths = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        try:
            valor = winreg.QueryValueEx(key, "SteamPath")[0]
            if valor:
                steam_paths.append(str(valor).replace("\\", "/"))
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass

    # Respaldo: Steam también puede estar registrado en HKLM y la vista de
    # 32 bits es especialmente habitual en Windows.
    for root, subkey, access in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", winreg.KEY_READ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", winreg.KEY_READ),
    ):
        try:
            key = winreg.OpenKey(root, subkey, 0, access)
            try:
                valor = winreg.QueryValueEx(key, "InstallPath")[0]
            finally:
                winreg.CloseKey(key)
            if valor:
                steam_paths.append(str(valor).replace("\\", "/"))
        except Exception:
            continue

    # Respaldo final para instalaciones estándar, sin convertirlas en una
    # detección positiva por sí mismas: solo se usan si realmente contienen
    # steamapps.
    for candidato in (
        r"C:/Program Files (x86)/Steam",
        r"C:/Program Files/Steam",
    ):
        steam_paths.append(candidato)

    # Conserva orden pero elimina duplicados.
    steam_paths_unicos = []
    vistos_steam = set()
    for sp in steam_paths:
        sp = os.path.normpath(sp).replace("\\", "/")
        clave = sp.lower()
        if clave not in vistos_steam and os.path.isdir(sp):
            vistos_steam.add(clave)
            steam_paths_unicos.append(sp)

    librerias = []
    for steam_path in steam_paths_unicos:
        candidatas_vdf = [
            os.path.join(steam_path, "steamapps", "libraryfolders.vdf"),
            os.path.join(steam_path, "config", "libraryfolders.vdf"),
        ]
        librerias_locales = [os.path.join(steam_path, "steamapps")]
        for lf in candidatas_vdf:
            if not os.path.isfile(lf):
                continue
            try:
                texto = open(lf, encoding="utf-8", errors="ignore").read()
                for m in re.finditer(r'"path"\s+"([^"]+)"', texto):
                    ruta_lib = m.group(1).replace("\\\\", "\\").replace("\\", "/")
                    librerias_locales.append(os.path.join(ruta_lib, "steamapps"))
            except Exception:
                continue
        for lib in librerias_locales:
            lib = os.path.normpath(lib).replace("\\", "/")
            if os.path.isdir(lib):
                librerias.append(lib)

    # Elimina bibliotecas repetidas.
    librerias = list(dict.fromkeys(librerias))

    vistos_apps = set()
    for lib in librerias:
        try:
            archivos = os.listdir(lib)
        except Exception:
            continue
        for f in archivos:
            if not (f.startswith("appmanifest_") and f.endswith(".acf")):
                continue
            m_id = re.search(r'appmanifest_(\d+)\.acf$', f)
            app_id = m_id.group(1) if m_id else None
            if app_id and app_id in vistos_apps:
                continue
            try:
                ruta_manifest = os.path.join(lib, f)
                texto = open(ruta_manifest, encoding="utf-8", errors="ignore").read()
                m_name = re.search(r'"name"\s+"([^"]+)"', texto)
                m_dir = re.search(r'"installdir"\s+"([^"]+)"', texto)
                if not m_name:
                    continue
                installdir = os.path.join(lib, "common", m_dir.group(1)) if m_dir else ""
                installdir = os.path.normpath(installdir).replace("\\", "/")
                # Steam puede conservar manifests mientras una instalación
                # está rota; para ASH solo lo tratamos como juego instalado si
                # la carpeta del juego existe realmente.
                if not installdir or not os.path.isdir(installdir):
                    continue
                if app_id:
                    vistos_apps.add(app_id)
                juegos.append({
                    "nombre": m_name.group(1),
                    "launcher": "Steam",
                    "installdir": installdir,
                    "id": app_id,
                })
            except Exception:
                continue
    return juegos


def detectar_juegos_epic():
    """Lee los manifiestos .item que Epic Games Launcher deja en %ProgramData%.
    La ruta estándar (ProgramData\\Epic\\EpicGamesLauncher\\Data\\Manifests) se
    usa como método principal, porque en muchos equipos la clave de registro
    con 'AppDataPath' no existe o no se ha escrito; el registro queda como
    alternativa por si la instalación de Epic no está en la ruta estándar."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos

    carpetas_manifiestos = []

    programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    ruta_estandar = os.path.join(programdata, "Epic", "EpicGamesLauncher", "Data", "Manifests")
    if os.path.isdir(ruta_estandar):
        carpetas_manifiestos.append(ruta_estandar)

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher")
        appdata = winreg.QueryValueEx(key, "AppDataPath")[0]
        winreg.CloseKey(key)
        ruta_registro = os.path.join(appdata, "Manifests")
        if os.path.isdir(ruta_registro) and ruta_registro not in carpetas_manifiestos:
            carpetas_manifiestos.append(ruta_registro)
    except Exception:
        pass

    if not carpetas_manifiestos:
        return juegos

    vistos = set()
    for manifiestos in carpetas_manifiestos:
        for f in os.listdir(manifiestos):
            if not f.endswith(".item"):
                continue
            try:
                datos = json.load(open(os.path.join(manifiestos, f), encoding="utf-8"))
                nombre = datos.get("DisplayName", "")
                installdir = datos.get("InstallLocation", "")
                if nombre and "launcher" not in _norm(nombre) and installdir and os.path.exists(installdir):
                    clave = _norm(nombre)
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    juegos.append({"nombre": nombre, "launcher": "Epic", "installdir": installdir, "id": None})
            except Exception:
                continue
    return juegos


def detectar_juegos_gog():
    """Lee HKLM\\SOFTWARE\\WOW6432Node\\GOG.com\\Games\\<id>."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games")
    except Exception:
        return juegos
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(key, i)
            i += 1
        except OSError:
            break
        try:
            k2 = winreg.OpenKey(key, sub)
            nombre = winreg.QueryValueEx(k2, "gameName")[0]
            path = winreg.QueryValueEx(k2, "path")[0]
            winreg.CloseKey(k2)
            if nombre and os.path.exists(path):
                juegos.append({"nombre": nombre, "launcher": "GOG", "installdir": path, "id": sub})
        except Exception:
            continue
    try:
        winreg.CloseKey(key)
    except Exception:
        pass
    return juegos


NOMBRES_BNET = {
    "agent": None, "battle.net": None, "battle.net.exe": None,
    "destiny2": "Destiny 2",
    "diablo iii": "Diablo III", "diablo iv": "Diablo IV",
    "hearthstone": "Hearthstone",
    "heroes of the storm": "Heroes of the Storm",
    "overwatch": "Overwatch",
    "starcraft": "StarCraft", "starcraft ii": "StarCraft II",
    "warcraft iii": "Warcraft III",
    "world of warcraft": "World of Warcraft",
    "wow classic": "WoW Classic",
    "call of duty": "Call of Duty",
    "black ops cold war": "CoD: Black Ops Cold War",
    "black ops 6": "CoD: Black Ops 6",
    "modern warfare": "CoD: Modern Warfare",
    "modern warfare 2": "CoD: Modern Warfare II",
    "vanguard": "CoD: Vanguard", "warzone": "CoD: Warzone",
}


def detectar_juegos_battlenet():
    """Lee HKLM\\SOFTWARE\\WOW6432Node\\Blizzard Entertainment\\Battle.net\\Install."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Blizzard Entertainment\Battle.net\Install")
    except Exception:
        return juegos
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(key, i)
            i += 1
        except OSError:
            break
        nombre = NOMBRES_BNET.get(sub.lower(), sub)
        if nombre is None:
            continue
        try:
            k2 = winreg.OpenKey(key, sub)
            path = winreg.QueryValueEx(k2, "InstallPath")[0]
            winreg.CloseKey(k2)
        except Exception:
            path = ""
        juegos.append({"nombre": nombre, "launcher": "Battle.net", "installdir": path, "id": None})
    try:
        winreg.CloseKey(key)
    except Exception:
        pass
    return juegos


def detectar_juegos_ubisoft():
    """Lee las instalaciones registradas por Ubisoft Connect, probando las
    vistas de registro de 32 y 64 bits.

    La ruta del juego (InstallDir) sirve para detectar el título instalado;
    las partidas de Ubisoft, cuando el manifest usa <root>, se resuelven
    aparte contra obtener_ubisoft_root()."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos
    rutas = [r"SOFTWARE\Ubisoft\Launcher\Installs",
             r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"]
    try:
        vistas = [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]
    except AttributeError:
        vistas = [0]
    vistas = list(dict.fromkeys(vistas))
    vistos = set()
    for ruta_reg in rutas:
        for vista in vistas:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta_reg, 0,
                                     winreg.KEY_READ | vista)
            except Exception:
                continue
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                    i += 1
                except OSError:
                    break
                try:
                    k2 = winreg.OpenKey(key, sub)
                    try:
                        path = winreg.QueryValueEx(k2, "InstallDir")[0]
                    finally:
                        winreg.CloseKey(k2)
                    if not path:
                        continue
                    clave = os.path.normcase(os.path.normpath(str(path)))
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    nombre = os.path.basename(str(path).rstrip("\\/")) or f"Ubisoft #{sub}"
                    juegos.append({"nombre": nombre, "launcher": "Ubisoft",
                                   "installdir": path, "id": None})
                except Exception:
                    continue
            try:
                winreg.CloseKey(key)
            except Exception:
                pass
    return juegos


def _detectar_juegos_registro_estilo_ea(ruta_registro, launcher):
    """Patrón común a las claves de registro de EA (tanto la app clásica
    'Origin' como la actual 'EA app', que siguen escribiendo bajo estas
    mismas rutas por compatibilidad): un subkey por juego con el valor
    'Install Dir' (o, en instalaciones más antiguas, 'InstallDir' sin
    espacio). El nombre "bonito" no siempre está disponible como tal, así
    que se intenta 'DisplayName' y, si no existe, se cae al nombre de la
    carpeta de instalación (mismo criterio que ya se usa para Ubisoft)."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta_registro)
    except Exception:
        return juegos
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(key, i)
            i += 1
        except OSError:
            break
        try:
            k2 = winreg.OpenKey(key, sub)
        except Exception:
            continue
        try:
            path = None
            for valor in ("Install Dir", "InstallDir"):
                try:
                    path = winreg.QueryValueEx(k2, valor)[0]
                    break
                except Exception:
                    continue
            if not path or not os.path.isdir(path):
                continue
            try:
                nombre = winreg.QueryValueEx(k2, "DisplayName")[0]
            except Exception:
                nombre = os.path.basename(path.rstrip("\\/")) or sub
            juegos.append({"nombre": nombre, "launcher": launcher, "installdir": path, "id": sub})
        finally:
            winreg.CloseKey(k2)
    try:
        winreg.CloseKey(key)
    except Exception:
        pass
    return juegos


def detectar_juegos_ea():
    """EA app / Origin. Ambos escriben (por compatibilidad hacia atrás) bajo
    las mismas dos rutas clásicas de registro, un subkey por juego:
        HKLM\\SOFTWARE\\WOW6432Node\\Origin Games\\<id>\\Install Dir
        HKLM\\SOFTWARE\\WOW6432Node\\EA Games\\<id>\\Install Dir
    Es de solo lectura y no requiere lanzar ningún proceso externo, igual
    que el resto de detecciones vía registro de esta app."""
    juegos = _detectar_juegos_registro_estilo_ea(r"SOFTWARE\WOW6432Node\Origin Games", "EA")
    juegos += _detectar_juegos_registro_estilo_ea(r"SOFTWARE\WOW6432Node\EA Games", "EA")
    # Un mismo juego puede aparecer registrado bajo las dos rutas a la vez en
    # algunas instalaciones; nos quedamos con una sola entrada por carpeta.
    vistas = set()
    unicos = []
    for j in juegos:
        clave = os.path.normcase(os.path.normpath(j["installdir"]))
        if clave in vistas:
            continue
        vistas.add(clave)
        unicos.append(j)
    return unicos


def detectar_juegos_amazon():
    """Amazon Games (incluye lo instalado vía Prime Gaming) no deja un
    subkey de registro por juego como GOG/Ubisoft/EA: guarda su catálogo en
    una base de datos SQLite propia,
        %LOCALAPPDATA%\\Amazon Games\\Data\\Games\\Sql\\GameInstallInfo.sqlite
    en una tabla 'DbSet' con columnas (entre otras) Id, ProductTitle,
    InstallDirectory e Installed. Se abre en modo solo-lectura (uri=True,
    mode=ro) para poder leerla sin problema aunque Amazon Games esté
    abierto en ese momento con el archivo detrás bloqueado para escritura."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos
    localappdata = os.environ.get("LOCALAPPDATA")
    if not localappdata:
        return juegos
    ruta_db = os.path.join(localappdata, "Amazon Games", "Data", "Games", "Sql",
                            "GameInstallInfo.sqlite").replace("\\", "/")
    if not os.path.exists(ruta_db):
        return juegos
    try:
        uri = f"file:{ruta_db}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            cur = con.cursor()
            cur.execute("SELECT Id, ProductTitle, InstallDirectory, Installed FROM DbSet")
            filas = cur.fetchall()
        finally:
            con.close()
    except Exception:
        return juegos

    for id_juego, titulo, installdir, instalado in filas:
        if not titulo or not installdir:
            continue
        # Installed puede venir como 0/1, True/False o texto según la
        # versión de la app; solo interesan los que sí están instalados.
        if instalado in (0, "0", False, None):
            continue
        if not os.path.isdir(installdir):
            continue
        juegos.append({
            "nombre": titulo,
            "launcher": "Amazon",
            "installdir": installdir.replace("\\", "/"),
            "id": str(id_juego) if id_juego is not None else None,
        })
    return juegos


def detectar_juegos_xbox():
    """Juegos UWP instalados (incluidos los de Xbox Game Pass para PC).

    Se lee HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AppModel\\
    Repository\\Packages\\<PackageFamilyName>, que es donde Windows guarda
    el registro de TODOS los paquetes UWP instalados para cualquier
    usuario del equipo. Es de solo lectura y no hace falta invocar
    Get-AppxPackage ni ningún proceso externo de PowerShell: el mismo dato
    que devolvería ese cmdlet ya vive aquí, en el registro.

    Limitación conocida: el valor 'DisplayName' de algunos paquetes es una
    referencia a un recurso interno del propio paquete (algo con forma
    "@{...}") en vez de texto legible, y resolverla requeriría llamadas de
    la API de Windows que no vienen en la librería estándar de Python. Para
    esos casos se deriva un nombre razonable a partir del propio
    PackageFamilyName (quitando el sufijo hash y separando palabras en
    mayúsculas), que el cruce por similitud contra el manifest (ver
    buscar_en_manifest) suele bastar para reconocer de todas formas."""
    juegos = []
    if not _ES_WINDOWS:
        return juegos
    RUTA_PACKAGES = r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"
    # Prefijos de paquetes de sistema/frameworks de Microsoft que nunca son
    # juegos, para no recorrerlos ni perder tiempo con ellos.
    PREFIJOS_SISTEMA = (
        "microsoft.", "windows.", "microsoftwindows.", "c5e2524a-ea46",
        "e2a4f912-2574", "f46d4000-fd22", "nvidiacorp.", "intel.",
        "clipchamp.", "royalapps.",
    )
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, RUTA_PACKAGES)
    except Exception:
        return juegos
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(key, i)
            i += 1
        except OSError:
            break
        if sub.lower().startswith(PREFIJOS_SISTEMA):
            continue
        try:
            k2 = winreg.OpenKey(key, sub)
        except Exception:
            continue
        try:
            try:
                ruta = winreg.QueryValueEx(k2, "PackageRootFolder")[0]
            except Exception:
                ruta = None
            try:
                nombre = winreg.QueryValueEx(k2, "DisplayName")[0]
            except Exception:
                nombre = None
        finally:
            winreg.CloseKey(k2)

        if nombre and nombre.startswith("@"):
            # Referencia a recurso interno, no texto legible: se descarta
            # a favor del nombre derivado del PackageFamilyName de abajo.
            nombre = None
        if not nombre:
            base = sub.split("_")[0]  # quita el sufijo hash del final
            base = base.rsplit(".", 1)[-1] if "." in base else base
            # CamelCase -> "Camel Case", para que se lea como un nombre.
            nombre = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", base).strip()
        if not nombre:
            continue

        juegos.append({
            "nombre": nombre,
            "launcher": "Xbox",
            "installdir": (ruta or "").replace("\\", "/"),
            "id": sub,
        })
    try:
        winreg.CloseKey(key)
    except Exception:
        pass
    return juegos


def detectar_todos_los_juegos():
    """Devuelve la lista completa de juegos instalados detectados vía launchers.

    Los detectores son independientes entre sí (registro, manifests y
    carpetas diferentes), por lo que se pueden ejecutar en paralelo. Esto
    reduce bastante el tiempo de espera en equipos con varias bibliotecas.
    El resultado se conserva en el mismo orden fijo de launchers para que la
    interfaz siga siendo determinista.
    """
    funciones = (
        detectar_juegos_steam, detectar_juegos_epic, detectar_juegos_gog,
        detectar_juegos_battlenet, detectar_juegos_ubisoft, detectar_juegos_ea,
        detectar_juegos_amazon, detectar_juegos_xbox,
    )
    resultados = [None] * len(funciones)
    try:
        with ThreadPoolExecutor(max_workers=len(funciones)) as executor:
            futuros = [executor.submit(fn) for fn in funciones]
            for i, futuro in enumerate(futuros):
                try:
                    resultados[i] = futuro.result() or []
                except Exception:
                    resultados[i] = []
    except Exception:
        # Respaldo conservador: si el pool no pudiera crearse, mantenemos el
        # comportamiento secuencial anterior.
        resultados = []
        for fn in funciones:
            try:
                resultados.append(fn() or [])
            except Exception:
                resultados.append([])

    todos = []
    for lista in resultados:
        todos.extend(lista or [])
    return todos


def detectar_juegos_carpetas_raiz(carpetas_raiz):
    """Trata cada subcarpeta de las 'carpetas raíz sin launcher' indicadas por
    el usuario como un posible juego instalado. Pensado para juegos DRM-free
    (típico de GOG) o instalaciones portables que no dejan ningún registro,
    manifiesto ni ID en el equipo: la única pista es la carpeta donde viven.
    Se cruzan igual que el resto, por nombre normalizado, contra el manifest
    de Ludusavi (no tienen ID de tienda del que tirar)."""
    juegos = []
    for carpeta_raiz in (carpetas_raiz or []):
        if not carpeta_raiz or not os.path.isdir(carpeta_raiz):
            continue
        try:
            for nombre_sub in os.listdir(carpeta_raiz):
                ruta_sub = os.path.join(carpeta_raiz, nombre_sub).replace("\\", "/")
                if not os.path.isdir(ruta_sub):
                    continue
                juegos.append({
                    "nombre": nombre_sub,
                    "launcher": "Carpeta",
                    "installdir": ruta_sub,
                    "id": None,
                })
        except Exception:
            continue
    return juegos


# ---------------------------------------------------------------------------
#  DETECCIÓN DE "¿SIGUE ABIERTO EL JUEGO?"
# ---------------------------------------------------------------------------
# Ni el backup ni la restauración comprobaban antes si el propio juego seguía
# en ejecución. Si en ese momento el juego está escribiendo su partida, el
# cálculo de tamaños puede toparse con una carrera de escritura, y restaurar
# encima de un save activo puede acabar sobrescribiéndose de nuevo en cuanto
# el juego vuelva a guardar. Esto solo se puede comprobar de forma fiable
# para los juegos "conocidos" (detectados vía registro/instalador de Steam,
# Epic, GOG, Battle.net, Ubisoft, EA, Amazon, Xbox o carpetas sin launcher), porque de esos sí
# se conoce su carpeta de instalación y, por tanto, sus .exe candidatos.

# Ejecutables que aparecen dentro de muchas carpetas de instalación pero que
# NUNCA son el juego en sí (instaladores, redistribuibles, anticheat, crash
# handlers...). Se ignoran para no dar falsos positivos de "sigue abierto".
_EXES_IGNORADOS_DETECCION = {
    "unins000.exe", "uninstall.exe", "uninst.exe",
    "unitycrashhandler64.exe", "unitycrashhandler32.exe",
    "vc_redist.x64.exe", "vc_redist.x86.exe", "vcredist.exe",
    "dxsetup.exe", "dotnetfx35setup.exe", "directx_installer.exe",
    "redistributables.exe", "redist.exe",
    "easyanticheat_setup.exe", "eastarter.exe", "battleye_installer.exe",
    "crashreportclient.exe", "crashpad_handler.exe", "crashsender.exe",
    "installer.exe", "setup.exe", "launcher_setup.exe",
}


def _detectar_exes_candidatos(installdir, max_exes=25, max_profundidad=2):
    """Busca, dentro de la carpeta de instalación de un juego, los .exe que
    con más probabilidad son el juego en sí (o alguno de sus procesos:
    muchos juegos tienen un launcher + el ejecutable real en una subcarpeta
    tipo Binaries/Win64), ignorando instaladores y redistribuibles conocidos.

    Se limita tanto la profundidad (por defecto 2 niveles) como la cantidad
    de resultados para no tardar en instalaciones enormes (p. ej. juegos con
    decenas de miles de archivos de assets); no hace falta encontrarlos
    todos, basta con encontrar uno que de verdad esté en ejecución."""
    encontrados = []
    if not installdir or not os.path.isdir(installdir):
        return encontrados
    raiz = os.path.normpath(installdir)
    profundidad_raiz = raiz.rstrip(os.sep).count(os.sep)
    try:
        for carpeta_actual, subcarpetas, ficheros in os.walk(raiz):
            profundidad_actual = carpeta_actual.rstrip(os.sep).count(os.sep) - profundidad_raiz
            if profundidad_actual >= max_profundidad:
                subcarpetas[:] = []  # no bajar más de la cuenta
            for fichero in ficheros:
                nombre_min = fichero.lower()
                if not nombre_min.endswith(".exe"):
                    continue
                if nombre_min in _EXES_IGNORADOS_DETECCION:
                    continue
                encontrados.append(nombre_min)
                if len(encontrados) >= max_exes:
                    return encontrados
    except Exception:
        pass
    return encontrados


def _listar_procesos_en_ejecucion():
    """Devuelve un conjunto con los nombres (en minúsculas) de todos los
    procesos .exe actualmente en ejecución.

    Se intenta primero con psutil, si está instalado, por ser más rápido y
    fiable; si no está disponible se recurre a "tasklist", que viene
    incluido en Windows y no exige ninguna dependencia extra. Si ninguno de
    los dos funciona (por ejemplo fuera de Windows, o por permisos), se
    devuelve un conjunto vacío y sencillamente no se avisa de nada: es
    preferible no molestar al usuario a bloquear el backup/restauración por
    una comprobación que ni siquiera es la función principal del programa.
    """
    nombres = set()
    if not _ES_WINDOWS:
        return nombres

    try:
        import psutil  # opcional: se usa si el usuario ya lo tiene instalado
        for proc in psutil.process_iter(["name"]):
            try:
                nombre = (proc.info.get("name") or "").strip().lower()
            except Exception:
                continue
            if nombre:
                nombres.add(nombre)
        if nombres:
            return nombres
    except Exception:
        pass  # psutil no instalado, o fallo consultando: probamos con tasklist

    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        salida = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            creationflags=flags, stderr=subprocess.DEVNULL, timeout=6,
        )
        texto = salida.decode("mbcs", errors="ignore")
        for linea in texto.splitlines():
            linea = linea.strip()
            if not linea or not linea.startswith('"'):
                continue
            primer_campo = linea.split('","')[0].strip('"').strip()
            if primer_campo:
                nombres.add(primer_campo.lower())
    except Exception as exc:
        logging.info(f"No se pudo obtener la lista de procesos en ejecución: {exc}")
    return nombres


# ---------------------------------------------------------------------------
#  CÁLCULO DE TAMAÑO DE CARPETAS
# ---------------------------------------------------------------------------

def _tamano_carpeta_bytes(ruta):
    """Tamaño total (bytes) de una carpeta, recorrida a mano con
    os.scandir() en vez de os.walk() + os.path.getsize().

    os.walk() ya usa scandir() por dentro para listar cada carpeta, y los
    DirEntry que genera esa misma llamada al sistema (FindNextFile en
    Windows) ya traen el tamaño del archivo cacheado. Pedir después
    os.path.getsize(fp) tira esa información y hace un stat() adicional
    por archivo, duplicando la E/S. Aquí se conserva el DirEntry y se usa
    su propio entry.stat() (que en Windows no vuelve a tocar el disco:
    reutiliza los datos que ya trajo scandir()), evitando ese stat() extra
    en carpetas con muchos archivos pequeños (slots de guardado, configs,
    caché de shaders...)."""
    total = 0
    try:
        with os.scandir(ruta) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        total += _tamano_carpeta_bytes(entry.path)
                    else:
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


# ---------------------------------------------------------------------------
#  APLICACIÓN
# ---------------------------------------------------------------------------

class GestorPartidasLocal:
    def _formatear_bytes(self, num_bytes):
        """Convierte bytes a una unidad legible para mostrar tamaños en la UI."""
        try:
            n = float(num_bytes or 0)
        except (TypeError, ValueError):
            n = 0.0
        unidades = ("B", "KB", "MB", "GB", "TB", "PB")
        i = 0
        while abs(n) >= 1024.0 and i < len(unidades) - 1:
            n /= 1024.0
            i += 1
        if i == 0:
            return f"{int(n)} {unidades[i]}"
        return f"{n:.2f} {unidades[i]}"

    def abrir_carpeta_backups(self):
        if not os.path.exists(self.dest):
            os.makedirs(self.dest, exist_ok=True)
        os.startfile(os.path.normpath(self.dest))

    def cambiar_carpeta(self):
        r = fd.askdirectory(initialdir=self.dest)
        if r:
            self.dest = r
            self.lbl_r.config(text=f"Guardando en: {self.dest}")

    def aplicar_icono_ventana(self, ventana):
        """Pone icono.ico en la barra de título de la ventana. En Windows,
        iconbitmap también es lo que usa la barra de tareas para esa misma
        ventana (el ajuste de identidad de la app para que no comparta el
        icono genérico de python.exe se hace aparte, ver
        _fijar_identidad_taskbar_windows() al arrancar el programa)."""
        try:
            if os.path.exists(ICON_PATH):
                ventana.iconbitmap(default=ICON_PATH)
            else:
                self._log("WARNING", f"No se encontró icono.ico junto al programa ({ICON_PATH}).")
        except Exception as e:
            self._log("WARNING", f"No se pudo aplicar el icono de la ventana: {e}")

    def centrar_ventana(self, ventana, ancho, alto):
        pantalla_ancho = ventana.winfo_screenwidth()
        pantalla_alto = ventana.winfo_screenheight()
        x = (pantalla_ancho // 2) - (ancho // 2)
        y = (pantalla_alto // 2) - (alto // 2)
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

    def ejecutar_en_hilo(self, funcion):
        """Ejecuta una tarea de fondo, evitando que dos operaciones pesadas
        (escaneo/BD/backup/restauración) se pisen entre sí."""
        def trabajador():
            # Espera a que termine la operación anterior en vez de ejecutar
            # dos escaneos/copias simultáneamente.
            self._worker_lock.acquire()
            try:
                self._log("INFO", "Inicio de tarea: %s", getattr(funcion, "__name__", repr(funcion)))
                funcion()
                self._log("INFO", "Fin de tarea: %s", getattr(funcion, "__name__", repr(funcion)))
            except Exception as exc:
                self._log("ERROR", "Error en tarea: %s", exc, exc_info=True)
                try:
                    self.root.after(0, lambda e=str(exc): mb.showerror(
                        "Error", f"La operación terminó con un error:\n\n{e}"
                    ))
                except Exception:
                    pass
            finally:
                self._worker_lock.release()

        hilo = threading.Thread(target=trabajador, daemon=True)
        hilo.start()

    def abrir_link_donar(self):
        webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def abrir_link_contacto(self):
        webbrowser.open("https://x.com/_noxbat")

    def seleccionar_todo_el_listado(self):
        self.box.selection_clear(0, tk.END)
        for i in range(self.box.size()):
            texto = self.box.get(i)
            if not texto.startswith("---") and texto != "":
                self.box.selection_set(i)

    def deseleccionar_todo_el_listado(self):
        self.box.selection_clear(0, tk.END)

    def get_sel_list(self):
        try:
            selección = self.box.curselection()
            if selección:
                elementos_validos = []
                for idx in selección:
                    texto_item = self.box.get(idx)
                    if not texto_item.startswith("---") and texto_item != "":
                        elementos_validos.append(texto_item)
                return elementos_validos
        except Exception:
            pass
        return []

    def limpiar_nombre_juego(self, texto_fila):
        res = texto_fila.replace("[👍 Copia Ok] ", "")
        res = res.replace("[Solo en Backup] ", "")
        res = res.strip()
        if " (" in res:
            partes = res.split(" (")
            res = " (".join(partes[:-1])
        return res.strip()

    def _normalizar_nombre_ruta(self, texto):
        """Normaliza un nombre de carpeta para poder compararlo con el nombre del juego."""
        try:
            return _norm(os.path.basename(str(texto).rstrip("/\\")))
        except Exception:
            return str(texto).strip().lower()

    # Carpetas contenedoras de Windows que agrupan varios juegos, cada uno
    # en su propia subcarpeta (el mismo papel que ya cumple "My Games").
    # Cuando la ruta de un juego pasa por una de estas carpetas, esa carpeta
    # SIEMPRE debe quedar como primer nivel dentro de "Backup Saves" —igual
    # que "My Games"— aunque el nombre de juego que coincide en la ruta esté
    # más adentro. Por ejemplo, en "Saved Games/CD Projekt Red/<juego>" el
    # nombre del juego puede coincidir dos niveles más abajo, pero
    # "Saved Games" (mostrada por Windows como "Juegos guardados") debe
    # seguir siendo el primer nivel, igual que pasa con "My Games".
    CARPETAS_CONTENEDORAS_CONOCIDAS = ("my games", "saved games")

    def _indice_raiz_juego(self, partes, nombre_juego_limpio):
        """Índice, dentro de 'partes' (una ruta ya troceada en componentes),
        que marca la carpeta que se considera la 'unidad de juego' completa:
        la que se copia entera al hacer backup/restaurar y la que se archiva
        como bloque al rotar copias antiguas.

        Si la ruta pasa antes por una carpeta contenedora conocida (Saved
        Games, My Games...), la subcarpeta que va justo debajo de ella es
        esa unidad —y no el nombre de juego que pueda coincidir más
        adentro—. Así no se pierde la carpeta contenedora ni se mezclan
        entre sí los saves de varios juegos que compartan una misma
        subcarpeta (p. ej. varios juegos de la misma editora dentro de
        "Saved Games").

        Si no hay ninguna carpeta contenedora conocida en la ruta, se usa
        el comportamiento de siempre: la carpeta cuyo nombre coincide con
        el nombre limpio del juego.
        """
        for i, parte in enumerate(partes):
            if parte.strip().lower() in self.CARPETAS_CONTENEDORAS_CONOCIDAS and i + 1 < len(partes):
                return i + 1

        nombre_norm = _norm(nombre_juego_limpio)
        for i in range(len(partes) - 1, -1, -1):
            if _norm(partes[i]) == nombre_norm:
                return i
        return None

    def _grupo_backup_y_relativo(self, origen, nombre_juego_limpio):
        """
        Determina la ruta relativa del save dentro de Backup Saves.

        La carpeta del juego es SIEMPRE la unidad que se versiona. Por ejemplo:

            .../My Games/Borderlands 2/WillowGame/SaveData

        queda como:

            Backup Saves/My Games/Borderlands 2/WillowGame/SaveData

        De esta forma, cuando se hace un backup nuevo, se renombra la carpeta
        completa "Borderlands 2" y no "SaveData" o "WillowGame". Lo mismo se
        aplica a carpetas contenedoras conocidas como "Saved Games" (ver
        _indice_raiz_juego): "Saved Games/CD Projekt Red/..." queda como
        "Backup Saves/Saved Games/CD Projekt Red/...".
        """
        so = origen if os.path.isabs(origen) else os.path.join(UP, origen)
        so = os.path.normpath(so).replace("\\", "/")
        partes = [p for p in so.replace("\\", "/").split("/") if p]

        indice_juego = self._indice_raiz_juego(partes, nombre_juego_limpio)

        if indice_juego is not None:
            nombre_juego = partes[indice_juego]
            grupo = partes[indice_juego - 1] if indice_juego > 0 else "Otros"
            resto = partes[indice_juego + 1:]
            return "/".join([grupo, nombre_juego] + resto)

        # Cuando el nombre del juego no forma parte de la ruta real, mantenemos
        # el comportamiento anterior: agrupamos por la carpeta padre inmediata.
        nombre_origen = partes[-1] if partes else nombre_juego_limpio
        grupo = partes[-2] if len(partes) >= 2 else "Otros"
        return "/".join([grupo, nombre_juego_limpio, nombre_origen])

    def _pc_game_root(self, origen, nombre_juego_limpio):
        """Devuelve la carpeta raíz del juego tal y como está en el disco
        real (el equivalente a _backup_game_root, pero del lado del PC en
        vez de Backup Saves).

        Ejemplo:
            .../My Games/Borderlands 2/WillowGame/SaveData
            -> .../My Games/Borderlands 2

        Si la ruta pasa por una carpeta contenedora conocida (Saved Games,
        My Games...) se usa la subcarpeta directa de esa carpeta como raíz,
        igual que hace _grupo_backup_y_relativo (ver _indice_raiz_juego), de
        forma que el origen copiado y el destino del backup siempre
        coincidan en qué carpeta representa "el juego completo".

        Si el nombre del juego no aparece en la ruta, no hay una carpeta
        padre común que valga la pena versionar entera, así que se devuelve
        la propia ruta de origen sin cambios (comportamiento anterior).
        """
        so = origen if os.path.isabs(origen) else os.path.join(UP, origen)
        so = os.path.normpath(so).replace("\\", "/")
        partes = [p for p in so.split("/") if p]
        indice = self._indice_raiz_juego(partes, nombre_juego_limpio)
        if indice is not None:
            return "/".join(partes[:indice + 1])
        return so

    def _backup_game_root(self, origen, nombre_juego_limpio):
        """Devuelve la carpeta raíz versionable del juego.

        Ejemplo:
            .../My Games/Borderlands 2/WillowGame/SaveData
            -> Backup Saves/My Games/Borderlands 2
        """
        rel = self._grupo_backup_y_relativo(origen, nombre_juego_limpio)
        partes = [p for p in rel.replace("\\", "/").split("/") if p]
        if len(partes) >= 2:
            return os.path.join(self.dest, partes[0], partes[1]).replace("\\", "/")
        return os.path.join(self.dest, partes[0] if partes else nombre_juego_limpio).replace("\\", "/")

    def r_path(self, orig, nombre_juego_limpio):
        so = orig if os.path.isabs(orig) else os.path.join(UP, orig).replace("\\", "/")
        rel = self._grupo_backup_y_relativo(so, nombre_juego_limpio)
        return os.path.join(self.dest, *rel.split("/")).replace("\\", "/"), so

    def check_bkp(self, folder, rutas=None):
        """Comprueba si existe el backup agrupado correspondiente al juego.

        También reconoce backups antiguos en la raíz de Backup Saves para no
        romper instalaciones existentes que todavía no hayan sido reubicadas.
        """
        nombre = str(folder).lower().strip()

        if rutas:
            if isinstance(rutas, str):
                rutas = [rutas]
            for ruta in rutas:
                try:
                    esperado, ruta_origen = self.r_path(ruta, folder)
                    if os.path.isdir(esperado):
                        return True

                    # Si desapareció la carpeta activa, seguimos considerando
                    # disponible la copia histórica más reciente.
                    game_root = self._backup_game_root(ruta_origen, folder)
                    historico = self._buscar_backup_historico_mas_reciente(game_root)
                    if historico:
                        rel = os.path.relpath(esperado, game_root)
                        candidato = historico if rel == "." else os.path.join(historico, rel)
                        if os.path.isdir(candidato):
                            return True
                except Exception:
                    continue

        # Compatibilidad con el formato antiguo: Backup Saves/Juego
        if nombre in getattr(self, "backups_existentes", set()):
            return True

        # Si el índice contiene rutas agrupadas, comprobamos el último componente.
        for rel in getattr(self, "backups_existentes", set()):
            if str(rel).replace("\\", "/").rstrip("/").split("/")[-1].lower() == nombre:
                return True
        return False

    def _log(self, nivel, mensaje, *args, exc_info=False):
        """Escribe en el log sin permitir que un fallo de logging rompa la app."""
        try:
            logger = getattr(self, "_logger", None)
            if logger:
                getattr(logger, nivel.lower())(mensaje, *args, exc_info=exc_info)
        except Exception:
            pass

    def run_cmd(self, o, d):
        """Copia o->d usando robocopy y devuelve True solo si la copia fue válida."""
        if not o or not os.path.exists(o):
            self._log("WARNING", "Origen inexistente: %s", o)
            return False

        try:
            # /MT:n activa la copia multihilo de robocopy. El valor se
            # calcula una vez al arrancar según el hardware (ver
            # _calcular_hilos_robocopy): en equipos muy modestos se omite
            # (ROBOCOPY_HILOS_MT == 0) y se mantiene la copia clásica de un
            # solo hilo; en el resto se añade automáticamente, escalando en
            # CPUs de muchos hilos sin que haya que tocar nada a mano.
            opcion_mt = [f"/MT:{ROBOCOPY_HILOS_MT}"] if ROBOCOPY_HILOS_MT else []

            if os.path.isdir(o):
                os.makedirs(d, exist_ok=True)
                cmd = [
                    "robocopy", o, d, "/E", "/R:1", "/W:1",
                    "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
                ] + opcion_mt
            elif os.path.isfile(o):
                parent = os.path.dirname(d) or d
                os.makedirs(parent, exist_ok=True)
                dir_o, file_o = os.path.split(o)
                dir_d = d if os.path.isdir(d) else os.path.dirname(d)
                os.makedirs(dir_d, exist_ok=True)
                cmd = [
                    "robocopy", dir_o, dir_d, file_o, "/R:1", "/W:1",
                    "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
                ] + opcion_mt
            else:
                return False

            self._log("INFO", "Copiando: %s -> %s", o, d)
            resultado = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="cp437", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            # Robocopy: 0..7 son resultados no fatales; >=8 es fallo.
            ok = resultado.returncode < 8
            if not ok:
                self._log("ERROR", "Robocopy falló (%s): %s",
                          resultado.returncode, resultado.stderr.strip() or resultado.stdout.strip())
                return False

            if not os.path.exists(d):
                self._log("ERROR", "Robocopy terminó bien pero el destino no existe: %s", d)
                return False

            origen_tam = self._folder_size_bytes(o)
            destino_tam = self._folder_size_bytes(d)
            if origen_tam != destino_tam:
                self._log("ERROR", "Verificación de tamaño fallida: %s (%s) != %s (%s)",
                          o, origen_tam, d, destino_tam)
                return False

            self._log("INFO", "Copia verificada correctamente: %s -> %s", o, d)
            return True
        except FileNotFoundError:
            self._log("ERROR", "No se encontró robocopy. Solo está disponible normalmente en Windows.")
            return False
        except Exception as exc:
            self._log("ERROR", "Error copiando %s -> %s: %s", o, d, exc, exc_info=True)
            return False

    def _formatear_fecha_es(self, instante=None, separador=" "):
        """Devuelve una fecha visible en formato español: DD-MM-YYYY HH-MM-SS."""
        if instante is None:
            instante = time.time()
        try:
            return time.strftime("%d-%m-%Y %H-%M-%S", time.localtime(instante))
        except Exception:
            return "fecha-desconocida"

    def _parsear_fecha_backup_historico(self, texto):
        """Convierte una fecha de nombre de backup a timestamp.

        El único formato de backups históricos utilizado por esta versión es
        el formato español: DD-MM-YYYY HH-MM-SS.
        """
        texto = str(texto).strip()
        try:
            return datetime.strptime(texto, "%d-%m-%Y %H-%M-%S").timestamp()
        except (ValueError, OverflowError, OSError):
            return None

    def _es_backup_historico_con_fecha(self, nombre):
        """Indica si una carpeta corresponde a un backup histórico fechado.

        Formato: "Juego [DD-MM-YYYY HH-MM-SS]".
        """
        try:
            patron = r"\s\[\d{2}-\d{2}-\d{4}\s\d{2}-\d{2}-\d{2}(?:\s+#\d+)?\]$"
            return bool(re.search(patron, str(nombre).strip(), re.I))
        except Exception:
            return False

    def _nombre_backup_historico(self, dst_actual):
        """Genera el nombre histórico usando la fecha de modificación del backup.

        La fecha corresponde al backup que se está sustituyendo, no al momento
        en que se pulsa el botón. Se muestra en formato español:
        "DD-MM-YYYY HH-MM-SS".
        """
        base = os.path.basename(os.path.normpath(dst_actual))
        try:
            instante = os.path.getmtime(dst_actual)
        except (OSError, ValueError):
            instante = time.time()

        fecha = self._formatear_fecha_es(instante)
        nombre = f"{base} [{fecha}]"
        destino = os.path.join(os.path.dirname(dst_actual), nombre)

        contador = 2
        while os.path.exists(destino):
            nombre = f"{base} [{fecha} #{contador}]"
            destino = os.path.join(os.path.dirname(dst_actual), nombre)
            contador += 1
        return destino.replace("\\", "/")

    def _buscar_backup_historico_mas_reciente(self, game_root):
        """Busca la versión histórica más reciente de un juego.

        Se usa como respaldo cuando la carpeta activa (con el nombre limpio)
        ya no existe. La elección se hace por la fecha escrita en el nombre,
        no por la fecha de modificación de Windows, para que el resultado sea
        estable y visible para el usuario.
        """
        if not game_root:
            return None

        game_root = os.path.normpath(game_root).replace("\\", "/")
        padre = os.path.dirname(game_root)
        base = os.path.basename(game_root)
        if not os.path.isdir(padre):
            return None

        candidatos = []
        prefijo = f"{base} ["
        try:
            for nombre in os.listdir(padre):
                ruta = os.path.join(padre, nombre)
                if not os.path.isdir(ruta):
                    continue
                if not nombre.startswith(prefijo):
                    continue

                m = re.match(
                    rf"^{re.escape(base)} \["
                    rf"(\d{{2}}-\d{{2}}-\d{{4}}\s\d{{2}}-\d{{2}}-\d{{2}})"
                    rf"(?:\s+#\d+)?\]$",
                    nombre,
                    re.I
                )
                if not m:
                    continue

                instante = self._parsear_fecha_backup_historico(m.group(1))
                if instante is None:
                    continue
                candidatos.append((instante, nombre.lower(), ruta.replace("\\", "/")))

        except Exception as exc:
            self._log("ERROR", "No se pudieron buscar backups históricos de %s: %s",
                      game_root, exc, exc_info=True)
            return None

        if not candidatos:
            return None

        candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
        elegido = candidatos[0][2]
        self._log(
            "WARNING",
            "No existe el backup activo %s; se utilizará la copia histórica más reciente: %s",
            game_root, elegido
        )
        return elegido

    def rotar_a_old(self, dst_actual):
        """Archiva el backup actual junto a su backup activo, con fecha y hora.

        El backup más reciente conserva siempre el nombre original del juego:
            My Games/Borderlands 2

        Cuando se crea uno nuevo, el anterior pasa a ser, por ejemplo:
            My Games/Borderlands 2 [2026-09-26 03-20-15]

        Esto permite distinguir rápidamente versiones antiguas sin llenar la
        raíz de "Backup Saves" con carpetas old, old2, old3, etc.
        """
        if not os.path.exists(dst_actual):
            return None

        camino_historico = self._nombre_backup_historico(dst_actual)
        try:
            os.makedirs(os.path.dirname(camino_historico), exist_ok=True)
            shutil.move(dst_actual, camino_historico)
            self._log(
                "INFO",
                "Backup anterior archivado con fecha: %s -> %s",
                dst_actual, camino_historico
            )
            return camino_historico
        except Exception as exc:
            self._log(
                "ERROR",
                "No se pudo archivar backup %s: %s",
                dst_actual, exc, exc_info=True
            )
            return False

    def _purgar_backups_historicos_antiguos(self, game_root):
        """Aplica el límite configurable de copias históricas por juego
        (self.max_backups_historicos). rotar_a_old() archiva cada versión
        anterior con fecha, pero sin este límite "Backup Saves" crecería sin
        parar si se hace backup a diario durante meses.

        0 (o cualquier valor <= 0) significa "sin límite": comportamiento de
        siempre, no se borra nada. Con un límite > 0, se conserva siempre la
        copia activa (game_root, con el nombre limpio del juego) más como
        mucho ese número de copias históricas fechadas, empezando a borrar
        las más antiguas en cuanto se supera.
        """
        limite = getattr(self, "max_backups_historicos", 0) or 0
        if limite <= 0:
            return

        game_root_norm = os.path.normpath(game_root).replace("\\", "/")
        padre = os.path.dirname(game_root_norm)
        base = os.path.basename(game_root_norm)
        if not os.path.isdir(padre):
            return

        prefijo = f"{base} ["
        historicos = []
        try:
            for nombre in os.listdir(padre):
                if not nombre.startswith(prefijo):
                    continue
                ruta = os.path.join(padre, nombre).replace("\\", "/")
                if not os.path.isdir(ruta):
                    continue
                m = re.match(
                    rf"^{re.escape(base)} \["
                    rf"(\d{{2}}-\d{{2}}-\d{{4}}\s\d{{2}}-\d{{2}}-\d{{2}})"
                    rf"(?:\s+#\d+)?\]$",
                    nombre, re.I
                )
                if not m:
                    continue
                instante = self._parsear_fecha_backup_historico(m.group(1))
                historicos.append((instante if instante is not None else 0, ruta))
        except Exception as exc:
            self._log(
                "ERROR",
                "No se pudo aplicar el límite de copias históricas de %s: %s",
                game_root_norm, exc, exc_info=True
            )
            return

        if len(historicos) <= limite:
            return  # todavía no se ha superado el máximo configurado

        # Más reciente primero; todo lo que sobre por detrás del límite se
        # borra, empezando por lo más antiguo.
        historicos.sort(key=lambda x: x[0], reverse=True)
        for _, ruta in historicos[limite:]:
            try:
                shutil.rmtree(ruta, ignore_errors=False)
                self._log(
                    "INFO",
                    "Copia histórica eliminada por límite de %d copias/juego: %s",
                    limite, ruta
                )
            except Exception as exc:
                self._log(
                    "ERROR",
                    "No se pudo eliminar la copia histórica antigua %s: %s",
                    ruta, exc, exc_info=True
                )

    def _listar_todos_los_backups(self, game_root_backup):
        """Devuelve TODAS las copias de seguridad disponibles para un juego:
        la copia activa (si existe) más todas las históricas fechadas que
        haya junto a ella, ordenadas de la más reciente a la más antigua.

        Cada elemento de la lista es una tupla (timestamp, etiqueta, ruta).
        """
        candidatos = []
        if not game_root_backup:
            return candidatos

        game_root_norm = os.path.normpath(game_root_backup).replace("\\", "/")

        if os.path.exists(game_root_norm):
            try:
                instante = os.path.getmtime(game_root_norm)
            except OSError:
                instante = None
            etiqueta = "🟢 Copia actual" + (
                f" ({self._formatear_fecha_es(instante)})" if instante else ""
            )
            candidatos.append((instante, etiqueta, game_root_norm))

        padre = os.path.dirname(game_root_norm)
        base = os.path.basename(game_root_norm)
        prefijo = f"{base} ["
        if os.path.isdir(padre):
            try:
                for nombre in os.listdir(padre):
                    if not nombre.startswith(prefijo):
                        continue
                    ruta = os.path.join(padre, nombre).replace("\\", "/")
                    if not os.path.isdir(ruta):
                        continue
                    m = re.match(
                        rf"^{re.escape(base)} \["
                        rf"(\d{{2}}-\d{{2}}-\d{{4}}\s\d{{2}}-\d{{2}}-\d{{2}})"
                        rf"(?:\s+#\d+)?\]$",
                        nombre, re.I
                    )
                    if not m:
                        continue
                    instante = self._parsear_fecha_backup_historico(m.group(1))
                    etiqueta = "🗓️ Copia del " + (
                        self._formatear_fecha_es(instante) if instante is not None else nombre
                    )
                    candidatos.append((instante, etiqueta, ruta))
            except Exception as exc:
                self._log("ERROR", "No se pudieron listar backups históricos de %s: %s",
                          game_root_backup, exc, exc_info=True)

        candidatos.sort(key=lambda x: (x[0] is None, -(x[0] or 0)))
        return candidatos

    def _elegir_backup_para_restaurar(self, nombre_juego, candidatos):
        """Cuando hay más de una copia de seguridad disponible para un
        juego, pregunta al usuario qué quiere hacer, con 3 opciones:
          - Reciente: restaura la copia más reciente (a la izquierda).
          - Cancelar: no restaura nada (a la derecha).
          - Elegir cuál restaurar: abre un menú sencillo con la lista de
            copias disponibles y botones Aceptar/Cancelar.

        Se puede llamar desde el hilo de trabajo (backup/restauración): la
        ventana se crea en el hilo principal de Tkinter y esta función
        espera, de forma segura y sin congelar la interfaz, a que el
        usuario responda.

        Devuelve la ruta elegida, o None si el usuario cancela.
        """
        resultado = {"ruta": None}
        evento = threading.Event()

        def cerrar_y_liberar(ventana, ruta=None):
            resultado["ruta"] = ruta
            ventana.destroy()
            evento.set()

        def construir_ventana():
            try:
                top = tk.Toplevel(self.root)
                top.title("Varios backups encontrados")
                top.configure(bg="#2c3e50")
                top.resizable(False, False)
                top.transient(self.root)
                top.grab_set()
                top.protocol("WM_DELETE_WINDOW", lambda: cerrar_y_liberar(top, None))

                tk.Label(
                    top,
                    text=(f"Se han encontrado {len(candidatos)} copias de seguridad para:\n"
                          f"\"{nombre_juego}\"\n\n¿Qué copia quieres restaurar?"),
                    font=("Arial", 11, "bold"), fg="white", bg="#2c3e50",
                    justify="center", wraplength=360
                ).pack(padx=20, pady=(18, 14))

                f_fila = tk.Frame(top, bg="#2c3e50")
                f_fila.pack(padx=20, fill="x")
                f_fila.columnconfigure(0, weight=1, uniform="g")
                f_fila.columnconfigure(1, weight=1, uniform="g")

                tk.Button(
                    f_fila, text="🕐 Reciente", font=("Arial", 10, "bold"),
                    bg="#2ecc71", fg="white", bd=0, pady=8, cursor="hand2",
                    command=lambda: cerrar_y_liberar(top, candidatos[0][2])
                ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

                tk.Button(
                    f_fila, text="✖ Cancelar", font=("Arial", 10, "bold"),
                    bg="#e74c3c", fg="white", bd=0, pady=8, cursor="hand2",
                    command=lambda: cerrar_y_liberar(top, None)
                ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

                def abrir_elegir_manual():
                    top.destroy()
                    self._mostrar_menu_elegir_backup(nombre_juego, candidatos, resultado, evento)

                tk.Button(
                    top, text="📂 Elegir cuál restaurar", font=("Arial", 10, "bold"),
                    bg="#3498db", fg="white", bd=0, pady=8, cursor="hand2",
                    command=abrir_elegir_manual
                ).pack(padx=20, pady=(8, 18), fill="x")

                top.update_idletasks()
                self.centrar_ventana(top, top.winfo_width(), top.winfo_height())
            except Exception as exc:
                self._log("ERROR", "No se pudo mostrar el selector de backups: %s", exc, exc_info=True)
                # Si la ventana falla por lo que sea, mejor no bloquear la
                # operación entera: se usa la copia más reciente por defecto.
                resultado["ruta"] = candidatos[0][2] if candidatos else None
                evento.set()

        self.root.after(0, construir_ventana)
        evento.wait()
        return resultado["ruta"]

    def _mostrar_menu_elegir_backup(self, nombre_juego, candidatos, resultado, evento):
        """Menú sencillo para elegir manualmente qué copia de seguridad
        restaurar, con una lista y botones Aceptar/Cancelar. Siempre se
        llama desde el hilo principal de Tkinter (ver
        _elegir_backup_para_restaurar)."""
        top = tk.Toplevel(self.root)
        top.title("Elegir copia a restaurar")
        top.configure(bg="#2c3e50")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()

        def cerrar_y_liberar(ruta=None):
            resultado["ruta"] = ruta
            top.destroy()
            evento.set()

        top.protocol("WM_DELETE_WINDOW", lambda: cerrar_y_liberar(None))

        tk.Label(
            top, text=f"\"{nombre_juego}\"\nSelecciona la copia que quieres restaurar:",
            font=("Arial", 11, "bold"), fg="white", bg="#2c3e50",
            justify="center", wraplength=380
        ).pack(padx=20, pady=(18, 10))

        box = tk.Listbox(
            top, font=("Arial", 10), bg="#34495e", fg="white",
            selectbackground="#1abc9c", bd=0, highlightthickness=0,
            activestyle="none", selectmode="browse", width=48,
            height=max(3, min(8, len(candidatos)))
        )
        box.pack(padx=20, pady=(0, 12), fill="both", expand=True)
        for _, etiqueta, _ in candidatos:
            box.insert(tk.END, etiqueta)
        box.selection_set(0)

        f_btn = tk.Frame(top, bg="#2c3e50")
        f_btn.pack(padx=20, pady=(0, 18), fill="x")
        f_btn.columnconfigure(0, weight=1, uniform="g")
        f_btn.columnconfigure(1, weight=1, uniform="g")

        def aceptar():
            sel = box.curselection()
            if not sel:
                mb.showwarning("Atención", "Selecciona una copia de la lista.", parent=top)
                return
            cerrar_y_liberar(candidatos[sel[0]][2])

        tk.Button(f_btn, text="✔ Aceptar", font=("Arial", 10, "bold"), bg="#2ecc71",
                  fg="white", bd=0, pady=8, cursor="hand2", command=aceptar
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        tk.Button(f_btn, text="✖ Cancelar", font=("Arial", 10, "bold"), bg="#e74c3c",
                  fg="white", bd=0, pady=8, cursor="hand2", command=lambda: cerrar_y_liberar(None)
                  ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        top.update_idletasks()
        ancho = max(top.winfo_width(), 420)
        alto = max(top.winfo_height(), 320)
        self.centrar_ventana(top, ancho, alto)

    def mostrar_submenu_ocultos(self):
        if not self.ocultos:
            mb.showinfo("Ocultos", "No tienes ningún elemento en la lista de ocultos actualmente.")
            return
        ventana_ocultos = tk.Toplevel(self.root)
        ventana_ocultos.title("Elementos Ocultados")
        ventana_ocultos.geometry("380x450")
        self.centrar_ventana(ventana_ocultos, 380, 450)
        ventana_ocultos.configure(bg="#2c3e50")
        ventana_ocultos.grab_set()
        tk.Label(ventana_ocultos, text="Lista de Elementos Ocultados", font=("Arial", 12, "bold"),
                 fg="#1abc9c", bg="#2c3e50").pack(pady=10)
        box_ocultos = tk.Listbox(ventana_ocultos, font=("Arial", 11), bg="#34495e", fg="white",
                                 selectbackground="#1abc9c", bd=0, highlightthickness=0,
                                 selectmode="multiple")
        box_ocultos.pack(padx=15, pady=5, fill="both", expand=True)
        for item in sorted(list(self.ocultos)):
            box_ocultos.insert(tk.END, item)

        def restaurar_elementos_multiples():
            selección = box_ocultos.curselection()
            if not selección:
                mb.showwarning("Atención", "Selecciona uno o varios elementos de la lista para restaurarlos.",
                               parent=ventana_ocultos)
                return
            elementos_a_quitar = [box_ocultos.get(idx) for idx in selección]
            if mb.askyesno("Restaurar", f"¿Quieres volver a mostrar los {len(elementos_a_quitar)} elementos seleccionados en el escáner principal?",
                           parent=ventana_ocultos):
                for nombre_item in elementos_a_quitar:
                    if nombre_item in self.ocultos:
                        self.ocultos.remove(nombre_item)
                self.save_data(M_O, self.ocultos)
                box_ocultos.delete(0, tk.END)
                for item in sorted(list(self.ocultos)):
                    box_ocultos.insert(tk.END, item)
                self.scan()
                if not self.ocultos:
                    ventana_ocultos.destroy()

        tk.Button(ventana_ocultos, text="✅ Volver a mostrar seleccionado(s)",
                  command=restaurar_elementos_multiples, bg="#2ecc71", fg="white",
                  font=("Arial", 10, "bold"), bd=0, pady=8, cursor="hand2").pack(fill="x", padx=15, pady=15)

    def hide(self):
        lista_seleccionados = self.get_sel_list()
        if lista_seleccionados:
            if mb.askyesno("Ocultar", f"¿Quieres ocultar los {len(lista_seleccionados)} elementos seleccionados de la vista?"):
                for tag_juego in lista_seleccionados:
                    nombre_limpio = self.limpiar_nombre_juego(tag_juego)
                    self.ocultos.add(nombre_limpio)
                self.save_data(M_O, self.ocultos)
                self.scan()

    def añadir_carpeta_manual(self):
        ruta_seleccionada = fd.askdirectory(title="Selecciona la carpeta donde están las partidas guardadas")
        if not ruta_seleccionada:
            return
        nombre_juego = sd.askstring("Nombre del Juego", "¿Qué nombre quieres darle a este juego en la lista?")
        if not nombre_juego or not nombre_juego.strip():
            mb.showwarning("Atención", "Debes asignar un nombre válido para identificar la carpeta.")
            return
        nombre_juego = nombre_juego.strip()
        self.manuales[nombre_juego] = ruta_seleccionada.replace("\\", "/")
        lineas_a_guardar = [f"{k}|||{v}" for k, v in self.manuales.items()]
        self.save_data(M_M, lineas_a_guardar)
        mb.showinfo("Éxito", f"¡Se ha añadido '{nombre_juego}' correctamente! El sistema volverá a escanear.")
        self.scan()

    def quitar_carpeta_manual(self):
        lista_seleccionados = self.get_sel_list()
        if not lista_seleccionados:
            mb.showwarning("Atención", "Por favor, selecciona uno o varios elementos manuales de la lista para quitarlos.")
            return
        manuales_a_eliminar = []
        for tag_seleccionado in lista_seleccionados:
            nombre_limpio = self.limpiar_nombre_juego(tag_seleccionado)
            if nombre_limpio in self.manuales:
                manuales_a_eliminar.append(nombre_limpio)
        if not manuales_a_eliminar:
            mb.showwarning("Atención", "Ninguno de los elementos seleccionados pertenece a la lista de carpetas manuales.")
            return
        if mb.askyesno("Quitar Manual", f"¿Quieres quitar los {len(manuales_a_eliminar)} juegos manuales seleccionados de la lista?\n(Esto NO borrará tus partidas guardadas del disco)."):
            for juego in manuales_a_eliminar:
                if juego in self.manuales:
                    del self.manuales[juego]
            lineas_a_guardar = [f"{k}|||{v}" for k, v in self.manuales.items()]
            self.save_data(M_M, lineas_a_guardar)
            self.scan()

    def load_manuales(self, path):
        if not os.path.exists(path):
            return {}
        dict_manuales = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for linea in f:
                    if "|||" in linea:
                        partes = linea.strip().split("|||")
                        if len(partes) == 2:
                            dict_manuales[partes[0]] = partes[1]
            return dict_manuales
        except Exception:
            return {}

    def load_carpetas(self, path):
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [linea.strip().replace("\\", "/") for linea in f if linea.strip()]
        except Exception:
            return []

    def gestionar_carpetas_sin_launcher(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Juegos sin Launcher (DRM-free / portables)")
        ventana.geometry("480x440")
        self.centrar_ventana(ventana, 480, 440)
        ventana.configure(bg="#2c3e50")
        ventana.grab_set()
        tk.Label(ventana, text="Juegos sin Launcher", font=("Arial", 12, "bold"),
                 fg="#1abc9c", bg="#2c3e50").pack(pady=10)
        tk.Label(ventana,
                 text="Cada subcarpeta directa dentro de estas rutas se tratará\n"
                      "como un posible juego (p. ej. instalaciones DRM-free de\n"
                      "GOG o ejecutables portables), cruzándose por nombre con\n"
                      "la base de datos de Arlequin-SaveHub igual que el resto.",
                 font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50", justify="left").pack(pady=(0, 8), padx=15)
        box = tk.Listbox(ventana, font=("Arial", 10), bg="#34495e", fg="white",
                          selectbackground="#1abc9c", bd=0, highlightthickness=0,
                          selectmode="multiple")
        box.pack(padx=15, pady=5, fill="both", expand=True)
        for c in self.carpetas_sin_launcher:
            box.insert(tk.END, c)

        def añadir():
            r = fd.askdirectory(title="Selecciona la carpeta raíz de tus juegos sin launcher")
            if r:
                r = r.replace("\\", "/")
                if r not in self.carpetas_sin_launcher:
                    self.carpetas_sin_launcher.append(r)
                    box.insert(tk.END, r)
                    self.save_data(M_C, self.carpetas_sin_launcher)

        def quitar():
            seleccion = box.curselection()
            if not seleccion:
                mb.showwarning("Atención", "Selecciona una o varias carpetas para quitarlas.", parent=ventana)
                return
            elementos = [box.get(i) for i in seleccion]
            for e in elementos:
                if e in self.carpetas_sin_launcher:
                    self.carpetas_sin_launcher.remove(e)
            for i in reversed(seleccion):
                box.delete(i)
            self.save_data(M_C, self.carpetas_sin_launcher)

        f_btns = tk.Frame(ventana, bg="#2c3e50")
        f_btns.pack(fill="x", padx=15, pady=10)
        tk.Button(f_btns, text="➕ Añadir carpeta", command=añadir, bg="#2ecc71", fg="white",
                  font=("Arial", 9, "bold"), bd=0, pady=6, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(f_btns, text="➖ Quitar seleccionada(s)", command=quitar, bg="#e67e22", fg="white",
                  font=("Arial", 9, "bold"), bd=0, pady=6, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(5, 0))

        def cerrar_y_reescanear():
            ventana.destroy()
            self.ejecutar_en_hilo(self.scan)

        tk.Button(ventana, text="✅ Cerrar y reescanear", command=cerrar_y_reescanear, bg="#3498db",
                  fg="white", font=("Arial", 10, "bold"), bd=0, pady=8, cursor="hand2").pack(fill="x", padx=15, pady=(0, 15))

    def _folder_size_bytes(self, path):
        """Devuelve el tamaño en bytes. Usa una caché breve para no recorrer
        repetidamente carpetas grandes durante cada refresco de la interfaz.
        Puede llamarse desde varios hilos a la vez (ver
        _precalentar_tamanos_en_paralelo): el acceso a la caché va protegido
        por un lock, y el recorrido de la carpeta en sí no toca estado
        compartido, así que es seguro en paralelo."""
        if not path or not os.path.exists(path):
            return 0
        try:
            clave = os.path.normcase(os.path.abspath(path))
            ahora = time.monotonic()
            try:
                marca = os.path.getmtime(path)
            except OSError:
                marca = 0

            lock = self._size_cache_lock
            with lock:
                anterior = self._size_cache.get(clave)
            if anterior and ahora - anterior[0] < 5 and anterior[1] == marca:
                return anterior[2]

            if os.path.isdir(path):
                total_size = _tamano_carpeta_bytes(path)
            else:
                total_size = os.path.getsize(path)

            with lock:
                self._size_cache[clave] = (ahora, marca, total_size)
            return total_size
        except Exception:
            return 0

    def _precalentar_tamanos_en_paralelo(self, rutas):
        """Calcula el tamaño de varias carpetas de saves EN PARALELO (con
        hilos) y deja el resultado en la caché de _folder_size_bytes, para
        que las llamadas posteriores y secuenciales a get_folder_size_str /
        get_rutas_size_str (que sí deben mantener su orden para construir la
        lista de la interfaz) sean prácticamente instantáneas.

        Calcular tamaños es trabajo de E/S, no de CPU (se pasa la mayor
        parte del tiempo esperando al disco, no calculando), así que varias
        carpetas a la vez con ThreadPoolExecutor aceleran bastante el primer
        escaneo con muchos juegos, sobre todo si "Backup Saves" vive en un
        disco distinto o más lento que el del sistema."""
        rutas_unicas = sorted({r for r in rutas if r and os.path.exists(r)})
        if not rutas_unicas:
            return
        max_hilos = min(8, len(rutas_unicas))
        try:
            with ThreadPoolExecutor(max_workers=max_hilos) as executor:
                # list(...) para esperar a que terminen todos los hilos antes
                # de continuar; el resultado en sí no se usa (ya queda en la
                # caché), solo nos interesa el efecto secundario.
                list(executor.map(self._folder_size_bytes, rutas_unicas))
        except Exception:
            # Si algo falla calentando la caché en paralelo, no pasa nada
            # grave: el código de siempre recalculará lo que falte, solo que
            # de una en una en vez de a la vez.
            pass

    def get_folder_size_str(self, path):
        if not path or not os.path.exists(path):
            return "No Encontrada"
        try:
            return self._formatear_bytes(self._folder_size_bytes(path))
        except Exception:
            return "Error Tam."

    def get_rutas_size_str(self, rutas):
        """Tamaño combinado de una o varias carpetas de save del MISMO juego
        (se usa para fusionar duplicados en una sola línea de la lista)."""
        if not rutas:
            return "No Encontrada"
        if isinstance(rutas, str):
            return self.get_folder_size_str(rutas)
        total = sum(self._folder_size_bytes(r) for r in rutas)
        return self._formatear_bytes(total)

    def _ruta_es_demasiado_amplia(self, ruta):
        """Comprueba si `ruta` es una de las carpetas compartidas por todos
        los juegos (Documents, AppData, My Games...) o el perfil entero del
        usuario. Última red de seguridad antes de tocar disco de verdad,
        para cualquier vía de entrada (manifest, carpeta añadida a mano...)."""
        try:
            carpetas_peligrosas = _carpetas_contenedoras_compartidas(entorno_windows_base())
            return _ruta_es_contenedor_compartido(ruta, carpetas_peligrosas)
        except Exception:
            return False

    def _juego_parece_en_ejecucion(self, tag_seleccionado):
        """Comprueba si el juego correspondiente a esta línea de la lista
        parece seguir abierto ahora mismo, para los juegos "conocidos" (los
        detectados vía registro/instalador de Steam/Epic/GOG/Battle.net/
        Ubisoft/EA/Amazon/Xbox o carpetas sin launcher, de los que se conoce su carpeta de
        instalación). Para el resto (carpetas añadidas a mano, entradas
        "solo en backup" de juegos desinstalados...) no hay .exe que
        comprobar y se devuelve None sin más.

        Devuelve el nombre del .exe detectado como en ejecución, o None si
        no está en marcha o no se pudo determinar."""
        installdir = (self.juegos_installdir or {}).get(tag_seleccionado, "")
        if not installdir:
            return None

        if installdir not in self._exes_cache:
            self._exes_cache[installdir] = _detectar_exes_candidatos(installdir)
        candidatos = self._exes_cache[installdir]
        if not candidatos:
            return None

        procesos_activos = _listar_procesos_en_ejecucion()
        if not procesos_activos:
            return None

        for exe in candidatos:
            if exe in procesos_activos:
                return exe
        return None

    def _confirmar_continuar_con_juego_activo(self, nombre_juego, exe_detectado, accion):
        """Avisa (de forma segura desde el hilo de trabajo, igual que
        _elegir_backup_para_restaurar) de que el juego parece seguir
        abierto, y pregunta si se quiere continuar de todas formas.

        accion: "backup" o "restore", solo para adaptar el texto del aviso.
        Devuelve True si el usuario quiere continuar igualmente."""
        resultado = {"continuar": False}
        evento = threading.Event()

        if accion == "backup":
            verbo = "hacer una copia de seguridad de"
            riesgo = ("la copia puede quedar incompleta o corrupta si el "
                      "juego está guardando partida justo en este momento")
        else:
            verbo = "restaurar"
            riesgo = ("se puede sobrescribir una partida activa y perder "
                      "progreso, o que el propio juego vuelva a sobrescribir "
                      "la copia restaurada en cuanto guarde de nuevo")

        def preguntar():
            try:
                continuar = mb.askyesno(
                    "El juego parece seguir abierto",
                    f"Parece que \"{nombre_juego}\" sigue en ejecución "
                    f"(proceso detectado: {exe_detectado}).\n\n"
                    f"Vas a {verbo} este juego mientras sigue abierto: "
                    f"{riesgo}.\n\n"
                    "Se recomienda cerrar el juego antes de continuar.\n\n"
                    "¿Quieres continuar de todas formas?",
                    parent=self.root
                )
            except Exception:
                continuar = False
            resultado["continuar"] = continuar
            evento.set()

        self.root.after(0, preguntar)
        evento.wait()
        return resultado["continuar"]

    def op(self, mode):
        lista_seleccionados = self.get_sel_list()
        if not lista_seleccionados:
            self.root.after(0, lambda: mb.showwarning(
                "Atención",
                "Por favor, selecciona uno o varios elementos de la lista haciendo clic sobre ellos."
            ))
            return

        exitosas = 0
        fallidas = []
        total_juegos = 0
        restauracion_cancelada = False

        for tag_seleccionado in lista_seleccionados:
            if tag_seleccionado not in self.juegos:
                continue
            origen = self.juegos[tag_seleccionado]
            if not origen:
                continue

            origenes = [origen] if isinstance(origen, str) else list(origen)
            nombre_limpio = self.limpiar_nombre_juego(tag_seleccionado)
            total_juegos += 1
            juego_ok = True

            # NUEVO: para juegos "conocidos" (con carpeta de instalación
            # detectada vía launcher/instalador), se comprueba si el .exe
            # del juego sigue en ejecución antes de tocar sus saves. Si es
            # así, se avisa y se deja elegir si continuar o no.
            exe_en_marcha = self._juego_parece_en_ejecucion(tag_seleccionado)
            if exe_en_marcha:
                accion = "backup" if mode == 1 else "restore"
                if not self._confirmar_continuar_con_juego_activo(nombre_limpio, exe_en_marcha, accion):
                    fallidas.append(
                        f"{nombre_limpio}: cancelado (el juego seguía en ejecución: {exe_en_marcha})"
                    )
                    continue

            # -----------------------------------------------------------------
            # BACKUP
            # -----------------------------------------------------------------
            if mode == 1:
                # Se copia la carpeta COMPLETA del juego tal cual está en su
                # ubicación de búsqueda (My Games, Saved Games, AppData...),
                # con todo lo que tenga dentro (Config, Logs, SaveData,
                # PersistentDownloadDir, etc.), no solo la subcarpeta de save
                # que apunta el manifest. Si varios orígenes del mismo juego
                # caen dentro de la misma carpeta raíz, solo se copia una vez.
                raices_vistas = set()
                for orig in origenes:
                    if not orig:
                        juego_ok = False
                        continue
                    ruta_real = orig if os.path.isabs(orig) else os.path.join(UP, orig)
                    ruta_real = os.path.normpath(ruta_real).replace("\\", "/")
                    if not os.path.exists(ruta_real):
                        fallidas.append(f"{nombre_limpio}: origen no existe ({ruta_real})")
                        juego_ok = False
                        continue

                    raiz_pc = self._pc_game_root(ruta_real, nombre_limpio)
                    if raiz_pc in raices_vistas:
                        continue
                    raices_vistas.add(raiz_pc)

                    # Red de seguridad final: por mucho que el manifest ya se
                    # haya filtrado, una carpeta añadida a mano ("➕ Añadir
                    # Manual") podría apuntar por error a una carpeta
                    # compartida por todos los juegos (Documents, AppData, o
                    # el perfil entero). Nunca se respalda algo así.
                    if self._ruta_es_demasiado_amplia(raiz_pc):
                        fallidas.append(
                            f"{nombre_limpio}: {raiz_pc} es una carpeta compartida por "
                            "todos los juegos (o el perfil entero); no se respalda por seguridad."
                        )
                        juego_ok = False
                        continue

                    game_root = self._backup_game_root(ruta_real, nombre_limpio)
                    tmp_root = game_root + f".__tmp_game_{uuid.uuid4().hex[:8]}"
                    antiguo_backup = None
                    try:
                        if os.path.exists(tmp_root):
                            shutil.rmtree(tmp_root, ignore_errors=True)

                        # Primero se copia la carpeta del juego ENTERA a una
                        # carpeta temporal. Así nunca dejamos un backup a medias.
                        if not self.run_cmd(raiz_pc, tmp_root):
                            raise RuntimeError(f"fallo copiando {raiz_pc}")

                        # Solo después de verificar la copia se archiva la
                        # versión anterior completa del juego.
                        antiguo_backup = self.rotar_a_old(game_root)
                        if antiguo_backup is False:
                            raise RuntimeError("no se pudo apartar el backup anterior")

                        os.makedirs(os.path.dirname(game_root), exist_ok=True)
                        try:
                            os.replace(tmp_root, game_root)
                        except Exception:
                            # Rollback: si no podemos instalar la nueva carpeta,
                            # recuperamos la versión anterior completa.
                            if antiguo_backup and os.path.exists(antiguo_backup) and not os.path.exists(game_root):
                                shutil.move(antiguo_backup, game_root)
                            raise

                        self._log("INFO", "Backup nuevo instalado: %s", game_root)
                        # NUEVO: aplica el máximo configurable de copias
                        # históricas para este juego, borrando las más
                        # antiguas si se ha superado el límite.
                        self._purgar_backups_historicos_antiguos(game_root)
                    except Exception as exc:
                        if os.path.exists(tmp_root):
                            shutil.rmtree(tmp_root, ignore_errors=True)
                        self._log(
                            "ERROR",
                            "Backup transaccional fallido para %s: %s",
                            nombre_limpio, exc, exc_info=True
                        )
                        fallidas.append(f"{nombre_limpio}: {exc}")
                        juego_ok = False

            # -----------------------------------------------------------------
            # RESTORE
            # -----------------------------------------------------------------
            elif mode == 2:
                # Simétrico al backup: se restaura la carpeta COMPLETA del
                # juego (todo lo que se guardó en el backup), no solo una
                # subcarpeta concreta. Si ya había algo en el destino, se
                # archiva con fecha y hora antes de pegar la restaurada, así
                # nunca se pierde. Esto se aplica igual a cualquier juego con
                # varias carpetas de búsqueda (My Games, Saved Games,
                # AppData...) sin tratarlos caso por caso.
                raices_vistas = set()
                for orig in origenes:
                    if not orig:
                        juego_ok = False
                        continue

                    ruta_real = orig if os.path.isabs(orig) else os.path.join(UP, orig)
                    ruta_real = os.path.normpath(ruta_real).replace("\\", "/")
                    _dst_ignorado, ruta_real = self.r_path(ruta_real, nombre_limpio)

                    raiz_pc = self._pc_game_root(ruta_real, nombre_limpio)
                    if raiz_pc in raices_vistas:
                        continue
                    raices_vistas.add(raiz_pc)

                    # Misma red de seguridad que en el backup: nunca se
                    # restaura ENCIMA de una carpeta compartida por todos los
                    # juegos (o el perfil entero), aunque venga de una
                    # carpeta añadida a mano.
                    if self._ruta_es_demasiado_amplia(raiz_pc):
                        fallidas.append(
                            f"{nombre_limpio}: {raiz_pc} es una carpeta compartida por "
                            "todos los juegos (o el perfil entero); no se restaura por seguridad."
                        )
                        juego_ok = False
                        continue

                    game_root_backup_base = self._backup_game_root(ruta_real, nombre_limpio)

                    # Se listan TODAS las copias disponibles para este juego
                    # (la activa + las históricas fechadas). Si solo hay una,
                    # se usa directamente como antes. Si hay más de una, se
                    # le pregunta al usuario cuál quiere restaurar en vez de
                    # asumir siempre la más reciente.
                    candidatos_backup = self._listar_todos_los_backups(game_root_backup_base)

                    if not candidatos_backup:
                        fallidas.append(f"{nombre_limpio}: no existe el backup ({game_root_backup_base})")
                        juego_ok = False
                        continue

                    if len(candidatos_backup) == 1:
                        game_root_backup = candidatos_backup[0][2]
                    else:
                        elegido = self._elegir_backup_para_restaurar(nombre_limpio, candidatos_backup)
                        if not elegido:
                            self._log("INFO", "Restauración de %s cancelada por el usuario.", nombre_limpio)
                            fallidas.append(f"{nombre_limpio}: restauración cancelada por el usuario")
                            juego_ok = False
                            restauracion_cancelada = True
                            break
                        game_root_backup = elegido
                        self._log(
                            "INFO", "Restaurando %s desde la copia elegida por el usuario: %s",
                            nombre_limpio, game_root_backup
                        )

                    tmp_root = raiz_pc + f".__tmp_restore_game_{uuid.uuid4().hex[:8]}"
                    archivo_raiz = None
                    try:
                        if os.path.exists(tmp_root):
                            shutil.rmtree(tmp_root, ignore_errors=True)

                        # Primero se copia el backup ENTERO a una carpeta
                        # temporal, verificando la copia. Así nunca se llega
                        # a tocar el save actual si algo falla a mitad de
                        # camino.
                        if not self.run_cmd(game_root_backup, tmp_root):
                            raise RuntimeError(f"el backup no supera la verificación ({game_root_backup})")

                        # Ya con todo verificado: si ya había una carpeta del
                        # juego en el PC, se archiva ENTERA con fecha y hora
                        # antes de pegar la restaurada.
                        if os.path.exists(raiz_pc):
                            archivo_raiz = self._nombre_backup_historico(raiz_pc)
                            shutil.move(raiz_pc, archivo_raiz)

                        os.makedirs(os.path.dirname(raiz_pc), exist_ok=True)
                        try:
                            os.replace(tmp_root, raiz_pc)
                        except Exception:
                            if archivo_raiz and os.path.exists(archivo_raiz) and not os.path.exists(raiz_pc):
                                shutil.move(archivo_raiz, raiz_pc)
                            raise

                        self._log("INFO", "Restauración completada: %s", raiz_pc)
                    except Exception as exc:
                        if os.path.exists(tmp_root):
                            shutil.rmtree(tmp_root, ignore_errors=True)
                        self._log("ERROR", "Restauración fallida para %s: %s", nombre_limpio, exc, exc_info=True)
                        fallidas.append(f"{nombre_limpio}: {exc}")
                        juego_ok = False

            if juego_ok:
                exitosas += 1

            if restauracion_cancelada:
                break

        def finalizar_operacion():
            if restauracion_cancelada:
                mb.showinfo(
                    "Restauración cancelada",
                    "Restauración cancelada por el usuario.\n\n"
                    f"Juegos restaurados antes de cancelar: {exitosas}/{total_juegos}"
                )
                self.ejecutar_en_hilo(self.scan)
                return
            accion = "backup" if mode == 1 else "restauración"
            if fallidas:
                detalle = "\n".join(f"• {x}" for x in fallidas[:12])
                extra = "" if len(fallidas) <= 12 else f"\n… y {len(fallidas)-12} errores más."
                mb.showwarning(
                    "Operación finalizada",
                    f"{accion.capitalize()} completado.\n\n"
                    f"Juegos correctos: {exitosas}/{total_juegos}\n"
                    f"Problemas: {len(fallidas)}\n\n{detalle}{extra}"
                )
            else:
                mb.showinfo(
                    "Operación completada",
                    f"¡{accion.capitalize()} completado!\n\n"
                    f"Juegos correctos: {exitosas}/{total_juegos}"
                )
            self.ejecutar_en_hilo(self.scan)

        self.root.after(0, finalizar_operacion)

    def indexar_backups_en_disco(self):
        """Indexa backups tanto en el formato nuevo agrupado como en el antiguo.

        Formato nuevo:
            Backup Saves/
                My Games/
                    Borderlands 2/
                    Otro juego/
                AppData/
                    Roaming/...?

        Cada carpeta de juego es un backup principal. Las carpetas old/old2/...
        y las carpetas de versión con fecha quedan fuera del índice porque son
        históricos; solo la carpeta con el nombre del juego a secas es la activa.
        """
        self.backups_existentes.clear()
        if not os.path.exists(self.dest) or not os.path.isdir(self.dest):
            return

        try:
            for elemento in os.listdir(self.dest):
                ruta_grupo = os.path.join(self.dest, elemento)
                if not os.path.isdir(ruta_grupo):
                    continue
                if re.fullmatch(r"old\d*", elemento.strip(), re.I):
                    continue

                # Compatibilidad con el formato antiguo: Backup Saves/Juego
                # se considera directamente un backup principal si contiene
                # archivos (o subcarpetas de datos) y no parece ser un grupo.
                hijos = []
                try:
                    hijos = [x for x in os.listdir(ruta_grupo)
                             if os.path.isdir(os.path.join(ruta_grupo, x))]
                except Exception:
                    pass

                archivos_directos = False
                try:
                    archivos_directos = any(
                        os.path.isfile(os.path.join(ruta_grupo, x))
                        for x in os.listdir(ruta_grupo)
                    )
                except Exception:
                    pass

                if archivos_directos or not hijos:
                    self.backups_existentes.add(elemento.lower().strip())
                    continue

                # Formato nuevo: grupo/juego. Solo indexamos el segundo nivel.
                # Los backups históricos fechados NO son el backup activo; el
                # activo es siempre el que conserva el nombre del juego a secas.
                for juego in hijos:
                    ruta_juego = os.path.join(ruta_grupo, juego)
                    if re.fullmatch(r"old\d*", juego.strip(), re.I):
                        continue
                    if self._es_backup_historico_con_fecha(juego):
                        continue
                    self.backups_existentes.add(
                        os.path.join(elemento, juego).replace("\\", "/").lower().strip()
                    )

            self._log("INFO", "Backups indexados: %d", len(self.backups_existentes))
        except Exception as exc:
            self._log("ERROR", "No se pudo indexar backups: %s", exc, exc_info=True)

    def load_ocultos(self, path):
        if not os.path.exists(path):
            return set()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set([linea.strip() for linea in f if linea.strip()])
        except Exception:
            return set()

    def save_data(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                for item in sorted(list(data)):
                    f.write(f"{item}\n")
        except Exception:
            pass

    # -- NUEVO: configuración general (máximo de copias históricas/juego) --

    def _cargar_max_backups(self):
        """Lee de disco el máximo de copias históricas por juego que el
        usuario haya configurado desde el desplegable. 0 = sin límite
        (comportamiento de siempre, es el valor por defecto)."""
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                valor = int(datos.get("max_backups_historicos", 0))
                return valor if valor > 0 else 0
        except Exception as exc:
            self._log("ERROR", "No se pudo leer config.json: %s", exc, exc_info=True)
        return 0

    def _guardar_max_backups(self, valor):
        """Guarda el máximo de copias históricas por juego en config.json,
        conservando cualquier otra clave que ya hubiera en el fichero."""
        datos = {}
        if os.path.exists(M_CFG):
            try:
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
            except Exception:
                datos = {}
        datos["max_backups_historicos"] = int(valor)
        try:
            with open(M_CFG, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._log("ERROR", "No se pudo guardar config.json: %s", exc, exc_info=True)

    def _cambiar_max_backups(self, valor_texto):
        """Se llama al elegir una opción del desplegable "Máx. copias/juego"
        (junto al botón de X/Twitter). Solo afecta a partir del próximo
        backup de cada juego: no borra de golpe copias que ya excedieran el
        nuevo límite, eso ocurre la próxima vez que se archive una nueva."""
        nuevo = 0 if valor_texto == "Sin límite" else int(valor_texto)
        self.max_backups_historicos = nuevo
        self._guardar_max_backups(nuevo)
        self._log(
            "INFO", "Máximo de copias históricas por juego cambiado a: %s",
            "sin límite" if nuevo == 0 else nuevo
        )

    # -- NUEVO: base de datos Arlequin-SaveHub + detección vía launchers ---

    def actualizar_base_de_datos(self, forzar=False):
        """Descarga/lee la base de datos de Arlequin-SaveHub y construye los índices de
        búsqueda. Se llama SIEMPRE en segundo plano, después de que la
        ventana ya esté abierta."""
        def avisar(texto, color):
            self.root.after(0, lambda: self.lbl_db_status.config(text=texto, fg=color))

        avisar("⏳ Actualizando base de datos de saves (Arlequin-SaveHub)...", "#f1c40f")
        (self.manifest, self.manifest_total_juegos, self.manifest_por_nombre,
         self.manifest_por_steam_id, self.manifest_por_gog_id) = descargar_manifest(forzar=forzar)
        if self.manifest:
            avisar(f"{self.manifest_total_juegos:,} juegos".replace(",", "."), "#2ecc71")
            self._log(
                "INFO",
                "Base de datos cargada: %d juegos en YAML; %d juegos indexados.",
                self.manifest_total_juegos,
                len(self.manifest),
            )
        else:
            avisar("⚠️ No se pudo descargar la base de datos (sin conexión). Reintenta más tarde.", "#e67e22")

    def actualizar_bd_y_escanear(self, forzar=False):
        self.actualizar_base_de_datos(forzar=forzar)
        self.scan()

    def buscar_en_manifest(self, info_juego):
        """Busca primero por identificador exacto y después por nombre.
        Las coincidencias aproximadas requieren una similitud alta y única,
        evitando cruzar juegos con nombres parecidos por simple subcadena."""
        store = LAUNCHER_A_STORE.get(info_juego.get("launcher"))
        id_juego = str(info_juego.get("id") or "").strip()

        # Si el launcher proporciona un ID real, ese ID es la identidad
        # principal del juego. No debemos caer al nombre si el ID existe en
        # el detector pero NO existe en nuestra BD: dos juegos distintos
        # pueden compartir exactamente el mismo nombre (caso real: Delta
        # Force clásico frente al Delta Force moderno de Steam).
        #
        # Solo usamos el nombre como respaldo cuando el launcher no nos ha
        # proporcionado ningún ID utilizable.
        if store == "steam" and id_juego:
            encontrado = self.manifest_por_steam_id.get(id_juego)
            return encontrado
        if store == "gog" and id_juego:
            encontrado = self.manifest_por_gog_id.get(id_juego)
            return encontrado

        n = _norm(info_juego.get("nombre"))
        if not n:
            return None
        if n in self.manifest_por_nombre:
            return self.manifest_por_nombre[n]

        # Las carpetas encontradas fuera de un launcher no deben usar el
        # fuzzy matching general para decidir entre ediciones. Por ejemplo,
        # "GTA V" y "Grand Theft Auto V Enhanced" son muy parecidos, pero
        # una carpeta llamada "GTA V" pertenece al título Legacy, no a
        # Enhanced. Para "Carpeta" aceptamos únicamente el nombre exacto o
        # un acrónimo/alias exacto declarado en la propia ficha.
        if info_juego.get("launcher") == "Carpeta":
            # manifest_por_nombre ya contiene nombres y acrónimos exactos.
            # Antes se recorrían las ~12.000 fichas una por una aquí, aunque
            # el índice ya estaba construido. Ahora es O(1).
            return self.manifest_por_nombre.get(n)

        # Primero aceptamos equivalencia por palabras, pero solo si una
        # ficha es claramente más parecida que las demás.
        #
        # RENDIMIENTO: con un manifest de varios miles de fichas, este bucle
        # se ejecuta por cada juego instalado que no tuvo match exacto, así
        # que aquí es donde más se nota el coste. Dos optimizaciones:
        #   1) Se reutiliza un único SequenceMatcher en vez de crear uno
        #      nuevo (con toda su inicialización interna) en cada vuelta.
        #      set_seq2() fija la cadena buscada una sola vez fuera del
        #      bucle; dentro solo cambia set_seq1(), que es la parte barata.
        #   2) Se descartan candidatos por longitud antes de calcular el
        #      ratio completo, usando la cota superior REAL de
        #      SequenceMatcher.ratio(): ratio = 2*M/(len_a+len_b), y como
        #      el número de caracteres coincidentes M nunca puede superar
        #      min(len_a, len_b), el ratio máximo posible entre dos cadenas
        #      es 2*min(len_a,len_b)/(len_a+len_b). Si ese máximo ya está
        #      por debajo de 0.90 (y ninguna es subcadena de la otra),
        #      ratio() nunca podría llegar al umbral, así que ni se calcula.
        matcher = SequenceMatcher(None, autojunk=False)
        matcher.set_seq2(n)
        len_n = len(n)
        candidatos = []
        for k_norm, k_real in self.manifest_por_nombre.items():
            len_k = len(k_norm)
            if not len_k:
                continue
            es_subcadena = n in k_norm or k_norm in n
            cota_superior_ratio = 2 * min(len_n, len_k) / (len_n + len_k)
            if not es_subcadena and cota_superior_ratio < 0.90:
                continue
            matcher.set_seq1(k_norm)
            ratio = matcher.ratio()
            if es_subcadena:
                ratio = max(ratio, min(len_n, len_k) / max(len_n, len_k))
            if ratio >= 0.90:
                candidatos.append((ratio, k_real))

        if candidatos:
            candidatos.sort(key=lambda x: x[0], reverse=True)
            if len(candidatos) == 1 or candidatos[0][0] - candidatos[1][0] >= 0.03:
                self._log("INFO", "Match aproximado: '%s' -> '%s' (%.1f%%)",
                          info_juego.get("nombre"), candidatos[0][1], candidatos[0][0] * 100)
                return candidatos[0][1]

        self._log("DEBUG", "Sin coincidencia segura en manifest: %s", info_juego.get("nombre"))
        return None

    # -- NUEVO: diagnóstico manual de un juego concreto ---------------------

    def diagnostico_juego(self):
        nombre_buscado = sd.askstring(
            "Diagnóstico",
            "¿Qué juego quieres diagnosticar? (escribe el nombre, aproximado vale)")
        if not nombre_buscado or not nombre_buscado.strip():
            return
        self.ejecutar_en_hilo(lambda: self._diagnostico_juego_hilo(nombre_buscado.strip()))

    def _diagnostico_juego_hilo(self, nombre_buscado):
        n_buscado = _norm(nombre_buscado)
        lineas = [f"🔍 Diagnóstico para: '{nombre_buscado}'", ""]

        instalados = detectar_todos_los_juegos() + detectar_juegos_carpetas_raiz(self.carpetas_sin_launcher)
        lineas.append(f"(Total de juegos detectados como instalados en el equipo: {len(instalados)})")
        lineas.append("")
        coincidencias = [j for j in instalados
                         if n_buscado and (n_buscado in _norm(j["nombre"]) or _norm(j["nombre"]) in n_buscado)]

        if not coincidencias:
            lineas.append("❌ Ningún launcher (Steam/Epic/GOG/Battle.net/Ubisoft/EA/Amazon/Xbox) reporta ese juego como instalado.")
            lineas.append("   Posibles causas:")
            lineas.append("   • El registro de ese launcher no se ha podido leer en este PC.")
            lineas.append("   • El nombre que usa el launcher difiere mucho del que has escrito.")
        else:
            for info in coincidencias:
                lineas.append(f"✅ Detectado como INSTALADO: '{info['nombre']}'  (launcher: {info['launcher']}, id: {info.get('id')})")
                lineas.append(f"   installdir: {info.get('installdir') or '(vacío)'}")

                clave_norm_info = _norm(info["nombre"])
                if _es_exclusion_sistema(clave_norm_info):
                    lineas.append("   ⏭️ Excluido a propósito (EXCLUSIONES_SISTEMA): es un runtime/herramienta")
                    lineas.append("      de sistema, no un juego con partida guardada. No aparece en ningún")
                    lineas.append("      bloque del escaneo.")
                    lineas.append("")
                    continue
                if _es_online_sin_save_local(clave_norm_info):
                    lineas.append("   ⏭️ Excluido a propósito (JUEGOS_SIN_SAVE_LOCAL_CONOCIDOS): es un juego")
                    lineas.append("      100% online cuyo progreso vive en el servidor, no en este PC. Aunque")
                    lineas.append("      el manifest pueda resolver una carpeta local, ahí solo hay ajustes,")
                    lineas.append("      no partida real, así que se omite por completo del escaneo.")
                    lineas.append("")
                    continue

                if not self.manifest:
                    lineas.append("   ⚠️ La base de datos de Arlequin-SaveHub todavía no está cargada.")
                    lineas.append("      Espera a que termine de actualizar o pulsa '🔄 Actualizar BD'.")
                    lineas.append("")
                    continue

                clave_manifest = self.buscar_en_manifest(info)
                if not clave_manifest:
                    lineas.append("   ❌ No hay ninguna ficha en la base de datos que cruce con ese nombre.")
                    rutas_intuidas = intuir_rutas_por_editoras_conocidas(info["nombre"], entorno_windows_base())
                    if rutas_intuidas:
                        lineas.append("   🔎 Pero se ha intuido por carpeta de editora conocida (Rockstar Games, etc.):")
                        for r in rutas_intuidas:
                            lineas.append(f"      -> {r}   [✅ EXISTE en disco]")
                    else:
                        lineas.append("      Tampoco coincide con ninguna carpeta de editora conocida (Rockstar Games...).")
                    lineas.append("")
                    continue

                lineas.append(f"   📖 Ficha de la base de datos: '{clave_manifest}'")
                datos_juego = self.manifest.get(clave_manifest) or {}
                entradas = datos_juego.get("save_locations") or []
                entorno = entorno_windows_base()
                if not entradas:
                    lineas.append("   ⚠️ Esa ficha no tiene ninguna ruta en 'save_locations'.")
                    rutas_intuidas = intuir_rutas_por_editoras_conocidas(info["nombre"], entorno)
                    if rutas_intuidas:
                        lineas.append("   🔎 Pero se ha intuido por carpeta de editora conocida (Rockstar Games, etc.):")
                        for r in rutas_intuidas:
                            lineas.append(f"      -> {r}   [✅ EXISTE en disco]")
                    lineas.append("")
                    continue

                steam_path = obtener_steam_path()
                steam_user_ids = obtener_steam_user_ids(steam_path)
                store = LAUNCHER_A_STORE.get(info["launcher"])
                installdir = (info.get("installdir") or "").replace("\\", "/")
                contexto = dict(entorno)
                contexto["base"] = installdir
                if store == "steam":
                    contexto["root"] = steam_path
                    contexto["storeUserIds"] = steam_user_ids
                elif store == "uplay":
                    contexto["root"] = ubisoft_root
                    contexto["storeUserIds"] = ubisoft_user_ids
                else:
                    contexto["root"] = ""
                    contexto["storeUserIds"] = []

                alguna_ruta_existe = False
                rutas_resueltas_total = []
                for entrada in entradas:
                    plantilla, condiciones = _parsear_entrada_save_location(entrada)
                    cumple_cond = condicion_aplica_en_windows(condiciones, store)
                    se_usa = bool(plantilla) and cumple_cond
                    cond_str = ", ".join(
                        f"{k}={'/'.join(sorted(v))}" for k, v in condiciones.items()) or "(ninguna)"
                    lineas.append(f"   • Plantilla: {plantilla}")
                    lineas.append(f"     condiciones=[{cond_str}] | ¿aplica en Windows/tienda?={cumple_cond} "
                                  f"| {'✅ SE USA' if se_usa else '⏭️ descartada (OS/tienda distinta)'}")
                    if se_usa:
                        rutas = resolver_plantilla_ruta(plantilla, contexto)
                        if not rutas:
                            lineas.append("     -> no se pudo resolver a una ruta real (falta algún placeholder)")
                        carpetas_peligrosas_diag = _carpetas_contenedoras_compartidas(contexto)
                        for r in rutas:
                            if _ruta_es_contenedor_compartido(r, carpetas_peligrosas_diag):
                                ruta_especifica = _buscar_carpeta_real_por_comodin(plantilla, contexto)
                                lineas.append(
                                    f"     -> {r}   [⚠️ CARPETA COMPARTIDA POR TODOS LOS JUEGOS: descartada]"
                                )
                                if ruta_especifica:
                                    lineas.append(
                                        f"        🔎 En su lugar se ha encontrado y usado: {ruta_especifica}"
                                    )
                                    rutas_resueltas_total.append(ruta_especifica)
                                    alguna_ruta_existe = True
                                else:
                                    lineas.append(
                                        "        No se encontró ninguna carpeta real más específica en disco."
                                    )
                                continue
                            existe = os.path.isdir(r)
                            alguna_ruta_existe = alguna_ruta_existe or existe
                            rutas_resueltas_total.append(r)
                            lineas.append(f"     -> {r}   [{'✅ EXISTE en disco' if existe else '❌ no existe en disco'}]")

                if not alguna_ruta_existe:
                    rutas_intuidas = intuir_rutas_por_editoras_conocidas(info["nombre"], entorno)
                    if rutas_intuidas:
                        lineas.append("   🔎 Ninguna ruta del manifest existe, pero se ha intuido por carpeta")
                        lineas.append("      de editora conocida (Rockstar Games, etc.):")
                        for r in rutas_intuidas:
                            lineas.append(f"      -> {r}   [✅ EXISTE en disco]")
                    elif rutas_resueltas_total:
                        lineas.append("   📌 El manifest SÍ cruzó y SÍ sabe resolver la ruta, pero esa carpeta")
                        lineas.append("      todavía no existe en disco. Lo más probable es que el juego esté")
                        lineas.append("      instalado pero no se haya ejecutado ni una vez en este Windows")
                        lineas.append("      (muchos juegos no crean su carpeta de guardado hasta el primer")
                        lineas.append("      arranque). Aparecerá en el bloque '⏳ A LA ESPERA DE PRIMER USO'")
                        lineas.append("      del escaneo, y pasará solo a 'encontrados' en cuanto abras/juegues")
                        lineas.append("      el título una vez (no hace falta terminar una partida, basta con")
                        lineas.append("      que el juego cree su carpeta de perfil/guardado al arrancar).")
                    else:
                        lineas.append("   ℹ️ El manifest SÍ cruzó, pero ninguna de sus rutas está marcada como")
                        lineas.append("      'save' para Windows (solo config/registro, o ninguna se pudo")
                        lineas.append("      resolver). La base de datos no tiene datos de guardado registrados para")
                        lineas.append("      este juego — no es un fallo de detección: lo más probable es que")
                        lineas.append("      no tenga partida persistente que respaldar (típico en shooters")
                        lineas.append("      competitivos como Counter-Strike 2, o en juegos sin sistema de")
                        lineas.append("      guardado como tal, p. ej. PEAK). Aparecerá en el bloque")
                        lineas.append("      'ℹ️ SIN DATOS DE GUARDADO CONOCIDOS' del escaneo.")
                lineas.append("")

        texto_final = "\n".join(lineas)
        self.root.after(0, lambda: self._mostrar_diagnostico(texto_final))

    def _mostrar_diagnostico(self, texto):
        ventana = tk.Toplevel(self.root)
        ventana.title("Diagnóstico")
        ventana.geometry("680x520")
        self.centrar_ventana(ventana, 680, 520)
        ventana.configure(bg="#2c3e50")
        caja = tk.Text(ventana, bg="#1b2731", fg="#ecf0f1", font=("Consolas", 9), wrap="word", bd=0)
        caja.pack(fill="both", expand=True, padx=10, pady=10)
        caja.insert("1.0", texto)
        caja.config(state="disabled")

    def localizar_saves_instalados(self):
        """Para cada juego instalado (detectado vía Steam/Epic/GOG/Battle.net/
        Ubisoft/EA/Amazon/Xbox/carpetas sin launcher), busca su ficha en el manifest de
        Ludusavi y resuelve la(s) carpeta(s) real(es) de guardado en este
        equipo.
        Devuelve (encontrados, previstos, sin_datos, sin_localizar,
        conteo_launchers) donde:
          - encontrados: lista de (nombre, launcher, ruta_carpeta) cuya
            carpeta YA existe en disco.
          - previstos: lista de (nombre, launcher, ruta_prevista) para
            juegos cuya ficha del manifest SÍ cruzó y SÍ se pudo resolver
            una ruta real, pero esa carpeta todavía no existe en disco —
            típicamente porque el juego está instalado pero no se ha
            ejecutado ni una vez en esta instalación/perfil de Windows
            (muchos juegos no crean su carpeta de guardado hasta el primer
            arranque). En cuanto lo abras/juegues una vez, el siguiente
            escaneo la moverá sola a "encontrados".
          - sin_datos: lista de (nombre, launcher) para juegos cuya ficha
            del manifest SÍ cruzó (Ludusavi conoce el juego), pero esa
            ficha no tiene ninguna ruta marcada como 'save' para Windows
            (solo config, solo registro, o directamente sin sección
            'files'). No es un fallo de detección: significa que Ludusavi
            no tiene constancia de que ese juego guarde partida en disco
            — típico de shooters competitivos sin progreso persistente
            (p. ej. Counter-Strike 2) o de juegos sin sistema de guardado
            como tal (p. ej. PEAK, que solo guarda ajustes, no partidas).
          - sin_localizar: lista de (nombre, launcher) que están instalados
            pero de los que no se pudo ni cruzar con el manifest ni resolver
            ninguna ruta candidata (nombre no reconocido por Ludusavi, etc.)
        Cuando el mismo juego se detecta por dos vías a la vez (p. ej. ya lo
        tienes en Steam y además en una carpeta sin launcher), se queda con
        la que dé mejor resultado (rutas reales > ruta prevista > cruce sin
        datos > nada), en vez de quedarse ciegamente con la primera que se
        procesó y descartar la otra en silencio.
        """
        entorno = entorno_windows_base()
        # El contexto del equipo se calcula una sola vez por escaneo y se
        # reutiliza para todos los juegos. En particular, no volvemos a leer
        # el Registro de Ubisoft ni a enumerar sus IDs para cada ficha.
        steam_path = obtener_steam_path()
        steam_user_ids = obtener_steam_user_ids(steam_path)
        ubisoft_root = obtener_ubisoft_root()
        ubisoft_user_ids = obtener_ubisoft_user_ids(ubisoft_root)
        contextos_por_store = {
            "steam": dict(entorno, root=steam_path or "", storeUserIds=steam_user_ids),
            "uplay": dict(entorno, root=ubisoft_root or "", storeUserIds=ubisoft_user_ids),
            None: dict(entorno, root="", storeUserIds=[]),
        }
        self._scan_contextos_por_store = contextos_por_store
        self._scan_steam_path = steam_path
        self._scan_ubisoft_root = ubisoft_root

        conteo_launchers = {}
        mejores_por_nombre = {}  # clave_norm -> {"nombre", "launcher", "rutas", "previstas", "sin_datos"}

        def rango(d):
            if d["rutas"]:
                return 3
            if d["previstas"]:
                return 2
            if d.get("sin_datos"):
                return 1
            return 0

        todos_los_detectados = detectar_todos_los_juegos() + detectar_juegos_carpetas_raiz(self.carpetas_sin_launcher)
        nombres_con_launcher_reales = {
            _norm(x.get("nombre"))
            for x in todos_los_detectados
            if x.get("launcher") != "Carpeta" and x.get("nombre")
        }
        for info in todos_los_detectados:
            # Una carpeta suelta puede ser un resto de una edición que ya no
            # está instalada. Si el launcher informa de una edición derivada
            # del mismo título (por ejemplo, "Grand Theft Auto V Enhanced"),
            # no usamos la carpeta vieja "GTA V" para fabricar una segunda
            # instalación ficticia.
            if info.get("launcher") == "Carpeta":
                clave_carpeta = _norm(info.get("nombre"))
                if clave_carpeta:
                    if any(_es_edicion_derivada_del_mismo_juego(clave_carpeta, n)
                           for n in nombres_con_launcher_reales):
                        continue
            
            clave_norm = _norm(info["nombre"])
            if not clave_norm:
                continue
            # Runtimes/herramientas de sistema (Steam Linux Runtime, Proton,
            # Lossless Scaling, 3DMark...): no son juegos con partida
            # guardada, así que ni se cuentan ni aparecen en ningún bloque.
            if _es_exclusion_sistema(clave_norm):
                continue
            if _es_online_sin_save_local(clave_norm):
                continue
            conteo_launchers[info["launcher"]] = conteo_launchers.get(info["launcher"], 0) + 1
            if info["nombre"] in self.ocultos:
                continue

            # Si ya tenemos una entrada para este mismo juego (por otra vía)
            # y esa entrada YA localizó una carpeta de saves real, no hace
            # falta volver a resolver esta: nos quedamos con la que ya funciona.
            existente = mejores_por_nombre.get(clave_norm)
            if existente and existente["rutas"]:
                continue

            store = LAUNCHER_A_STORE.get(info["launcher"])
            clave_manifest = self.buscar_en_manifest(info) if self.manifest else None

            rutas_validas = []
            rutas_previstas = []
            sin_datos_guardado = False
            if clave_manifest:
                datos_juego = self.manifest.get(clave_manifest) or {}
                installdir = (info.get("installdir") or "").replace("\\", "/")
                contexto = dict(contextos_por_store.get(store, contextos_por_store[None]))
                contexto["base"] = installdir

                rutas_resueltas = obtener_rutas_guardado(datos_juego, contexto, store)
                rutas_validas = [r for r in rutas_resueltas if os.path.isdir(r)]
                if not rutas_validas:
                    if rutas_resueltas:
                        # El manifest cruzó y sí sabe resolver la ruta, pero
                        # esa carpeta aún no existe en disco: lo más probable
                        # es que el juego esté instalado pero nunca se haya
                        # ejecutado en este Windows. La guardamos como
                        # "prevista" en vez de descartarla sin más.
                        rutas_previstas = rutas_resueltas
                    else:
                        # El juego SÍ está en el manifest, pero ninguna de
                        # sus rutas 'files' está etiquetada como 'save' para
                        # Windows (o la ficha no tiene 'files' en absoluto).
                        # No es un fallo: la base de datos no tiene datos de
                        # guardado registrados para este título.
                        sin_datos_guardado = True

            # Último recurso: si el manifest no tenía ficha, o la tenía pero
            # no resolvió ninguna ruta real, probamos con las carpetas de
            # editoras conocidas (Rockstar Games, etc. — ver
            # CARPETAS_EDITORAS_CONOCIDAS) por si el juego guarda ahí aunque
            # Ludusavi todavía no lo tenga bien mapeado.
            if not rutas_validas:
                intuidas = intuir_rutas_por_editoras_conocidas(info["nombre"], entorno)
                if intuidas:
                    rutas_validas = intuidas
                    rutas_previstas = []
                    sin_datos_guardado = False

            nuevo = {
                "nombre": info["nombre"], "launcher": info["launcher"],
                "rutas": rutas_validas, "previstas": rutas_previstas,
                "sin_datos": sin_datos_guardado,
                # NUEVO: se conserva la carpeta de instalación para poder,
                # más adelante, comprobar si el .exe del juego sigue vivo
                # antes de un backup/restauración (ver _juego_parece_en_ejecucion).
                "installdir": (info.get("installdir") or "").replace("\\", "/"),
            }
            if existente is None or rango(nuevo) > rango(existente):
                mejores_por_nombre[clave_norm] = nuevo

        encontrados = []
        previstos = []
        sin_datos = []
        sin_localizar = []
        # NUEVO: nombre de juego -> carpeta de instalación conocida (solo
        # para juegos detectados vía launcher/instalador; vacío si no se
        # pudo determinar). Se usa únicamente para la comprobación de
        # "¿sigue en ejecución?", no cambia nada más de la lógica existente.
        installdirs_por_nombre = {}
        for datos in mejores_por_nombre.values():
            installdirs_por_nombre[datos["nombre"]] = datos.get("installdir") or ""
            if datos["rutas"]:
                for ruta in datos["rutas"]:
                    encontrados.append((datos["nombre"], datos["launcher"], ruta))
            elif datos["previstas"]:
                for ruta in datos["previstas"]:
                    previstos.append((datos["nombre"], datos["launcher"], ruta))
            elif datos["sin_datos"]:
                sin_datos.append((datos["nombre"], datos["launcher"]))
            else:
                sin_localizar.append((datos["nombre"], datos["launcher"]))

        return encontrados, previstos, sin_datos, sin_localizar, conteo_launchers, installdirs_por_nombre

    def actualizar_label_launchers(self, conteo_launchers):
        if conteo_launchers:
            resumen = " · ".join(f"{NOMBRE_VISUAL_LAUNCHER.get(l, l)}: {c}"
                                 for l, c in sorted(conteo_launchers.items()))
            color = "#2ecc71"
            self.lbl_launchers_status.config(text=f"instalados → {resumen}", fg=color)
        else:
            color = "#e67e22"
            self.lbl_launchers_status.config(text="ningún launcher con juegos instalados", fg=color)
        # "Partidas N" comparte fila y pieza de estado con "instalados →
        # ...", así que lleva el mismo color que este último en cada caso.
        self.lbl_i.config(fg=color)

    # -- ESCANEO (ahora vía base de datos de Arlequin-SaveHub) --------------

    def scan(self):
        inicio_scan = time.perf_counter()
        self.root.after(0, lambda: self.btn_scan.config(state="disabled", text="⏳ ESCANEANDO..."))
        self.juegos.clear()
        self.juegos_installdir.clear()
        self._exes_cache.clear()
        self.root.after(0, lambda: self.box.delete(0, tk.END))
        self.indexar_backups_en_disco()

        (encontrados, previstos, sin_datos, sin_localizar,
         _conteo_launchers_bruto, installdirs_por_nombre) = self.localizar_saves_instalados()
        # NOTA: el conteo que se muestra en "instalados → ..." ya NO se saca
        # de lo que cada launcher reporta en bruto (_conteo_launchers_bruto):
        # eso incluía juegos ocultos, o instalados de los que luego no se
        # localizó nada, y en cambio se dejaba fuera cualquier juego que solo
        # se encontrara por su ruta de guardado (sin que el launcher lo
        # reportase instalado ahora mismo). Se construye más abajo
        # (conteo_launchers_final) a partir de lo que de verdad se termina
        # mostrando en cada bloque de tienda, así los números siempre
        # cuadran con la lista, y una tienda sin nada detectado ni mostrado
        # simplemente no aparece.
        conteo_launchers_final = {}

        juegos_encontrados_global = set()
        total_items_detectados = 0

        elementos_a_insertar = []

        if self.manuales:
            elementos_a_insertar.append("")
            elementos_a_insertar.append("--- ➕ CARPETAS AÑADIDAS MANUALMENTE ---")
            manuales_filtrados = [
                (nombre_manual, ruta_manual)
                for nombre_manual, ruta_manual in sorted(self.manuales.items())
                if nombre_manual not in self.ocultos
            ]
            # Se calientan en paralelo todos los tamaños de esta sección
            # antes de formatear: así el bucle de abajo (que sí debe ir
            # secuencial, porque construye la lista en orden) encuentra la
            # caché ya rellena y es prácticamente instantáneo.
            self._precalentar_tamanos_en_paralelo(r for _, r in manuales_filtrados)
            for nombre_manual, ruta_manual in manuales_filtrados:
                juegos_encontrados_global.add(nombre_manual)
                ind = "[👍 Copia Ok] " if self.check_bkp(nombre_manual, ruta_manual) else "               "
                tam_str = self.get_folder_size_str(ruta_manual)
                nv = f"{ind}{nombre_manual} ({tam_str})"
                self.juegos[nv] = ruta_manual
                elementos_a_insertar.append(nv)
                total_items_detectados += 1

        # Agrupamos por launcher para mostrar bloques ordenados, como antes.
        # Un mismo juego puede tener varias rutas de save resueltas (p. ej.
        # una en AppData y otra en Documents, o varias carpetas de perfil):
        # se agrupan TODAS bajo el mismo nombre para que aparezcan como UNA
        # sola línea en la lista (el tamaño mostrado es la suma de todas), en
        # vez de una línea repetida por cada carpeta encontrada.
        por_launcher = {}
        for nombre, launcher, ruta in encontrados:
            por_launcher.setdefault(launcher, {}).setdefault(nombre, []).append(ruta)

        iconos_launcher = {"Steam": "📂", "Epic": "🟣", "GOG": "🟪", "Battle.net": "🔷",
                           "Ubisoft": "🔵", "Carpeta": "📁", "Xbox": "🟩",
                           "EA": "🟠", "Amazon": "⬛"}

        # NUEVO (v1.1.0): lo que antes era el botón aparte "🏴‍☠️ Búsqueda
        # Extensa en BD" ahora se hace siempre, como parte del escaneo
        # normal (ya no hace falta un botón ni una espera aparte: con las
        # mejoras de rendimiento del propio escaneo, esto ya va rápido).
        # Se recorre el resto de la base de datos calculando dónde DEBERÍA
        # estar la carpeta de guardado de cada juego usando solo las
        # carpetas estándar de Windows (sin necesitar saber dónde está
        # instalado ni en qué tienda), y se comprueba si esa carpeta existe
        # de verdad. Así se encuentran saves de copias que ningún launcher
        # conocido tiene registradas (descargas sueltas, repacks, portables
        # movidos de otro PC, itch.io...).
        #
        # A petición del usuario, esto se hace ANTES de montar los bloques
        # por tienda (en vez de en un bloque aparte al final), y sus
        # resultados se fusionan dentro del MISMO "por_launcher" que los
        # juegos que sí reportó el launcher correspondiente: al usuario no
        # le interesa (ni se le muestra) CÓMO se encontró cada save, solo
        # que "Epic", "Steam", etc. salgan todos agrupados en un único
        # bloque por tienda. Un juego que el launcher YA reportó como
        # instalado no se vuelve a añadir aquí (el launcher manda).
        #
        # El rastreo por catálogo no conoce de entrada una carpeta de instalación
        # concreta para cada ficha, pero sí puede construir contextos seguros
        # para las rutas que no dependen de <base>. Además de las carpetas
        # estándar de Windows, incluimos Steam y Ubisoft Connect: ambas tienen
        # una raíz conocida en el equipo y pueden aparecer en el manifest como
        # <root>/... . Para Ubisoft también enumeramos sus IDs reales de
        # cuenta bajo savegames/, por lo que rutas como <storeUserId> no quedan
        # bloqueadas durante la búsqueda extensa.
        encontrados_nuevos_ext = {}  # nombre real -> [rutas], sin tienda identificable
        if self.manifest:
            # Reutiliza el mismo contexto de Windows/Steam/Ubisoft ya creado
            # al principio del escaneo. No repetimos lecturas del Registro ni
            # enumeraciones de userdata/savegames.
            # Usamos una copia explícita del contexto base para que esta fase\n            # no dependa de una variable local que pueda quedar fuera de\n            # alcance en una compilación optimizada/antigua.\n            # Reutilizamos el contexto calculado por localizar_saves_instalados().
            # Antes esta fase intentaba usar variables locales de ese método
            # (steam_path, contextos_por_store y ubisoft_root), que no existen
            # dentro de scan() y provocaban NameError en el EXE.
            contextos_por_store_ext = getattr(self, "_scan_contextos_por_store", None)
            steam_path_ext = getattr(self, "_scan_steam_path", None)
            ubisoft_root_ext = getattr(self, "_scan_ubisoft_root", None)
            if not contextos_por_store_ext:
                entorno_ext_base = entorno_windows_base()
                steam_path_ext = obtener_steam_path()
                steam_user_ids_ext = obtener_steam_user_ids(steam_path_ext)
                ubisoft_root_ext = obtener_ubisoft_root()
                ubisoft_user_ids_ext = obtener_ubisoft_user_ids(ubisoft_root_ext)
                contextos_por_store_ext = {
                    "steam": dict(entorno_ext_base, root=steam_path_ext or "", storeUserIds=steam_user_ids_ext),
                    "uplay": dict(entorno_ext_base, root=ubisoft_root_ext or "", storeUserIds=ubisoft_user_ids_ext),
                    None: dict(entorno_ext_base, root="", storeUserIds=[]),
                }

            entorno_extenso = dict(contextos_por_store_ext[None])
            contextos_extensos = [(None, entorno_extenso)]
            if steam_path_ext:
                contexto_steam_ext = dict(contextos_por_store_ext["steam"])
                contexto_steam_ext["base"] = ""
                contextos_extensos.append(("steam", contexto_steam_ext))
            if ubisoft_root_ext:
                contexto_ubisoft_ext = dict(contextos_por_store_ext["uplay"])
                contexto_ubisoft_ext["base"] = ""
                contextos_extensos.append(("uplay", contexto_ubisoft_ext))

            nombres_ya_con_launcher = {
                _norm(n) for juegos_launcher in por_launcher.values() for n in juegos_launcher
            }
            ya_detectados_norm = set(nombres_ya_con_launcher)
            ya_detectados_norm |= {_norm(n) for n in self.ocultos}

            def _resolver_extenso(item):
                nombre_real, datos_juego = item
                nombre_real_norm = _norm(nombre_real)
                if nombre_real_norm in ya_detectados_norm:
                    return None
                if any(_es_edicion_derivada_del_mismo_juego(nombre_real_norm, n)
                       for n in nombres_ya_con_launcher):
                    return None
                existentes = []
                vistos_ext = set()
                for store_contexto, contexto_extenso in contextos_extensos:
                    try:
                        rutas_con_store = obtener_rutas_guardado(
                            datos_juego, contexto_extenso, store_contexto,
                            con_store_origen=True
                        )
                    except Exception:
                        continue
                    for ruta, store_origen in rutas_con_store:
                        if os.path.isdir(ruta) and ruta not in vistos_ext:
                            vistos_ext.add(ruta)
                            existentes.append((ruta, store_origen or store_contexto))
                if not existentes:
                    return None
                rutas_existentes = [r for r, _ in existentes]
                stores_encontrados = {s for _, s in existentes if s}
                launcher_inferido = None
                if len(stores_encontrados) == 1:
                    launcher_inferido = STORE_A_LAUNCHER.get(next(iter(stores_encontrados)))
                return nombre_real, rutas_existentes, launcher_inferido

            # El rastreo por catálogo es independiente por juego. Se reparte
            # entre varios hilos porque la mayor parte del trabajo es E/S:
            # exists/isdir/glob sobre el disco. executor.map conserva el orden
            # de entrada, por lo que la salida sigue siendo determinista.
            items_manifest = list(self.manifest.items())
            try:
                with ThreadPoolExecutor(max_workers=min(8, max(1, len(items_manifest)))) as executor:
                    resultados_ext = executor.map(_resolver_extenso, items_manifest)
                    for resultado in resultados_ext:
                        if not resultado:
                            continue
                        nombre_real, rutas_existentes, launcher_inferido = resultado
                        if launcher_inferido:
                            por_launcher.setdefault(launcher_inferido, {})[nombre_real] = rutas_existentes
                        else:
                            encontrados_nuevos_ext[nombre_real] = rutas_existentes
            except Exception:
                # Respaldo secuencial si el pool falla por alguna razón.
                for item in items_manifest:
                    resultado = _resolver_extenso(item)
                    if not resultado:
                        continue
                    nombre_real, rutas_existentes, launcher_inferido = resultado
                    if launcher_inferido:
                        por_launcher.setdefault(launcher_inferido, {})[nombre_real] = rutas_existentes
                    else:
                        encontrados_nuevos_ext[nombre_real] = rutas_existentes

        # Primera pasada: solo decidir qué juegos entran en cada bloque de
        # launcher (sin calcular tamaños todavía), para poder lanzar el
        # cálculo de TODAS las carpetas de golpe, en paralelo.
        bloques_launcher = []
        rutas_a_precalentar = []
        for launcher in sorted(por_launcher.keys()):
            nombres_launcher = sorted(por_launcher[launcher].keys(), key=str.lower)
            elementos_carpeta = []
            for nombre in nombres_launcher:
                if nombre in self.ocultos or nombre in juegos_encontrados_global:
                    continue
                elementos_carpeta.append((nombre, por_launcher[launcher][nombre]))
            if not elementos_carpeta:
                continue
            for _, rutas in elementos_carpeta:
                rutas_a_precalentar.extend(rutas)
            juegos_encontrados_global.update(nombre for nombre, _ in elementos_carpeta)
            bloques_launcher.append((launcher, elementos_carpeta))
            conteo_launchers_final[launcher] = conteo_launchers_final.get(launcher, 0) + len(elementos_carpeta)

        self._precalentar_tamanos_en_paralelo(rutas_a_precalentar)

        # Segunda pasada: ahora sí, en el mismo orden de siempre, se formatea
        # cada línea (get_rutas_size_str ya encuentra la caché caliente).
        for launcher, elementos_carpeta in bloques_launcher:
            icono = iconos_launcher.get(launcher, "🎮")
            nombre_visual_launcher = NOMBRE_VISUAL_LAUNCHER.get(launcher, launcher)
            elementos_a_insertar.append("")
            elementos_a_insertar.append(f"--- {icono} {nombre_visual_launcher.upper()} ---")
            for nombre, rutas in elementos_carpeta:
                ind = "[👍 Copia Ok] " if self.check_bkp(nombre, rutas) else "               "
                tam_str = self.get_rutas_size_str(rutas)
                # Ya está agrupado bajo la cabecera de su tienda (arriba),
                # así que aquí no hace falta repetir de qué tienda es.
                nv = f"{ind}{nombre} ({tam_str})"
                # Si hay más de una carpeta real para este juego, se guardan
                # todas: al respaldar/restaurar se procesan las dos, aunque
                # en la lista cuenten y se vean como un único elemento.
                self.juegos[nv] = rutas[0] if len(rutas) == 1 else rutas
                # NUEVO: se recuerda la carpeta de instalación de este juego
                # (si se conoce) para poder avisar si sigue abierto. Los
                # añadidos por ruta de guardado (sin confirmar instalación)
                # simplemente no tendrán installdir conocido.
                self.juegos_installdir[nv] = installdirs_por_nombre.get(nombre, "")
                elementos_a_insertar.append(nv)
                total_items_detectados += 1

        if encontrados_nuevos_ext:
            elementos_a_insertar.append("")
            elementos_a_insertar.append(
                "═══ 🏴‍☠️ SIN LAUNCHER CONOCIDO (encontrado por su ruta de guardado) ═══")
            for nombre_real in sorted(encontrados_nuevos_ext.keys(), key=str.lower):
                if nombre_real in self.ocultos or nombre_real in juegos_encontrados_global:
                    continue
                rutas = encontrados_nuevos_ext[nombre_real]
                ind = "[👍 Copia Ok] " if self.check_bkp(nombre_real, rutas) else "               "
                tam_str = self.get_rutas_size_str(rutas)
                nv = f"{ind}{nombre_real} ({tam_str} · sin launcher)"
                self.juegos[nv] = rutas[0] if len(rutas) == 1 else rutas
                # No se conoce la instalación de estos juegos, así
                # que no se puede comprobar si el .exe está abierto.
                self.juegos_installdir[nv] = ""
                juegos_encontrados_global.add(nombre_real)
                elementos_a_insertar.append(nv)
                total_items_detectados += 1

        # instalados cuya ficha del manifest SÍ cruzó (Ludusavi conoce el
        # juego), pero esa ficha no tiene ninguna ruta marcada como 'save'
        # para Windows: no es un fallo de detección, es que Ludusavi no
        # tiene constancia de que ese juego guarde partida en disco (típico
        # de shooters competitivos como Counter-Strike 2, o de juegos sin
        # sistema de guardado como tal, p. ej. PEAK). Se muestran aparte
        # para no confundirlos con los realmente "no reconocidos".
        sin_datos_filtrado = [
            (nombre, launcher) for nombre, launcher in sin_datos
            if nombre not in self.ocultos and nombre not in juegos_encontrados_global
        ]
        if sin_datos_filtrado:
            por_launcher_sd = {}
            for nombre_real, launcher in sin_datos_filtrado:
                por_launcher_sd.setdefault(launcher, []).append(nombre_real)

            elementos_a_insertar.append("")
            elementos_a_insertar.append("═══ ℹ️ SIN DATOS DE GUARDADO CONOCIDOS (la base de datos no registra save para estos) ═══")

            for launcher in sorted(por_launcher_sd.keys()):
                icono = iconos_launcher.get(launcher, "🎮")
                nombre_visual_launcher = NOMBRE_VISUAL_LAUNCHER.get(launcher, launcher)
                elementos_a_insertar.append(f"--- {icono} {nombre_visual_launcher.upper()} (sin datos de guardado) ---")
                conteo_launchers_final[launcher] = conteo_launchers_final.get(launcher, 0) + len(por_launcher_sd[launcher])
                for nombre_real in sorted(por_launcher_sd[launcher], key=str.lower):
                    juegos_encontrados_global.add(nombre_real)
                    nv = f"               {nombre_real} (instalado · sin save conocido)"
                    self.juegos[nv] = ""  # informativo: no hay ruta de save que respaldar
                    elementos_a_insertar.append(nv)
                    total_items_detectados += 1

        # A petición del usuario: los juegos instalados de los que NO se pudo
        # localizar ninguna carpeta de saves ("sin_localizar") ya NO se
        # muestran en la lista. Siguen detectándose por debajo (por eso
        # localizar_saves_instalados() los sigue devolviendo, y siguen
        # contando en el resumen de launchers de arriba), pero se omiten
        # aquí en vez de mostrarse bajo "🎮 INSTALADOS SIN LOCALIZAR". Si
        # quieres respaldar uno de esos juegos igualmente, usa
        # "➕ Añadir Manual" para indicar su carpeta a mano.
        _ = sin_localizar  # variable ya no se usa para mostrar nada en pantalla

        lista_solo_backup = []
        encontrados_norm = {str(x).lower() for x in juegos_encontrados_global}
        ocultos_norm = {str(x).lower() for x in self.ocultos}
        for rel_bkp in sorted(self.backups_existentes):
            partes_bkp = [p for p in str(rel_bkp).replace("\\", "/").split("/") if p]
            if not partes_bkp:
                continue
            nombre_bkp = partes_bkp[-1]
            if nombre_bkp.lower() in encontrados_norm or nombre_bkp.lower() in ocultos_norm:
                continue
            ruta_bkp = os.path.join(self.dest, *partes_bkp).replace("\\", "/")
            lista_solo_backup.append((rel_bkp, nombre_bkp, ruta_bkp))

        if lista_solo_backup:
            elementos_a_insertar.append("")
            elementos_a_insertar.append("--- 💾 SOLO EN CARPETA BACKUP (DESINSTALADOS) ---")
            self._precalentar_tamanos_en_paralelo(r_c for _, _, r_c in lista_solo_backup)
            for rel_bkp, nombre_bkp, r_c in lista_solo_backup:
                tam_str = self.get_folder_size_str(r_c)
                # Mostramos el grupo para que quede claro dónde está ordenado.
                nv = f"[👍 Copia Ok] [Solo en Backup] {rel_bkp} ({tam_str})"
                # Para una restauración de un juego desinstalado, el usuario
                # deberá volver a añadir manualmente su carpeta de save; aquí
                # conservamos una referencia útil al backup, sin asumir que
                # Documents sea su ruta original.
                self.juegos[nv] = r_c
                elementos_a_insertar.append(nv)
                total_items_detectados += 1

        # instalados cuya ficha del manifest SÍ cruzó y SÍ resolvió una ruta,
        # pero esa carpeta todavía no existe en disco (típicamente: el juego
        # está instalado pero nunca se ha ejecutado en este Windows, así que
        # aún no ha creado su carpeta de guardado). Se muestran aparte, con
        # la ruta exacta donde aparecerá en cuanto lo abras/juegues una vez.
        # A petición del usuario, este bloque va SIEMPRE el último de toda
        # la lista (después de todo lo demás, backups incluidos): son
        # juegos sin ningún dato real que respaldar todavía, así que no
        # deben mezclarse ni competir en la vista con los que sí tienen
        # save real.
        previstos_filtrado = [
            (nombre, launcher, ruta) for nombre, launcher, ruta in previstos
            if nombre not in self.ocultos and nombre not in juegos_encontrados_global
        ]
        if previstos_filtrado:
            # Igual que en "encontrados": si el mismo juego tiene varias
            # rutas previstas, se fusionan y solo se muestra/cuenta una vez.
            por_launcher_prev = {}
            for nombre_real, launcher, ruta in previstos_filtrado:
                por_launcher_prev.setdefault(launcher, {}).setdefault(nombre_real, []).append(ruta)

            elementos_a_insertar.append("")
            elementos_a_insertar.append("════ ⏳ INSTALADOS - A LA ESPERA DE PRIMER USO ════")

            for launcher in sorted(por_launcher_prev.keys()):
                icono = iconos_launcher.get(launcher, "🎮")
                nombre_visual_launcher = NOMBRE_VISUAL_LAUNCHER.get(launcher, launcher)
                elementos_a_insertar.append(f"--- {icono} {nombre_visual_launcher.upper()} (ruta prevista) ---")
                conteo_launchers_final[launcher] = conteo_launchers_final.get(launcher, 0) + len(por_launcher_prev[launcher])
                for nombre_real in sorted(por_launcher_prev[launcher].keys(), key=str.lower):
                    rutas = por_launcher_prev[launcher][nombre_real]
                    juegos_encontrados_global.add(nombre_real)
                    if len(rutas) == 1:
                        nv = f"               {nombre_real} → se creará en: {rutas[0]}"
                    else:
                        nv = f"               {nombre_real} → se creará en: {rutas[0]} (+{len(rutas) - 1} más)"
                    self.juegos[nv] = ""  # carpeta aún no existe: solo informativo, no respaldable todavía
                    elementos_a_insertar.append(nv)
                    total_items_detectados += 1

        def actualizar_interfaz_grafica():
            for item in elementos_a_insertar:
                self.box.insert(tk.END, item)
            # "instalados → ..." ahora se calcula (conteo_launchers_final)
            # a partir de lo que de verdad se ha mostrado en cada bloque de
            # tienda, así que se actualiza aquí, junto con el resto de la
            # interfaz, en vez de al principio del escaneo con el conteo en
            # bruto de cada launcher.
            self.actualizar_label_launchers(conteo_launchers_final)
            self.lbl_i.config(text=f"Partidas {total_items_detectados}")
            self.btn_scan.config(state="normal", text="🔍 ESCANEAR SAVES")

        duracion_scan = time.perf_counter() - inicio_scan
        self._log(
            "INFO",
            "Escaneo completado en %.2f s: %d elementos mostrados.",
            duracion_scan, total_items_detectados,
        )
        self.root.after(0, actualizar_interfaz_grafica)

    def verificar_backups(self):
        """Comprueba que las copias principales existen y tienen contenido."""
        self.indexar_backups_en_disco()
        total = len(self.backups_existentes)
        validos = 0
        problemas = []
        for rel_bkp in sorted(self.backups_existentes):
            partes_bkp = [p for p in str(rel_bkp).replace("\\", "/").split("/") if p]
            ruta = os.path.join(self.dest, *partes_bkp)
            try:
                if not os.path.isdir(ruta):
                    problemas.append(f"{rel_bkp}: no es una carpeta")
                    continue
                archivos = 0
                for _, _, nombres in os.walk(ruta):
                    archivos += len(nombres)
                if archivos > 0:
                    validos += 1
                else:
                    problemas.append(f"{rel_bkp}: carpeta vacía")
            except Exception as exc:
                problemas.append(f"{rel_bkp}: {exc}")
        self._log("INFO", "Verificación de backups: %d/%d válidos", validos, total)

        def mostrar():
            if problemas:
                detalle = "\n".join(f"• {x}" for x in problemas[:15])
                extra = "" if len(problemas) <= 15 else f"\n… y {len(problemas)-15} problemas más."
                mb.showwarning(
                    "Verificación de backups",
                    f"Backups válidos: {validos}/{total}\n"
                    f"Problemas: {len(problemas)}\n\n{detalle}{extra}"
                )
            else:
                mb.showinfo(
                    "Verificación de backups",
                    f"Todos los backups principales parecen válidos.\n\n"
                    f"Carpetas verificadas: {total}"
                )
        self.root.after(0, mostrar)

    def mostrar_detalles_seleccionado(self):
        seleccion = self.get_sel_list()
        if len(seleccion) != 1:
            mb.showwarning("Detalles", "Selecciona exactamente un juego.")
            return
        fila = seleccion[0]
        origen = self.juegos.get(fila)
        nombre = self.limpiar_nombre_juego(fila)
        if isinstance(origen, (list, tuple)):
            rutas = list(origen)
        elif origen:
            rutas = [origen]
        else:
            rutas = []

        partes = [f"Juego: {nombre}", ""]
        if rutas:
            for n, ruta in enumerate(rutas, 1):
                tam = self.get_folder_size_str(ruta)
                try:
                    mod = self._formatear_fecha_es(os.path.getmtime(ruta))
                except Exception:
                    mod = "No disponible"
                partes.append(f"Ruta {n}: {ruta}")
                partes.append(f"  Tamaño: {tam}")
                partes.append(f"  Última modificación: {mod}")
                dst, _ = self.r_path(ruta, nombre)
                partes.append(f"  Backup: {dst}")
                partes.append(f"  Backup existe: {'Sí' if os.path.exists(dst) else 'No'}")
                partes.append("")
        else:
            partes.append("No hay una ruta de save local respaldable.")
        partes.append(f"Log: {LOG_FILE}")

        mb.showinfo("Detalles del juego", "\n".join(partes))

    def __init__(self, root):
        self.root = root
        # Sincronización: solo una tarea pesada puede modificar el estado
        # interno o las copias a la vez.
        self._worker_lock = threading.Lock()
        self._size_cache = {}
        self._size_cache_lock = threading.Lock()
        self._logger = logging.getLogger("ArlequinSaveManager")
        if not self._logger.handlers:
            try:
                os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
                handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
                handler.setFormatter(logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(message)s"
                ))
                self._logger.addHandler(handler)
                self._logger.setLevel(logging.INFO)
                self._logger.propagate = False
            except Exception:
                pass
        self._log("INFO", "Aplicación iniciada.")
        self.aplicar_icono_ventana(root)
        root.title("Arlequin SaveHub")
        root.geometry("820x900")
        root.minsize(820, 680)
        root.configure(bg="#2c3e50")
        self.centrar_ventana(root, 820, 900)
        self.dest = BKP
        self.juegos = {}
        # NUEVO: nombre de juego (tal como aparece en la lista) -> carpeta de
        # instalación conocida (vacío si no se pudo determinar). Usado solo
        # para avisar si el juego sigue en ejecución antes de backup/restore.
        self.juegos_installdir = {}
        # NUEVO: caché de .exe candidatos ya detectados por carpeta de
        # instalación, para no volver a recorrer el disco en cada backup.
        self._exes_cache = {}
        # NUEVO: máximo configurable de copias históricas por juego (0 =
        # sin límite, comportamiento de siempre). Ver rotar_a_old().
        self.max_backups_historicos = self._cargar_max_backups()
        self.backups_existentes = set()
        self.ocultos = self.load_ocultos(M_O)
        self.manuales = self.load_manuales(M_M)
        # NUEVO: carpetas raíz de juegos sin launcher (DRM-free / portables)
        self.carpetas_sin_launcher = self.load_carpetas(M_C)
        # NUEVO: base de datos de rutas de saves (Arlequin-SaveHub)
        self.manifest = {}
        self.manifest_total_juegos = 0
        self.manifest_por_nombre = {}
        self.manifest_por_steam_id = {}
        self.manifest_por_gog_id = {}
        # NUEVO (v1.1.0): reordenado para que coincida con la maqueta:
        #   Fila 1: los botones (Diagnóstico / Actualizar BD), con el
        #           título "Arlequin SaveHub" centrado EN ESA MISMA fila,
        #           justo entre los dos botones (cada palabra de un color
        #           distinto). Se usa place(relx=0.5) en vez de dejar que
        #           el hueco lo deje el propio pack(), porque así queda
        #           centrado respecto al ANCHO TOTAL de la fila, y no solo
        #           respecto al hueco libre entre los dos botones (que
        #           puede no ser simétrico si un botón es más ancho que
        #           el otro). Altura fija (pack_propagate(False)) para que
        #           el título, con una tipografía más grande que la de los
        #           botones, no se salga de la fila ni se monte con la de
        #           abajo.
        #   Fila 2: "N juegos en BD" y "Estás al día"/"Actualizado" (ahora
        #           intercambiados de lado: el estado de actualización va
        #           primero, a la izquierda).
        f_botones_bd = tk.Frame(root, bg="#2c3e50", height=40)
        f_botones_bd.pack_propagate(False)
        f_botones_bd.pack(pady=(10, 2), fill="x", padx=20)
        tk.Button(f_botones_bd, text="🩺 Diagnóstico", command=self.diagnostico_juego,
                  bg="#e67e22", fg="white", activebackground="#d35400", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3).pack(side="left")
        tk.Button(f_botones_bd, text="🔄 Actualizar BD", command=lambda: self.ejecutar_en_hilo(
                      lambda: self.actualizar_bd_y_escanear(forzar=True)),
                  bg="#1abc9c", fg="white", activebackground="#16a085", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3).pack(side="right")
        f_titulo = tk.Frame(f_botones_bd, bg="#2c3e50")
        f_titulo.place(relx=0.5, rely=0.5, anchor="center")
        # "SaveHub" va pegado, como una sola palabra: sin espacio en el
        # texto entre los dos Label, sin padx entre ellos al empaquetarlos,
        # y sin borde/resalte propio (que si no, aunque el texto no tenga
        # espacio, cada Label deja un pequeño margen visual alrededor).
        tk.Label(f_titulo, text="Arlequin ", font=("Arial", 16, "bold"),
                 fg="#e74c3c", bg="#2c3e50", bd=0, highlightthickness=0,
                 padx=0).pack(side="left")
        tk.Label(f_titulo, text="Save", font=("Arial", 16, "bold"),
                 fg="#f1c40f", bg="#2c3e50", bd=0, highlightthickness=0,
                 padx=0).pack(side="left", padx=0)
        tk.Label(f_titulo, text="Hub", font=("Arial", 16, "bold"),
                 fg="#1abc9c", bg="#2c3e50", bd=0, highlightthickness=0,
                 padx=0).pack(side="left", padx=0)
        f_db = tk.Frame(root, bg="#2c3e50")
        f_db.pack(pady=(0, 2), fill="x", padx=20)
        # NUEVO: orden intercambiado respecto a antes ("Estás al día" /
        # ahora "Actualizado" va primero, a la izquierda; "N juegos" pasa a
        # la derecha), y sin el emoji de check en ninguno de los dos.
        self.lbl_update_status = tk.Label(f_db, text="🔍 Comprobando actualizaciones...",
                                          fg="#95a5a6", bg="#2c3e50", font=("Arial", 11, "bold"))
        self.lbl_update_status.pack(side="left")
        self.lbl_db_status = tk.Label(f_db, text="Ventana lista. Preparando actualización de la base de datos...",
                                      fg="#bdc3c7", bg="#2c3e50", font=("Arial", 11, "bold"))
        self.lbl_db_status.pack(side="right")
        # NUEVO (v1.1.0): "instalados → resumen" y "Partidas N" ya NO
        # comparten fila: a petición del usuario, "instalados" va arriba
        # (a la altura que ocupaba antes esta fila conjunta), alineado del
        # todo a la izquierda, y "Partidas N" justo debajo, también a la
        # izquierda. El botón "📁 Juegos sin Launcher" sigue anclado a la
        # derecha de este mismo bloque.
        f_launchers = tk.Frame(root, bg="#2c3e50")
        f_launchers.pack(pady=(0, 2), fill="x", padx=20)
        f_launchers_texto = tk.Frame(f_launchers, bg="#2c3e50")
        f_launchers_texto.pack(side="left", anchor="w")
        self.lbl_launchers_status = tk.Label(f_launchers_texto, text="detectando launchers instalados...",
                                             fg="#bdc3c7", bg="#2c3e50", font=("Arial", 11, "bold"),
                                             anchor="w", justify="left")
        self.lbl_launchers_status.pack(side="top", anchor="w")
        self.lbl_i = tk.Label(f_launchers_texto, text="Partidas 0", font=("Arial", 11, "bold"),
                              fg="white", bg="#2c3e50", anchor="w", justify="left")
        self.lbl_i.pack(side="top", anchor="w")
        tk.Button(f_launchers, text="📁 Juegos sin Launcher", command=self.gestionar_carpetas_sin_launcher,
                  bg="#9b59b6", fg="white", activebackground="#8e44ad", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3).pack(side="right")
        f_r = tk.Frame(root, bg="#34495e", bd=1, relief="solid")
        f_r.pack(pady=5, fill="x", padx=20, ipady=5)
        self.lbl_r = tk.Label(f_r, text=f" Guardando en: {self.dest}", fg="#bdc3c7", bg="#34495e",
                              font=("Arial", 9), wraplength=420, justify="left")
        self.lbl_r.pack(side="left", fill="x", expand=True, padx=5)
        f_r_btns = tk.Frame(f_r, bg="#34495e")
        f_r_btns.pack(side="right", padx=5)
        tk.Button(f_r_btns, text="Abrir", command=self.abrir_carpeta_backups, bg="#3498db",
                  fg="white", font=("Arial", 8, "bold"), bd=0, cursor="hand2", padx=8, pady=2).pack(side="left", padx=(0, 4))
        tk.Button(f_r_btns, text="Cambiar", command=self.cambiar_carpeta, bg="#1abc9c",
                  fg="white", font=("Arial", 8, "bold"), bd=0, cursor="hand2", padx=8, pady=2).pack(side="left")
        # NUEVO (v1.1.0): esta fila ahora es solo de botones (el contador de
        # partidas se fue a la fila de arriba). Tres zonas independientes:
        #   - "🔍 ESCANEAR SAVES" fijo pegado al borde izquierdo.
        #   - "Añadir Manual"/"Quitar Manual" CENTRADOS de verdad en el
        #     espacio que quede libre entre los dos extremos (con place() y
        #     relx=0.5 dentro de un contenedor que se expande, en vez de un
        #     simple pack a la izquierda, que los dejaría pegados al lado
        #     de "ESCANEAR SAVES" en vez de centrados).
        #   - "Detalles"/"Verificar" anclados al borde derecho: al ir en un
        #     frame empaquetado con side="right" dentro de f_s (que tiene
        #     fill="x"), se mueven solos con el borde de la ventana si se
        #     redimensiona hacia la derecha, en vez de quedarse fijos donde
        #     estaban.
        f_s = tk.Frame(root, bg="#2c3e50")
        f_s.pack(pady=8, fill="x", padx=20)
        self.btn_scan = tk.Button(f_s, text="🔍 ESCANEAR SAVES",
                                  command=lambda: self.ejecutar_en_hilo(self.scan),
                                  bg="#3498db", fg="white", font=("Arial", 9, "bold"), bd=0,
                                  padx=8, pady=4, cursor="hand2")
        self.btn_scan.pack(side="left", padx=2)

        f_s_derecha = tk.Frame(f_s, bg="#2c3e50")
        f_s_derecha.pack(side="right")
        tk.Button(f_s_derecha, text="ℹ️ Detalles", command=self.mostrar_detalles_seleccionado,
                  bg="#16a085", fg="white", font=("Arial", 9, "bold"), bd=0,
                  padx=8, pady=4, cursor="hand2").pack(side="left", padx=2)
        tk.Button(f_s_derecha, text="🧪 Verificar", command=lambda: self.ejecutar_en_hilo(
                      self.verificar_backups),
                  bg="#8e44ad", fg="white", font=("Arial", 9, "bold"), bd=0,
                  padx=8, pady=4, cursor="hand2").pack(side="left", padx=2)

        # Antes este botón se centraba dentro del hueco que quedaba entre
        # "ESCANEAR SAVES" (izquierda) y "Detalles"/"Verificar" (derecha);
        # como "ESCANEAR SAVES" es más ancho que ese otro grupo, ese hueco
        # no es simétrico respecto al centro real de la ventana, y el
        # resultado quedaba visiblemente desplazado a la izquierda respecto
        # a los botones de más abajo. Ahora se centra con place(relx=0.5)
        # directamente sobre f_s (la fila entera), así que queda centrado
        # de verdad respecto al ancho TOTAL de la fila -y por tanto
        # alineado con los botones de las filas de debajo-, sin importar
        # cuánto ocupen los botones de los lados.
        f_s_centro = tk.Frame(f_s, bg="#2c3e50")
        f_s_centro.place(relx=0.5, rely=0.5, anchor="center")
        tk.Button(f_s_centro, text="➕ Añadir Manual", command=self.añadir_carpeta_manual, bg="#9b59b6",
                  fg="white", font=("Arial", 9, "bold"), bd=0, padx=8, pady=4, cursor="hand2").pack(side="left", padx=2)
        tk.Button(f_s_centro, text="➖ Quitar Manual", command=self.quitar_carpeta_manual, bg="#e67e22",
                  fg="white", font=("Arial", 9, "bold"), bd=0, padx=8, pady=4, cursor="hand2").pack(side="left", padx=2)
        self.box = tk.Listbox(root, font=("Arial", 11), bg="#34495e", fg="white",
                              selectbackground="#1abc9c", bd=0, highlightthickness=0,
                              activestyle="none", selectmode="multiple")
        self.box.pack(pady=5, padx=20, fill="both", expand=True)
        f_v = tk.Frame(root, bg="#2c3e50")
        f_v.pack(pady=4, fill="x", padx=20)
        f_v.columnconfigure(0, weight=1, uniform="grupo_ocultos")
        f_v.columnconfigure(1, weight=1, uniform="grupo_ocultos")
        btn_ocultar = tk.Button(f_v, text="Ocultar seleccionado(s)", font=("Arial", 9, "bold"),
                                bg="#e67e22", fg="white", bd=0, relief="flat", pady=6, cursor="hand2",
                                activebackground="#d35400", activeforeground="white",
                                command=self.hide)
        btn_ocultar.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        btn_gestionar_ocultos = tk.Button(f_v, text="Gestionar Ocultos", font=("Arial", 9, "bold"),
                                          bg="#3498db", fg="white", bd=0, relief="flat", pady=6, cursor="hand2",
                                          activebackground="#2980b9", activeforeground="white",
                                          command=self.mostrar_submenu_ocultos)
        btn_gestionar_ocultos.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        f_m = tk.Frame(root, bg="#2c3e50")
        f_m.pack(pady=4, fill="x", padx=20)
        f_m.columnconfigure(0, weight=1, uniform="grupo_botones")
        f_m.columnconfigure(1, weight=1, uniform="grupo_botones")
        btn_sel = tk.Button(f_m, text="Seleccionar Todos", font=("Arial", 10, "bold"), bg="#9b59b6",
                            fg="white", bd=0, relief="flat", pady=8, cursor="hand2",
                            command=self.seleccionar_todo_el_listado)
        btn_sel.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        btn_desel = tk.Button(f_m, text="Deseleccionar Todos", font=("Arial", 10, "bold"), bg="#95a5a6",
                              fg="black", bd=0, relief="flat", pady=8, cursor="hand2",
                              command=self.deseleccionar_todo_el_listado)
        btn_desel.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        f_b = tk.Frame(root, bg="#2c3e50")
        f_b.pack(pady=4, fill="x", padx=20)
        f_b.columnconfigure(0, weight=1, uniform="grupo_botones")
        f_b.columnconfigure(1, weight=1, uniform="grupo_botones")
        btn_resp = tk.Button(f_b, text="Respaldar Save(s)", font=("Arial", 11, "bold"), bg="#2ecc71",
                             fg="white", bd=0, relief="flat", pady=8, cursor="hand2",
                             command=lambda: self.ejecutar_en_hilo(lambda: self.op(1)))
        btn_resp.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        btn_rest = tk.Button(f_b, text="Restaurar Save(s)", font=("Arial", 11, "bold"), bg="#e74c3c",
                             fg="white", bd=0, relief="flat", pady=8, cursor="hand2",
                             command=lambda: self.ejecutar_en_hilo(lambda: self.op(2)))
        btn_rest.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        f_inf = tk.Frame(root, bg="#2c3e50")
        f_inf.pack(pady=15, fill="x", padx=20)
        tk.Button(f_inf, text="🎁 Donar", command=self.abrir_link_donar, bg="#e67e22", fg="white",
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2").pack(side="left")
        tk.Button(f_inf, text="➡️ X (Twitter)", command=self.abrir_link_contacto, bg="#d35400", fg="white",
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2").pack(side="left", padx=10)
        # NUEVO: desplegable para configurar el máximo de copias históricas
        # que se conservan por juego (rotar_a_old ya no crece sin parar).
        tk.Label(f_inf, text="Máx. copias/juego:", font=("Arial", 8, "bold"),
                 fg="#bdc3c7", bg="#2c3e50").pack(side="left", padx=(0, 4))
        opciones_max_backups = ["Sin límite", "1", "2", "3", "5", "10", "15", "20"]
        valor_actual = "Sin límite" if self.max_backups_historicos == 0 else str(self.max_backups_historicos)
        if valor_actual not in opciones_max_backups:
            opciones_max_backups.append(valor_actual)
        self.var_max_backups = tk.StringVar(value=valor_actual)
        menu_max_backups = tk.OptionMenu(f_inf, self.var_max_backups, *opciones_max_backups,
                                         command=self._cambiar_max_backups)
        menu_max_backups.config(bg="#34495e", fg="white", font=("Arial", 8, "bold"),
                                bd=0, highlightthickness=0, cursor="hand2",
                                activebackground="#1abc9c", activeforeground="white")
        menu_max_backups["menu"].config(bg="#34495e", fg="white")
        menu_max_backups.pack(side="left", padx=(0, 10))
        tk.Button(f_inf, text="🚪 Salir", command=root.quit, bg="#7f8c8d", fg="white",
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2").pack(side="right")
        tk.Label(f_inf, text="by loco965", font=("Arial", 11, "bold", "italic"),
                 fg="#bdc3c7", bg="#2c3e50").pack(side="right", padx=(0, 8))
        # IMPORTANTE: la ventana ya está construida y a punto de mostrarse
        # (root.mainloop() se llama justo después, fuera de esta clase).
        # Solo AHORA, en un hilo aparte para no bloquear la interfaz, se
        # descarga/actualiza la base de datos de Arlequin-SaveHub y se escanea.
        def arranque():
            self.indexar_backups_en_disco()
            self.actualizar_bd_y_escanear(forzar=False)
        self.ejecutar_en_hilo(arranque)
        # Comprobación de actualizaciones: en su propio hilo (no comparte el
        # candado de ejecutar_en_hilo) para que no espere a que termine el
        # escaneo inicial ni lo bloquee.
        threading.Thread(target=self.comprobar_actualizaciones_al_inicio, daemon=True).start()

    def _set_estado_actualizacion(self, texto, color="#95a5a6"):
        self.root.after(0, lambda: self.lbl_update_status.config(text=texto, fg=color))

    def comprobar_actualizaciones_al_inicio(self):
        """Se ejecuta en segundo plano al abrir el programa. Si hay una
        versión más nueva publicada, pregunta al usuario (en el hilo
        principal de Tkinter) si quiere actualizar."""
        self._set_estado_actualizacion("🔍 Comprobando actualizaciones...", "#95a5a6")
        try:
            datos = comprobar_actualizacion_disponible()
        except Exception as e:
            self._log("ERROR", "Error comprobando actualizaciones: %s", e, exc_info=True)
            self._set_estado_actualizacion(f"Actualizado v{APP_VERSION}", "#2ecc71")
            return
        if not datos or not datos.get("url_descarga", "").strip():
            self._set_estado_actualizacion(f"Actualizado v{APP_VERSION}", "#2ecc71")
            return

        url_descarga = datos.get("url_descarga", "").strip()
        version_remota = datos.get("version", "?")
        novedades = datos.get("novedades", "").strip()
        self._set_estado_actualizacion(f"🆕 Versión v{version_remota} disponible", "#f1c40f")

        def preguntar():
            texto = f"Hay una nueva versión disponible: v{version_remota}\n(tienes v{APP_VERSION})"
            if novedades:
                texto += f"\n\nNovedades:\n{novedades}"
            texto += "\n\n¿Quieres actualizar ahora?"
            if mb.askyesno("Actualización disponible", texto):
                self.ejecutar_en_hilo(lambda: self._aplicar_actualizacion(url_descarga, version_remota))
            else:
                self._set_estado_actualizacion(
                    f"🆕 Versión v{version_remota} disponible (pendiente)", "#f1c40f")

        self.root.after(0, preguntar)

    def _aplicar_actualizacion(self, url_descarga, version_remota="?"):
        """Descarga la nueva versión y, si todo va bien, cierra la app para
        que el script de actualización termine el reemplazo y la reabra."""
        self._set_estado_actualizacion(f"⬇️ Descargando actualización v{version_remota}...", "#3498db")
        cerrar_app = descargar_y_aplicar_actualizacion(url_descarga)
        if cerrar_app:
            self.root.after(0, self.root.destroy)
        else:
            self._set_estado_actualizacion(
                f"⚠️ Arlequin no se pudo actualizar (sigues en v{APP_VERSION})", "#e74c3c")


def _fijar_identidad_taskbar_windows():
    """Sin esto, cuando el programa se lanza con python.exe (no como .exe
    compilado), Windows suele agrupar la ventana bajo el icono genérico de
    Python en la barra de tareas, aunque la ventana ya tenga su propio
    icono.ico puesto con iconbitmap(). Al darle a la app un AppUserModelID
    propio, Windows la trata como una aplicación independiente y usa el
    icono real en la barra de tareas. No tiene efecto ni falla en Linux/Mac."""
    if not _ES_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ArlequinSaveHub.App")
    except Exception:
        pass


def _es_admin_windows():
    """Devuelve True/False si se puede determinar si el proceso actual tiene
    privilegios de administrador en Windows, o None si no se ha podido
    comprobar (por ejemplo, fuera de Windows)."""
    if not _ES_WINDOWS:
        return None
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


def verificar_permisos_criticos(root):
    """Comprueba, nada más arrancar, que el programa puede realmente leer y
    escribir en las carpetas que necesita.

    El .exe se compila con --uac-admin, lo que en condiciones normales hace
    que Windows pida elevación antes de dejar arrancar el programa. Pero hay
    casos raros en los que eso no basta:
      - El UAC está desactivado y la cuenta es estándar (no administrador):
        según la configuración de Windows, el programa puede terminar
        ejecutándose SIN privilegios de administrador en vez de bloquearse.
      - Alguna política de grupo o antivirus interfiere con la elevación.
    Si eso pasa y no se comprueba nada, el programa se abriría con normalidad
    y fallaría más tarde, a mitad de un backup o una restauración, con un
    error críptico. Aquí se hace una prueba de escritura real, al principio,
    para poder avisar de forma amigable y clara si algo no va a funcionar.

    Devuelve True si se puede continuar (todo bien, o el usuario decide
    continuar de todas formas) y False si el usuario prefiere cerrar el
    programa.
    """
    if not _ES_WINDOWS:
        return True

    carpetas_a_probar = [APP_GAMESAVES_DIR, BKP]
    carpetas_con_problemas = []

    for carpeta in carpetas_a_probar:
        try:
            os.makedirs(carpeta, exist_ok=True)
            ruta_prueba = os.path.join(carpeta, f".permtest_{uuid.uuid4().hex[:8]}.tmp")
            with open(ruta_prueba, "w") as f:
                f.write("test")
            os.remove(ruta_prueba)
        except Exception as exc:
            carpetas_con_problemas.append((carpeta, exc))

    if not carpetas_con_problemas:
        return True

    es_admin = _es_admin_windows()
    detalle = "\n".join(f"• {c}" for c, _ in carpetas_con_problemas)
    aviso_admin = ""
    if es_admin is False:
        aviso_admin = (
            "\n\nParece que el programa NO se está ejecutando como "
            "administrador. Esto puede pasar si el Control de Cuentas de "
            "Usuario (UAC) está desactivado, si tu cuenta es una cuenta "
            "estándar sin acceso a una contraseña de administrador, o si "
            "se canceló el aviso de permisos al abrir el programa."
        )

    mensaje = (
        "Arlequin SaveHub no tiene permisos suficientes para escribir en "
        f"estas carpetas:\n\n{detalle}{aviso_admin}\n\n"
        "Prueba a cerrar el programa y volver a abrirlo haciendo clic derecho "
        "sobre él y eligiendo \"Ejecutar como administrador\". Si el problema "
        "continúa, revisa los permisos de esas carpetas o la configuración "
        "de UAC de tu cuenta de Windows.\n\n"
        "¿Quieres continuar de todas formas? Es posible que algunas "
        "funciones (guardar copias, escanear, etc.) fallen."
    )

    try:
        return mb.askyesno("Permisos insuficientes", mensaje, parent=root)
    except Exception:
        # Si ni siquiera se puede mostrar el aviso, dejamos continuar: es
        # preferible intentarlo a bloquear el programa por completo.
        return True


if __name__ == "__main__":
    _fijar_identidad_taskbar_windows()
    root = tk.Tk()
    root.withdraw()
    if not verificar_permisos_criticos(root):
        root.destroy()
        sys.exit(0)
    root.deiconify()
    app = GestorPartidasLocal(root)
    root.mainloop()
