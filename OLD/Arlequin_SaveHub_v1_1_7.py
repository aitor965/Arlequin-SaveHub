# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Arlequin SaveHub v1.1.7 by aitor965 — https://github.com/aitor965/Arlequin-SaveHub

Copyright (C) 2026 aitor965 <arlequinsavehub@gmail.com>

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details (LICENSE). The game database ArlequinGameDB.yaml is licensed separately
under CC BY-NC-SA 3.0 (see LICENSE-DATABASE.md).

Novedades de la v1.1.7 (resumen; detalle en README.md):
  - Partidas guardadas en el registro de Windows (exportadas a .reg).
  - Contadores de copias locales y en la nube en la lista principal.
  - Elegir qué copia descargar de la nube; "↩️ Antes de restaurar" para deshacer.
  - Opciones reorganizadas (General / Local / Nube) y opciones nuevas: avisos,
    verificación semanal, exclusión de archivos, juegos online, OBS abierto...
  - Escaneo 4-6 veces más rápido y varias correcciones de fiabilidad.

Diseño general:
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
  - Integración inicial con Google Drive mediante OAuth y permiso drive.file,
    con cargas ZIP reanudables y token persistente en APPDATA.
"""

import os
import sys
import re
import json
import sqlite3
import time
import gzip
import hashlib
import glob
import fnmatch
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
import webbrowser
import subprocess
import logging
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from difflib import SequenceMatcher
import urllib.request
import urllib.error
import urllib.parse
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox as mb
from tkinter import filedialog as fd
from tkinter import simpledialog as sd
from tkinter import ttk

try:
    import winreg
    _ES_WINDOWS = True
except ImportError:
    _ES_WINDOWS = False  # por si se abre el archivo fuera de Windows

def _instalar_paquetes_pip(*paquetes):
    """Instala dependencias con pip SOLO cuando se ejecuta el .py.

    En el .exe (PyInstaller) sys.executable es el propio Arlequin_SaveHub.exe:
    llamar a "sys.executable -m pip" abriría otra copia del programa en vez
    de instalar nada. En ese caso las librerías deben ir ya empaquetadas.
    """
    if getattr(sys, "frozen", False):
        raise ImportError("Dependencia no incluida en el ejecutable: " + ", ".join(paquetes))
    subprocess.check_call([sys.executable, "-m", "pip", "install", *paquetes, "--quiet"])


try:
    import yaml
except ImportError:
    try:
        import subprocess
        import sys
        _instalar_paquetes_pip("pyyaml")
        import yaml
    except Exception:
        yaml = None  # si no se puede instalar, el manifest no se podrá leer

# Google Drive / OAuth. Se usa acceso directo a la API de Drive para mantener
# ASH en un solo .py y controlar explícitamente las cargas reanudables.
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials as GoogleCredentials
    from google.auth.transport.requests import Request as GoogleAuthRequest
except ImportError:
    try:
        _instalar_paquetes_pip("google-auth", "google-auth-oauthlib")
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials as GoogleCredentials
        from google.auth.transport.requests import Request as GoogleAuthRequest
    except Exception:
        InstalledAppFlow = None
        GoogleCredentials = None
        GoogleAuthRequest = None

# Bandeja del sistema para el modo de inicio minimizado.
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    try:
        _instalar_paquetes_pip("pystray", "pillow")
        import pystray
        from PIL import Image, ImageDraw
    except Exception:
        pystray = None
        Image = None
        ImageDraw = None


DESKTOP_PATH = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop').replace("\\", "/")
if not os.path.exists(DESKTOP_PATH):
    DESKTOP_PATH = os.path.expanduser("~/Desktop").replace("\\", "/")

APP_ARLEQUIN_SAVEHUB_DIR = os.path.join(os.getenv('APPDATA') or os.path.expanduser("~"), 'Arlequin SaveHub').replace("\\", "/")
if not os.path.exists(APP_ARLEQUIN_SAVEHUB_DIR):
    os.makedirs(APP_ARLEQUIN_SAVEHUB_DIR, exist_ok=True)

# Google Drive / OAuth. Estas rutas dependen de APP_ARLEQUIN_SAVEHUB_DIR, por lo que
# deben declararse después de crear la carpeta de datos de ASH.
GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
# Credenciales OAuth integradas para evitar que el usuario tenga que seleccionar un JSON externo.
GOOGLE_EMBEDDED_CLIENT_CONFIG = '{"installed":{"client_id":"161551432311-23mgcn2pf0q3i63sa1jp5u78ugti6058.apps.googleusercontent.com","project_id":"arlequin-savehub-510109","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"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","redirect_uris":["http://localhost"]}}'
GOOGLE_CLOUD_DIR = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "Google Drive").replace("\\", "/")
GOOGLE_CREDENTIALS_FILE = os.path.join(GOOGLE_CLOUD_DIR, "client_credentials.json").replace("\\", "/")
GOOGLE_TOKEN_FILE = os.path.join(GOOGLE_CLOUD_DIR, "token.json").replace("\\", "/")
GOOGLE_UPLOAD_STATE_FILE = os.path.join(GOOGLE_CLOUD_DIR, "upload_state.json").replace("\\", "/")
GOOGLE_CLOUD_MANIFEST_FILE = os.path.join(GOOGLE_CLOUD_DIR, "cloud_manifest.json").replace("\\", "/")
GOOGLE_CLOUD_MANIFEST_NAME = "ArlequinConfigNube.json"  # Nombre del manifiesto remoto en Google Drive

os.makedirs(GOOGLE_CLOUD_DIR, exist_ok=True)

# No creamos todavía "Arlequin Backups": la primera ejecución debe poder
# preguntar al usuario si quiere utilizar el Escritorio o elegir otra ubicación.
BKP = os.path.join(DESKTOP_PATH, 'Arlequin Backups').replace("\\", "/")
BKP_EXISTIA_AL_ARRANCAR = os.path.isdir(BKP)
UP = os.environ.get('USERPROFILE', os.path.expanduser('~')).replace("\\", "/")
M_O = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "juegos_ocultos.txt").replace("\\", "/")
M_M = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "juegos_manuales.txt").replace("\\", "/")
M_C = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "carpetas_sin_launcher.txt").replace("\\", "/")
# Configuración general de la app: máximo de copias históricas y ubicación
# persistente de la carpeta de backups.
M_CFG = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "config.json").replace("\\", "/")
LOG_FILE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "app.log").replace("\\", "/")
DETECTION_CACHE_FILE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "detection_cache.json").replace("\\", "/")
# Inventario persistente de los juegos que Windows/los launchers detectan como instalados.
# Es independiente de la base de datos de saves: puede contener juegos online o juegos
# que ASH todavía no conoce.
INSTALLED_GAMES_FILE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "installed_games.json").replace("\\", "/")
# Índice persistente de carpetas raíz de instalaciones que ASH ya ha podido
# descubrir a partir de otros juegos instalados. Se usa para encontrar juegos
# DRM-free/portables que comparten una carpeta (p. ej. E:/Juegos/CS2 y
# E:/Juegos/Borderlands 2) sin tener que volver a recorrerlas a ciegas.
KNOWN_GAME_PATHS_FILE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "known_game_paths.json").replace("\\", "/")
BACKUP_METADATA_NAME = "ash_backup.json"
BACKUP_HASH_ALGORITHM = "sha256"
BACKUP_SPACE_MARGIN = 0.10  # 10% de margen de seguridad para el espacio libre

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
#   stores: [steam, gog]    (opcional, tiendas del juego; se usa sobre todo en
#     fichas sin rutas, cuyas rutas no llevan [store=...])
#   save_locations:
#     - "<plantilla>/de/ruta [os=windows, store=steam]"
#     (puede ser una lista vacía [] si no se conoce la ruta de guardado)
#   registry:               (opcional) claves de HKEY_CURRENT_USER donde el juego
#     - "HKEY_CURRENT_USER/Software/Estudio/Juego"   guarda la partida; se
#     exportan a .reg en REGISTRO_DIR/<Juego> y se respaldan como una ruta más
#   no_save_path: true      (opcional, marca explícita de "juego conocido pero
#     sin ruta de guardado registrada"; el escaneo lo muestra en
#     "SIN DATOS DE GUARDADO CONOCIDOS" y no intenta respaldarlo)
#   probable_save_path: true (opcional, las rutas son una suposición -p. ej.
#     Steam Cloud userdata/<id>/<appid>/remote-; si no existen en disco el
#     juego se trata como "sin datos", no como ruta prevista)
#   acronyms: "alias1, alias2, ..."  (opcional, NUEVO: alias/acrónimos
#     alternativos del juego separados por comas, p. ej. "AoE2, AoE, AoEII".
#     Se indexan igual que "name" para mejorar la detección cuando el
#     launcher -EA app, Amazon Games, Xbox...- reporta el juego con un
#     nombre distinto al oficial.)
# Las condiciones entre corchetes al final de cada ruta son opcionales; si
# faltan, la ruta se considera válida siempre. Varios valores de la misma
# clave (p. ej. "os=windows, os=linux") son un OR; claves distintas dentro
# del mismo corchete son un AND.
MANIFEST_URL = ("https://raw.githubusercontent.com/aitor965/Arlequin-SaveHub/refs/heads/main/ArlequinGameDB.yaml")
MANIFEST_CACHE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "ArlequinGameDB.yaml").replace("\\", "/")
# NOTA: ya no hay un temporizador de "refrescar cada X días" a ciegas. En
# cada arranque se comprueba contra GitHub con ETag / If-None-Match (ver
# descargar_manifest): si el YAML no ha cambiado, la respuesta es un 304
# Not Modified de 0 bytes, así que comprobarlo siempre sale gratis.

# Caché del YAML ya parseado e indexado (manifest + los tres índices de
# construir_indices_manifest), para no tener que volver a hacer yaml.load()
# sobre el archivo completo (~84.000 líneas) en cada arranque. Solo se
# regenera cuando cambia la "firma" (tamaño + fecha de modificación) del
# YAML de origen, es decir, cuando se ha descargado una versión nueva.
MANIFEST_PARSED_CACHE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "ArlequinGameDB_parsed.json").replace("\\", "/")

# ETag devuelto por GitHub en la última descarga correcta del YAML. Se manda
# de vuelta como cabecera If-None-Match en la siguiente comprobación: si el
# archivo remoto no ha cambiado, GitHub responde 304 Not Modified (0 bytes,
# prácticamente instantáneo) en vez de tener que volver a mandar el YAML
# entero (comprimido o no) solo para comprobar si hace falta actualizarlo.
MANIFEST_ETAG_CACHE = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "ArlequinGameDB.etag").replace("\\", "/")

# ---------------------------------------------------------------------------
#  VERSIÓN Y AUTOACTUALIZACIÓN (contra un version.json en el propio repo)
# ---------------------------------------------------------------------------

APP_VERSION = "1.1.7"

# Debe apuntar a un fichero "version.json" en la raíz del repo con este
# formato (el mismo que ya tienes preparado):
#   {
#     "version": "1.0.1",
#     "url_descarga": "https://github.com/aitor965/Arlequin-SaveHub/releases/latest/download/Arlequin_SaveHub.exe",
#     "novedades": "Texto que se muestra al usuario"
#   }
VERSION_CHECK_URL = ("https://raw.githubusercontent.com/aitor965/Arlequin-SaveHub/refs/heads/main/version.json")

# Enlaces de apoyo al proyecto (ventana "Donar"). Mantener sincronizados con
# .github/FUNDING.yml y README.md.
DONAR_PAYPAL_URL = "https://www.paypal.me/ArlequinSaveHub"
DONAR_GITHUB_SPONSORS_URL = "https://github.com/sponsors/aitor965"


def _version_a_tupla(texto_version):
    """Convierte una versión en una tupla comparable.

    Admite versiones finales ('1.2.10', 'v1.2.10') y previas
    ('1.1.6.beta14', '1.1.6-beta14', '1.1.6rc1'). Una versión previa es
    siempre MENOR que la final con los mismos números:
        1.1.6.alpha2 < 1.1.6.beta14 < 1.1.6.rc1 < 1.1.6 < 1.1.7
    """
    texto = str(texto_version).strip().lstrip("vV").lower()
    m = re.match(r"^(\d+(?:\.\d+)*)(.*)$", texto)
    if not m:
        return ((0, 0, 0, 0), 3, 0)
    numeros = [int(x) for x in m.group(1).split(".")]
    numeros = tuple((numeros + [0, 0, 0, 0])[:4])
    resto = m.group(2).strip(" .-_+")
    if not resto:
        return (numeros, 3, 0)  # versión final
    etapas = (("alpha", 0), ("a", 0), ("beta", 1), ("b", 1), ("rc", 2), ("pre", 2))
    etapa = 1
    for prefijo, valor in etapas:
        if resto.startswith(prefijo):
            etapa = valor
            break
    num = re.search(r"(\d+)", resto)
    return (numeros, etapa, int(num.group(1)) if num else 0)


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


def descargar_y_aplicar_actualizacion(url_descarga, sha256_esperado=None, avisar=None):
    """Actualizador robusto para EXE PyInstaller situado en cualquier carpeta.

    Se ejecuta en un hilo secundario: los mensajes al usuario pasan por
    `avisar(tipo, titulo, texto)` (tipo "info"/"error"), que el llamador
    debe encaminar al hilo de Tkinter. Tkinter no admite abrir ventanas
    desde otros hilos (puede colgar o cerrar la app).

    Si version.json incluye "sha256", el EXE descargado se verifica contra
    él antes de instalarlo; si no coincide, se descarta.

    - Descarga junto al EXE actual.
    - El proceso actual se identifica por PID.
    - El EXE anterior se conserva temporalmente para poder hacer rollback.
    - El nuevo EXE se lanza mediante Explorer, evitando heredar un cmd.exe
      temporal como proceso padre.
    - El BAT comprueba durante unos segundos que el nuevo proceso arranca;
      si no aparece, restaura automáticamente el EXE anterior.
    """
    if avisar is None:
        def avisar(tipo, titulo, texto):
            (mb.showerror if tipo == "error" else mb.showinfo)(titulo, texto)

    if not getattr(sys, "frozen", False):
        avisar(
            "info", "Actualización",
            "Estás ejecutando el código fuente (.py), no el .exe compilado.\n"
            "Se abrirá el enlace de descarga en el navegador."
        )
        webbrowser.open(url_descarga)
        return False

    exe_actual = os.path.abspath(sys.executable)
    carpeta = os.path.dirname(exe_actual)
    nombre_exe_actual = os.path.basename(exe_actual)
    nuevo_exe = os.path.join(carpeta, "_Arlequin_SaveHub_nuevo.exe")
    anterior_exe = os.path.join(carpeta, "_Arlequin_SaveHub_anterior.exe")
    pid_actual = os.getpid()

    try:
        peticion = urllib.request.Request(
            url_descarga, headers={"User-Agent": "Arlequin-SaveHub-Updater"})
        with urllib.request.urlopen(peticion, timeout=60) as resp:
            try:
                esperado = int(resp.headers.get("Content-Length") or 0)
            except ValueError:
                esperado = 0
            with open(nuevo_exe, "wb") as f:
                shutil.copyfileobj(resp, f)
        tam = os.path.getsize(nuevo_exe) if os.path.isfile(nuevo_exe) else 0
        if tam < 100_000:
            raise RuntimeError("la descarga del nuevo EXE parece incompleta")
        if esperado and tam != esperado:
            raise RuntimeError(f"descarga incompleta ({tam:,} de {esperado:,} bytes)")
        with open(nuevo_exe, "rb") as f:
            if f.read(2) != b"MZ":
                raise RuntimeError("el archivo descargado no es un ejecutable de Windows")
        sha256_esperado = str(sha256_esperado or "").strip().lower()
        if sha256_esperado:
            real = _sha256_archivo(nuevo_exe)
            if real != sha256_esperado:
                raise RuntimeError(
                    "la huella SHA-256 del EXE descargado no coincide con la publicada "
                    f"(esperada {sha256_esperado[:12]}…, recibida {real[:12]}…)")
    except Exception as e:
        logging.error(f"Fallo al descargar la actualización: {e}")
        try:
            if os.path.exists(nuevo_exe): os.remove(nuevo_exe)
        except Exception: pass
        avisar("error", "Actualización", f"No se pudo descargar la actualización:\n{e}")
        return False

    # BAT independiente: funciona aunque ASH esté instalado en Escritorio,
    # otra unidad, una carpeta personalizada o una ruta con espacios.
    bat_path = os.path.join(os.environ.get("TEMP", carpeta), f"arlequin_update_{pid_actual}.bat")
    contenido_bat = (
        "@echo off\r\n"
        "setlocal EnableExtensions\r\n"
        f'set "VIEJO={exe_actual}"\r\n'
        f'set "NUEVO={nuevo_exe}"\r\n'
        f'set "ANTERIOR={anterior_exe}"\r\n'
        f'set "PID_ASH={pid_actual}"\r\n'
        f'set "NOMBRE_EXE={nombre_exe_actual}"\r\n'
        ":esperar_ash\r\n"
        'tasklist /FI "PID eq %PID_ASH%" 2>NUL | find /I "%PID_ASH%" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >NUL\r\n"
        "    goto esperar_ash\r\n"
        ")\r\n"
        ":preparar_anterior\r\n"
        'if exist "%ANTERIOR%" del /F /Q "%ANTERIOR%" >NUL 2>NUL\r\n'
        'if exist "%VIEJO%" move /Y "%VIEJO%" "%ANTERIOR%" >NUL 2>NUL\r\n'
        'if exist "%VIEJO%" goto preparar_anterior\r\n'
        ":instalar_nuevo\r\n"
        'move /Y "%NUEVO%" "%VIEJO%" >NUL 2>NUL\r\n'
        'if exist "%NUEVO%" ( timeout /t 1 /nobreak >NUL & goto instalar_nuevo )\r\n'
        'start "" explorer.exe "%VIEJO%"\r\n'
        "set /a INTENTOS=0\r\n"
        ":comprobar_arranque\r\n"
        'tasklist /FI "IMAGENAME eq %NOMBRE_EXE%" 2>NUL | find /I "%NOMBRE_EXE%" >NUL\r\n'
        "if not errorlevel 1 goto exito\r\n"
        "set /a INTENTOS+=1\r\n"
        "if %INTENTOS% GEQ 15 goto rollback\r\n"
        "timeout /t 1 /nobreak >NUL\r\n"
        "goto comprobar_arranque\r\n"
        ":exito\r\n"
        'del /F /Q "%ANTERIOR%" >NUL 2>NUL\r\n'
        'del /F /Q "%~f0" >NUL 2>NUL\r\n'
        "exit /b 0\r\n"
        ":rollback\r\n"
        'if exist "%VIEJO%" del /F /Q "%VIEJO%" >NUL 2>NUL\r\n'
        'if exist "%ANTERIOR%" move /Y "%ANTERIOR%" "%VIEJO%" >NUL 2>NUL\r\n'
        'if exist "%VIEJO%" start "" explorer.exe "%VIEJO%"\r\n'
        'if exist "%NUEVO%" del /F /Q "%NUEVO%" >NUL 2>NUL\r\n'
        'del /F /Q "%~f0" >NUL 2>NUL\r\n'
        "exit /b 1\r\n"
    )
    try:
        with open(bat_path, "w", encoding="utf-8") as f: f.write(contenido_bat)
        subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
        return True
    except Exception as e:
        logging.error(f"Fallo al preparar el relanzamiento automático: {e}")
        avisar("error", "Actualización", f"La descarga terminó pero no se pudo preparar el reinicio automático:\n{e}\n\nEl nuevo EXE quedó en:\n{nuevo_exe}")
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
    """Construye índices de identidad para la BD.

    Una coincidencia ambigua NO se resuelve arbitrariamente con ``setdefault``.
    Si un alias o un ID pertenece a más de una ficha, se deja fuera del índice
    y la detección tendrá que apoyarse en otra evidencia. Esto evita que un
    acrónimo genérico (por ejemplo ``BL``) o un ID compartido fabrique un
    falso positivo.
    """
    por_nombre_tmp, por_steam_tmp, por_gog_tmp = {}, {}, {}

    def anadir(tmp, clave, nombre):
        if not clave:
            return
        tmp.setdefault(clave, set()).add(nombre)

    for nombre_juego, datos in manifest.items():
        if not isinstance(datos, dict):
            continue
        anadir(por_nombre_tmp, _norm(nombre_juego), nombre_juego)

        acronimos = datos.get("acronyms")
        if acronimos:
            valores = acronimos if isinstance(acronimos, (list, tuple, set)) else str(acronimos).split(",")
            for alias in valores:
                anadir(por_nombre_tmp, _norm(alias), nombre_juego)

        ids = datos.get("ids") or {}
        if isinstance(ids, dict):
            try:
                steam_id = ids.get("steam")
                if steam_id is not None and str(steam_id).strip():
                    anadir(por_steam_tmp, str(steam_id).strip(), nombre_juego)
                for extra_id in ids.get("steamExtra") or []:
                    if extra_id is not None and str(extra_id).strip():
                        anadir(por_steam_tmp, str(extra_id).strip(), nombre_juego)
            except Exception:
                pass
            try:
                gog_id = ids.get("gog")
                if gog_id is not None and str(gog_id).strip():
                    anadir(por_gog_tmp, str(gog_id).strip(), nombre_juego)
                for extra_id in ids.get("gogExtra") or []:
                    if extra_id is not None and str(extra_id).strip():
                        anadir(por_gog_tmp, str(extra_id).strip(), nombre_juego)
            except Exception:
                pass

    def solo_unicos(tmp):
        return {k: next(iter(v)) for k, v in tmp.items() if len(v) == 1}

    return solo_unicos(por_nombre_tmp), solo_unicos(por_steam_tmp), solo_unicos(por_gog_tmp)


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


class _IndiceCarpetasEscaneo:
    """Filtro previo del rastreo por catálogo.

    La mayoría de saves cuelgan de unas pocas carpetas contenedoras
    (Documents/My Games, Saved Games, AppData/Roaming, Local, LocalLow,
    RenPy, Godot/app_userdata...). En vez de preguntar al disco por cada
    ruta de cada ficha (decenas de miles de isdir()/glob()), se lista cada
    carpeta UNA sola vez por escaneo y se comprueba en memoria si los
    primeros niveles de la ruta existen.

    Es conservador: solo responde False cuando SABE que un componente de la
    ruta no existe. Ante cualquier duda (ruta fuera de las raíces conocidas,
    error de permisos, comodín) responde True y la ruta se resuelve como
    siempre, así que nunca oculta un save que antes se encontraba.
    """

    _COMODINES = re.compile(r"[*?\[{]")
    PROFUNDIDAD = 3

    def __init__(self, contextos):
        anclas = set()
        for ctx in contextos:
            for clave in ("home", "winAppData", "winLocalAppData", "winDocuments",
                          "winPublic", "winProgramData", "root"):
                valor = (ctx.get(clave) or "").replace("\\", "/").rstrip("/")
                if valor:
                    anclas.add(valor.lower())
            local = (ctx.get("winLocalAppData") or "").replace("\\", "/").rstrip("/")
            if local:
                anclas.add((local + "Low").lower())
        # De más larga a más corta: gana la raíz más concreta.
        self._anclas = sorted((a for a in anclas if os.path.isdir(a)), key=len, reverse=True)
        self._listados = {}

    def _listar(self, carpeta):
        try:
            return self._listados[carpeta]
        except KeyError:
            pass
        try:
            contenido = {n.lower() for n in os.listdir(carpeta)}
        except Exception:
            contenido = None
        self._listados[carpeta] = contenido
        return contenido

    def puede_existir(self, ruta):
        p = ruta.replace("\\", "/")
        m = self._COMODINES.search(p)
        if m:
            p = p[:m.start()]
            p = p[:p.rfind("/")] if "/" in p else ""
        p = p.rstrip("/").lower()
        if not p:
            return True
        for ancla in self._anclas:
            if p == ancla:
                return True
            if p.startswith(ancla + "/"):
                break
        else:
            return True  # fuera de las raíces conocidas: no se filtra
        actual = ancla
        for parte in p[len(ancla) + 1:].split("/")[:self.PROFUNDIDAD]:
            if not parte:
                continue
            contenido = self._listar(actual)
            if contenido is None:
                return True
            if parte not in contenido:
                return False
            actual = actual + "/" + parte
        return True

    def juego_puede_tener_save(self, datos_juego, contexto, store_actual):
        # El registro no son carpetas: se comprueba aparte (siempre pasa).
        if (datos_juego or {}).get("registry"):
            return True
        for entrada in (datos_juego or {}).get("save_locations") or []:
            plantilla, condiciones = _parsear_entrada_save_location(entrada)
            if not plantilla or not condicion_aplica_en_windows(condiciones, store_actual):
                continue
            for candidata in _sustituir_placeholders(plantilla, contexto):
                if self.puede_existir(candidata):
                    return True
        return False


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
        # Contenedores de motor/lanzador compartidos por muchos juegos
        # (según el análisis de ArlequinGameDB v1.4: RenPy ~230
        # juegos, Godot ~115, DefaultCompany de Unity ~35, etc.). Una
        # plantilla con comodín que se recorte hasta aquí no identifica a
        # ningún juego concreto.
        os.path.join(app_data, "RenPy") if app_data else "",
        os.path.join(app_data, "Godot") if app_data else "",
        os.path.join(app_data, "Godot", "app_userdata") if app_data else "",
        os.path.join(app_data, "MMFApplications") if app_data else "",
        os.path.join(app_data, "Macromedia", "Flash Player") if app_data else "",
        os.path.join(local_app_data + "Low", "DefaultCompany") if local_app_data else "",
        os.path.join(local_app_data, "GOG.com", "Galaxy", "Applications") if local_app_data else "",
        os.path.join(documentos, "SavedGames") if documentos else "",
        os.path.join(documentos, "Saved Games") if documentos else "",
        (os.path.join(entorno.get("root", ""), "steamapps", "common")
         if entorno.get("root") else ""),
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


# Carpetas habituales donde la gente instala juegos fuera de los launchers.
# Al arrancar, ASH mira si existen en la RAÍZ de cada unidad local (C:/,
# D:/, E:/...). Si existen, se registran como raíces conocidas y se revisan
# sus subcarpetas (un nivel) buscando juegos de la BD. Windows no distingue
# mayúsculas, así que "Games" también cubre "games" o "GAMES".
COMMON_GAME_ROOT_NAMES = (
    "Games", "Game", "Juegos", "Juego", "Jocs", "Jogos",
    "PC Games", "PCGames", "Juegos PC", "JuegosPC",
    "GOG Games", "GOG", "Epic Games", "EA Games", "Ubisoft Games",
    "XboxGames", "Riot Games", "Portable Games", "Juegos Portables",
)

# Rutas de varios niveles, relativas a la raíz de cada unidad, donde suelen
# vivir bibliotecas de juegos. Cada entrada es una tupla de partes.
COMMON_GAME_ROOT_RELATIVE = (
    ("SteamLibrary", "steamapps", "common"),
    ("Steam", "steamapps", "common"),
    ("Games", "SteamLibrary", "steamapps", "common"),
    ("Juegos", "SteamLibrary", "steamapps", "common"),
    ("Program Files (x86)", "Steam", "steamapps", "common"),
    ("Program Files", "Steam", "steamapps", "common"),
    ("Program Files", "Epic Games"),
    ("Program Files (x86)", "Epic Games"),
    ("Program Files (x86)", "GOG Galaxy", "Games"),
    ("GOG Galaxy", "Games"),
    ("Program Files", "EA Games"),
    ("Program Files (x86)", "Origin Games"),
    ("Program Files (x86)", "Ubisoft", "Ubisoft Game Launcher", "games"),
    ("Amazon Games", "Library"),
    ("Games", "GOG"),
    ("Games", "Epic Games"),
    ("Juegos", "GOG"),
    ("Juegos", "Epic Games"),
)


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


def _obs_esta_abierto_proceso():
    """Devuelve True si OBS Studio está actualmente abierto.

    Se usa como barrera para tareas AUTOMÁTICAS de ASH. No bloquea por sí sola
    las operaciones manuales: abrir OBS no debe impedir al usuario hacer un
    backup/restauración deliberadamente desde la interfaz.
    """
    try:
        activos = _listar_procesos_en_ejecucion()
        return bool({"obs64.exe", "obs32.exe", "obs.exe"} & activos)
    except Exception:
        return False


PROCESOS_SINCRONIZACION = {
    "onedrive.exe": "OneDrive", "dropbox.exe": "Dropbox",
    "googledrivesync.exe": "Google Drive", "drivefs.exe": "Google Drive",
    "iclouddrive.exe": "iCloud Drive",
}

def _sincronizadores_activos():
    activos = _listar_procesos_en_ejecucion()
    return [nombre for exe, nombre in PROCESOS_SINCRONIZACION.items() if exe.lower() in activos]

def _ruta_bajo_de(ruta, padre):
    try:
        if not padre: return False
        return os.path.commonpath([os.path.abspath(ruta), os.path.abspath(padre)]) == os.path.abspath(padre)
    except Exception:
        return False

# ---------------------------------------------------------------------------
#  CÁLCULO DE TAMAÑO DE CARPETAS
# ---------------------------------------------------------------------------

def _coincide_patron(nombre, patrones):
    """True si `nombre` coincide con algún patrón (comodines * ?), sin
    distinguir mayúsculas. Los nombres exactos también son patrones."""
    if not patrones:
        return False
    n = str(nombre).lower()
    return any(fnmatch.fnmatchcase(n, str(p).lower()) for p in patrones)


def _tamano_carpeta_bytes(ruta, excluir_archivos=None, excluir_carpetas=None):
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
                        if not _coincide_patron(entry.name, excluir_carpetas):
                            total += _tamano_carpeta_bytes(entry.path, excluir_archivos, excluir_carpetas)
                    elif not _coincide_patron(entry.name, excluir_archivos):
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


# ---------------------------------------------------------------------------
#  SEGURIDAD, INTEGRIDAD Y DIAGNÓSTICO DE BACKUPS
# ---------------------------------------------------------------------------
def _contar_archivos_carpeta(ruta):
    total = 0
    try:
        for raiz, _, archivos in os.walk(ruta):
            total += len(archivos)
    except OSError:
        pass
    return total


def _sha256_archivo(ruta, chunk_size=1024 * 1024):
    import hashlib
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(chunk_size)
            if not bloque:
                break
            h.update(bloque)
    return h.hexdigest()


# ---------------------------------------------------------------------------
#  PARTIDAS GUARDADAS EN EL REGISTRO DE WINDOWS
# ---------------------------------------------------------------------------
# Muchos juegos (clásicos y, sobre todo, juegos Unity con PlayerPrefs) guardan
# la partida en HKEY_CURRENT_USER\Software\<Estudio>\<Juego>. La BD lo indica
# con la lista "registry". Para respaldarlos sin tocar el sistema de backups,
# las claves se EXPORTAN a archivos .reg dentro de una carpeta propia del juego
# (REGISTRO_DIR/<Juego>), y esa carpeta se trata como una ruta de save más:
# versionado, historial, "sin cambios", nube y "Antes de restaurar" funcionan
# igual. Al restaurar, los .reg se vuelven a importar (ver
# _importar_registro_carpeta). Solo HKEY_CURRENT_USER: no requiere permisos de
# administrador.
REGISTRO_DIR = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "Registro de Windows").replace("\\", "/")
_RAIZ_REGISTRO = "HKEY_CURRENT_USER"


def _clave_registro_windows(clave):
    """'HKEY_CURRENT_USER/Software/X' -> 'HKEY_CURRENT_USER\\Software\\X'
    (None si no es una clave de HKEY_CURRENT_USER utilizable)."""
    k = str(clave or "").replace("/", "\\").strip("\\ ")
    if not k.upper().startswith(_RAIZ_REGISTRO + "\\") or "*" in k:
        return None
    return _RAIZ_REGISTRO + k[len(_RAIZ_REGISTRO):]


def _clave_registro_existe(clave_win):
    if not _ES_WINDOWS or not clave_win:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave_win[len(_RAIZ_REGISTRO) + 1:]):
            return True
    except OSError:
        return False


def _nombre_carpeta_segura(nombre):
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(nombre)).strip(" .")
    return limpio or "Juego"


def _ejecutar_reg(*args):
    """Ejecuta reg.exe sin ventana. Devuelve (ok, salida)."""
    try:
        r = subprocess.run(["reg", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="cp850", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()
    except Exception as exc:
        return False, str(exc)


def _claves_en_archivo_reg(ruta):
    """Claves ([HKEY_...]) que modifica un archivo .reg."""
    datos = open(ruta, "rb").read()
    for cod in ("utf-16", "utf-8-sig", "cp1252"):
        try:
            texto = datos.decode(cod)
            if "[" in texto:
                break
        except UnicodeDecodeError:
            continue
    else:
        return None
    claves = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea.startswith("[") and linea.endswith("]"):
            claves.append(linea[1:-1].lstrip("-"))
    return claves

# ---------------------------------------------------------------------------
#  ESCRITURA SEGURA DE ARCHIVOS DE CONFIGURACIÓN
# ---------------------------------------------------------------------------
# config.json lo escriben varios hilos (Opciones, respaldos automáticos, nube,
# ubicación de backups...). Cada escritura es "leer -> cambiar -> escribir", así
# que sin un candado común dos hilos podían pisarse y perder cambios. Además se
# escribía directamente sobre el archivo: un corte de luz o un cierre a mitad
# dejaba un JSON truncado, y la siguiente lectura fallida hacía que se
# reescribiera config.json desde cero (perdiendo la carpeta de backups, la
# cuenta de la nube, etc.).
_CONFIG_LOCK = threading.RLock()


def _escribir_texto_atomico(ruta, texto):
    """Escribe en un temporal y lo sustituye de golpe (os.replace). Si el
    proceso muere a mitad, el archivo original sigue intacto."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    temporal = f"{ruta}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        # Un antivirus o el indexador pueden tener el archivo abierto un instante.
        for intento in range(5):
            try:
                os.replace(temporal, ruta)
                return
            except PermissionError:
                if intento == 4:
                    raise
                time.sleep(0.1 * (intento + 1))
    finally:
        if os.path.exists(temporal):
            try:
                os.remove(temporal)
            except OSError:
                pass


def _escribir_json_atomico(ruta, datos):
    _escribir_texto_atomico(ruta, json.dumps(datos, ensure_ascii=False, indent=2))


def _leer_config_para_modificar():
    """Lee config.json para modificarlo. Si existe pero está dañado, guarda
    una copia (config.json.danado-FECHA) antes de continuar, para que las
    opciones del usuario no se pierdan sin dejar rastro."""
    if not os.path.exists(M_CFG):
        return {}
    try:
        with open(M_CFG, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except Exception as exc:
        copia = f"{M_CFG}.danado-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            shutil.copy2(M_CFG, copia)
        except Exception:
            copia = "(no se pudo copiar)"
        logging.getLogger("ArlequinSaveManager").error(
            "config.json ilegible (%s); copia guardada en %s", exc, copia)
        return {}


def _actualizar_config(cambios):
    """Aplica `cambios` (dict) a config.json de forma atómica y sin carreras
    entre hilos. Devuelve True si se guardó."""
    with _CONFIG_LOCK:
        datos = _leer_config_para_modificar()
        datos.update(cambios)
        _escribir_json_atomico(M_CFG, datos)
    return True

# ---------------------------------------------------------------------------
#  APLICACIÓN
# ---------------------------------------------------------------------------

class GestorPartidasLocal:
    def _formatear_bytes(self, valor):
        """Convierte bytes a una unidad legible para mostrar tamaños en la UI.
        Devuelve "—" si el valor no es numérico (p. ej. cuota de Drive desconocida)."""
        try:
            n = float(valor)
        except (TypeError, ValueError):
            return "—"
        unidades = ("B", "KB", "MB", "GB", "TB", "PB")
        i = 0
        while abs(n) >= 1024.0 and i < len(unidades) - 1:
            n /= 1024.0
            i += 1
        if i == 0:
            return f"{int(n)} {unidades[i]}"
        return f"{n:.1f} {unidades[i]}"

    def abrir_carpeta_backups(self):
        if not os.path.exists(self.dest):
            os.makedirs(self.dest, exist_ok=True)
        os.startfile(os.path.normpath(self.dest))

    def cambiar_carpeta(self):
        r = fd.askdirectory(initialdir=self.dest)
        if r:
            self.dest = os.path.normpath(r).replace("\\", "/")
            self._guardar_ruta_backup_config(self.dest)
            self.lbl_r.config(text=f"Guardando en: {self.dest}")

    def _crear_icono_bandeja(self):
        """Carga el icono de ASH para mostrarlo en la bandeja del sistema."""
        if Image is None:
            return None
        try:
            if os.path.exists(ICON_PATH):
                img = Image.open(ICON_PATH).convert("RGBA")
                img.thumbnail((32, 32), Image.LANCZOS)
                lienzo = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
                lienzo.alpha_composite(img, ((32 - img.width) // 2, (32 - img.height) // 2))
                return lienzo
        except Exception as e:
            self._log("WARNING", f"No se pudo cargar el icono para la bandeja: {e}")
        try:
            img = Image.new("RGBA", (32, 32), (44, 62, 80, 255))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((2, 2, 30, 30), radius=5, outline=(255, 255, 255, 255), width=2)
            draw.text((8, 7), "A", fill=(255, 255, 255, 255))
            return img
        except Exception:
            return None

    def _mostrar_desde_bandeja(self, icono=None, item=None):
        """Restaura la ventana desde la bandeja."""
        try:
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)
            self.root.after(50, lambda: self.root.attributes("-topmost", True))
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
            self.root.after(180, self.root.focus_force)
        except Exception as e:
            self._log("ERROR", f"No se pudo restaurar la ventana desde la bandeja: {e}")

    def _salir_desde_bandeja(self, icono=None, item=None):
        """Solicita confirmación al salir desde la bandeja si los respaldos al cierre están activos."""
        def cerrar_confirmado():
            self._cerrando_desde_tray = True
            try:
                if icono is not None:
                    icono.stop()
            except Exception:
                pass
            self.root.destroy()

        def comprobar_salida():
            if self._confirmar_cierre_si_respaldos_al_cierre():
                cerrar_confirmado()

        self.root.after(0, comprobar_salida)

    def _iniciar_bandeja(self):
        """Inicia el icono de Arlequin SaveHub en la bandeja del sistema."""
        if pystray is None:
            self._log("WARNING", "pystray/Pillow no está disponible; no se puede usar la bandeja.")
            return False
        if self._tray_icon is not None:
            return True
        imagen = self._crear_icono_bandeja()
        if imagen is None:
            return False
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Abrir Arlequin SaveHub", self._mostrar_desde_bandeja, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", self._salir_desde_bandeja),
            )
            self._tray_icon = pystray.Icon("ArlequinSaveHub", imagen, "Arlequin SaveHub", menu)
            self._tray_thread = threading.Thread(
                target=self._tray_icon.run,
                name="ArlequinSaveHubTray",
                daemon=True,
            )
            self._tray_thread.start()
            return True
        except Exception as e:
            self._tray_icon = None
            self._log("ERROR", f"No se pudo iniciar el icono de bandeja: {e}")
            return False

    def ocultar_en_bandeja(self):
        """Oculta la ventana y la deja accesible desde la bandeja."""
        if self._iniciar_bandeja():
            self.root.withdraw()

    def _confirmar_cierre_si_respaldos_al_cierre(self):
        """Pide confirmación si están activos los respaldos automáticos al cerrar juegos."""
        try:
            _, _, al_cierre, juegos, _ = self._cargar_opciones_respaldos_automaticos()
        except Exception:
            al_cierre = False
            juegos = []

        if not al_cierre:
            return True

        if juegos:
            detalle = (
                "El respaldo automático al cerrar juegos está activado.\n\n"
                f"Hay {len(juegos)} juego(s) seleccionado(s) para este modo.\n\n"
                "Si cierras Arlequin SaveHub ahora, el programa no podrá "
                "detectar los cierres de los juegos ni realizar esos respaldos "
                "automáticos mientras esté cerrado.\n\n"
                "¿Quieres cerrar Arlequin SaveHub de todas formas?"
            )
        else:
            detalle = (
                "El respaldo automático al cerrar juegos está activado.\n\n"
                "No hay juegos seleccionados actualmente para este modo.\n\n"
                "¿Quieres cerrar Arlequin SaveHub de todas formas?"
            )

        try:
            return mb.askyesno("Respaldos automáticos", detalle, parent=self.root)
        except Exception:
            return True

    def _confirmar_cierre_si_subida_nube(self):
        """Pregunta antes de cerrar si hay una subida o descarga de Google Drive activa."""
        if getattr(self, "_cloud_download_active", False):
            try:
                return mb.askyesno(
                    "Descarga de Google Drive en curso",
                    "Hay una descarga de Google Drive en curso.\n\n"
                    "Si cierras ahora, no se modificará ningún backup y lo ya descargado "
                    "se aprovechará la próxima vez que descargues esa copia.\n\n"
                    "¿Quieres cerrar igualmente?",
                    parent=self.root,
                )
            except Exception:
                return True
        if not getattr(self, "_cloud_upload_active", False):
            return True
        try:
            return mb.askyesno(
                "Subida a Google Drive en curso",
                "Hay una subida a Google Drive en curso.\n\n"
                "Si cierras Arlequin SaveHub ahora, la subida quedará guardada "
                "para intentar reanudarla la próxima vez que abras el programa.\n\n"
                "¿Quieres cerrar igualmente?",
                parent=self.root,
            )
        except Exception:
            return True

    def _cerrar_ventanas_secundarias(self):
        """Libera y cierra todas las ventanas secundarias, incluidas las anidadas."""
        def recorrer(widget):
            try:
                hijos = list(widget.winfo_children())
            except Exception:
                hijos = []
            for hijo in hijos:
                recorrer(hijo)
                try:
                    if isinstance(hijo, tk.Toplevel):
                        try:
                            hijo.grab_release()
                        except Exception:
                            pass
                        try:
                            hijo.grab_set_global(False)
                        except Exception:
                            pass
                        try:
                            hijo.destroy()
                        except Exception:
                            pass
                except Exception:
                    pass

        try:
            # Es importante hacerlo ANTES de mostrar cualquier confirmación:
            # una ventana secundaria con grab_set() puede impedir que el
            # cuadro de confirmación del cierre reciba correctamente el foco.
            recorrer(self.root)
            try:
                self.root.grab_release()
            except Exception:
                pass
        except Exception:
            pass

    def _cerrar_ventana_principal(self):
        """Cierra ASH por completo aunque haya ventanas secundarias abiertas."""
        if self._cerrando_desde_tray:
            return

        # Primero quitamos cualquier Toplevel/modal abierto. Esto permite que
        # la X de la ventana principal y el "Cerrar ventana" de Windows
        # funcionen incluso con Opciones, Nube u otros diálogos abiertos.
        self._cerrar_ventanas_secundarias()

        if not self._confirmar_cierre_si_respaldos_al_cierre():
            return
        if not self._confirmar_cierre_si_subida_nube():
            return

        try:
            if self._tray_icon is not None:
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            self._automaticos_detenidos.set()
        except Exception:
            pass
        self.root.destroy()

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

    def _detectar_minimizado(self, _event=None):
        """Si la opción está activa, convierte la minimización normal en ocultación en la bandeja."""
        if self._minimizando_a_bandeja or getattr(self, "_cerrando_desde_tray", False):
            return
        if not getattr(self, "minimizar_en_bandeja", False):
            return

        def comprobar():
            try:
                if self._minimizando_a_bandeja or getattr(self, "_cerrando_desde_tray", False):
                    return
                if self.root.state() == "iconic":
                    self._minimizando_a_bandeja = True
                    if not self._iniciar_bandeja():
                        self._minimizando_a_bandeja = False
                        return
                    self.root.withdraw()
                    self._minimizando_a_bandeja = False
            except Exception as exc:
                self._minimizando_a_bandeja = False
                self._log("WARNING", "No se pudo enviar la ventana a la bandeja al minimizar: %s", exc)

        self.root.after_idle(comprobar)

    def abrir_link_donar(self):
        """Muestra la ventana de apoyo al proyecto con PayPal y GitHub Sponsors."""
        ventana_existente = getattr(self, "_ventana_donar", None)
        if ventana_existente is not None:
            try:
                if ventana_existente.winfo_exists():
                    ventana_existente.deiconify()
                    ventana_existente.lift()
                    ventana_existente.focus_force()
                    return
            except Exception:
                pass

        def abrir(url):
            try:
                webbrowser.open(url)
            except Exception as e:
                self._log("ERROR", "No se pudo abrir el enlace de Donar (%s): %s", url, e)

        bg = "#2c3e50"
        v = tk.Toplevel(self.root)
        self._ventana_donar = v
        v.title("Apoya Arlequin SaveHub")
        v.configure(bg=bg)
        v.resizable(False, False)
        v.transient(self.root)
        self.aplicar_icono_ventana(v)
        self.centrar_ventana(v, 420, 330)

        tk.Label(v, text="❤️ Apoya Arlequin SaveHub", font=("Arial", 15, "bold"),
                 fg="white", bg=bg).pack(pady=(22, 12))
        tk.Label(v, text="Arlequin es gratuito y open source.\n"
                         "Si te resulta útil, puedes ayudarme a seguir\n"
                         "mejorándolo y manteniendo la base de datos.",
                 font=("Arial", 10), fg="#ecf0f1", bg=bg, justify="center").pack(pady=(0, 18))

        tk.Button(v, text="💙 Apoyar con PayPal", command=lambda: abrir(DONAR_PAYPAL_URL),
                  bg="#0070ba", fg="white", activebackground="#005ea6", activeforeground="white",
                  font=("Arial", 11, "bold"), bd=0, relief="flat", width=24, pady=7,
                  cursor="hand2").pack(pady=4)
        tk.Button(v, text="⭐ GitHub Sponsors", command=lambda: abrir(DONAR_GITHUB_SPONSORS_URL),
                  bg="#6e5494", fg="white", activebackground="#5b4580", activeforeground="white",
                  font=("Arial", 11, "bold"), bd=0, relief="flat", width=24, pady=7,
                  cursor="hand2").pack(pady=4)

        tk.Label(v, text="Gracias por apoyar el proyecto ❤️", font=("Arial", 10, "italic"),
                 fg="#bdc3c7", bg=bg).pack(pady=(18, 0))
        v.bind("<Escape>", lambda _e: v.destroy())
        v.focus_force()

    def _cargar_opciones_inicio(self):
        """Lee las opciones de inicio guardadas en config.json."""
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                return (
                    bool(datos.get("iniciar_con_windows", False)),
                    bool(datos.get("iniciar_minimizado", False)),
                    bool(datos.get("minimizar_en_bandeja", False)),
                )
        except Exception as exc:
            self._log("ERROR", "No se pudieron leer las opciones de inicio: %s", exc)
        return False, False, False

    def _guardar_opciones_inicio(self, iniciar_windows, iniciar_minimizado, minimizar_en_bandeja):
        """Guarda las opciones de inicio sin modificar el resto de config.json."""
        try:
            return _actualizar_config({
                "iniciar_con_windows": bool(iniciar_windows),
                "iniciar_minimizado": bool(iniciar_minimizado),
                "minimizar_en_bandeja": bool(minimizar_en_bandeja),
            })
        except Exception as exc:
            self._log("ERROR", "No se pudieron guardar las opciones de inicio: %s", exc)
            return False

    def _comando_inicio_windows(self, iniciar_minimizado=False):
        """Construye el comando que Windows usará para iniciar Arlequin SaveHub."""
        if getattr(sys, "frozen", False):
            comando = f'"{os.path.abspath(sys.executable)}"'
        else:
            python_exe = sys.executable
            pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            if os.path.isfile(pythonw):
                python_exe = pythonw
            script = os.path.abspath(__file__)
            comando = f'"{python_exe}" "{script}"'

        if iniciar_minimizado:
            comando += " --minimized"
        return comando

    def _actualizar_inicio_windows(self, iniciar_windows, iniciar_minimizado):
        """Añade o elimina Arlequin SaveHub del inicio de Windows."""
        if not _ES_WINDOWS:
            return True

        try:
            clave_ruta = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                clave_ruta,
                0,
                winreg.KEY_SET_VALUE,
            ) as clave:
                if iniciar_windows:
                    winreg.SetValueEx(
                        clave,
                        "Arlequin SaveHub",
                        0,
                        winreg.REG_SZ,
                        self._comando_inicio_windows(iniciar_minimizado),
                    )
                else:
                    try:
                        winreg.DeleteValue(clave, "Arlequin SaveHub")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as exc:
            self._log("ERROR", "No se pudo actualizar el inicio de Windows: %s", exc)
            return False

    def _cargar_opciones_respaldos_automaticos(self):
        """Carga la configuración de respaldos automáticos desde config.json."""
        datos = {}
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
        except Exception as exc:
            self._log("ERROR", "No se pudo leer la configuración de respaldos automáticos: %s", exc)

        try:
            dias = max(1, int(datos.get("respaldo_automatico_dias", 7)))
        except Exception:
            dias = 7

        juegos = datos.get("respaldo_automatico_juegos", [])
        if not isinstance(juegos, list):
            juegos = []
        juegos = [str(x) for x in juegos if str(x).strip()]

        ultimos = datos.get("respaldo_automatico_ultimos", {})
        if not isinstance(ultimos, dict):
            ultimos = {}
        ultimos = {str(k): float(v) for k, v in ultimos.items() if str(k).strip()}

        return (
            bool(datos.get("respaldo_automatico_intervalo", False)),
            dias,
            bool(datos.get("respaldo_automatico_cierre", False)),
            juegos,
            ultimos,
        )

    def _guardar_opciones_respaldos_automaticos(self, intervalo, dias, al_cierre, juegos, ultimos=None, solo_idle=None, juegos_periodicos=None, juegos_cierre=None, juegos_periodicos_excluidos=None, juegos_cierre_excluidos=None, intervalo_valor=None, intervalo_unidad=None):
        """Guarda la configuración de respaldos automáticos sin tocar el resto de config.json."""
        datos = {}
        datos["respaldo_automatico_intervalo"] = bool(intervalo)
        datos["respaldo_automatico_dias"] = max(1, int(dias))
        datos["respaldo_automatico_cierre"] = bool(al_cierre)
        datos["respaldo_automatico_juegos"] = list(juegos or [])
        if juegos_periodicos is not None:
            datos["respaldo_automatico_juegos_periodicos"] = list(dict.fromkeys(juegos_periodicos))
        if juegos_cierre is not None:
            datos["respaldo_automatico_juegos_cierre"] = list(dict.fromkeys(juegos_cierre))
        if juegos_periodicos_excluidos is not None:
            datos["respaldo_automatico_juegos_periodicos_excluidos"] = list(dict.fromkeys(juegos_periodicos_excluidos))
        if juegos_cierre_excluidos is not None:
            datos["respaldo_automatico_juegos_cierre_excluidos"] = list(dict.fromkeys(juegos_cierre_excluidos))
        # Marca explícita de que el usuario ya ha configurado los modos de
        # exclusión. Si no existe, una instalación nueva debe incluir todos
        # los juegos por defecto, aunque haya restos de configuraciones
        # antiguas generadas por versiones previas.
        if juegos_periodicos_excluidos is not None or juegos_cierre_excluidos is not None:
            datos["respaldo_automatico_exclusiones_configuradas"] = True
        if intervalo_valor is not None:
            datos["respaldo_automatico_intervalo_valor"] = max(1, int(intervalo_valor))
        if intervalo_unidad is not None:
            datos["respaldo_automatico_unidad"] = str(intervalo_unidad)
        if ultimos is not None:
            datos["respaldo_automatico_ultimos"] = dict(ultimos)
        if solo_idle is not None:
            datos["respaldo_automatico_solo_idle"] = bool(solo_idle)

        try:
            return _actualizar_config(datos)
        except Exception as exc:
            self._log("ERROR", "No se pudo guardar la configuración de respaldos automáticos: %s", exc)
            return False

    def _cargar_intervalo_respaldo_automatico(self):
        """Carga el intervalo local en valor/unidad y lo convierte a segundos."""
        try:
            with open(M_CFG, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception:
            datos = {}
        try:
            unidad = str(datos.get("respaldo_automatico_unidad", "días") or "días")
            if unidad not in ("horas", "días", "semanas"):
                unidad = "días"
            if "respaldo_automatico_intervalo_valor" in datos:
                valor = max(1, int(datos.get("respaldo_automatico_intervalo_valor", 7)))
            else:
                valor = max(1, int(datos.get("respaldo_automatico_dias", 7)))
            factores = {"horas": 3600, "días": 86400, "semanas": 604800}
            return valor, unidad, valor * factores[unidad]
        except Exception:
            return 7, "días", 7 * 86400

    def _cargar_juegos_automaticos_por_modo(self):
        """Devuelve los juegos incluidos en cada modo.

        La configuración funciona por exclusión: activar un modo significa
        incluir todos los juegos detectados. Los botones "X juego(s) excluidos"
        almacenan únicamente las excepciones que el usuario ha quitado.
        Se conserva una migración transparente desde las versiones anteriores,
        que guardaban directamente la lista de juegos incluidos.
        """
        try:
            with open(M_CFG, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception:
            datos = {}

        disponibles = [str(j) for j, r in self.juegos.items() if r and str(j).strip()]
        disponibles_set = set(disponibles)

        exclusiones_configuradas = bool(datos.get("respaldo_automatico_exclusiones_configuradas", False))

        def cargar_modo(clave_excluidos, clave_incluidos, legado):
            # Si el usuario nunca ha configurado las exclusiones, todos los
            # juegos están incluidos por defecto. Esto también corrige restos
            # de configuraciones creadas por versiones anteriores.
            if not exclusiones_configuradas:
                return list(disponibles)

            # Formato nuevo: lista de exclusiones.
            if clave_excluidos in datos:
                excluidos = datos.get(clave_excluidos, [])
                if not isinstance(excluidos, list):
                    excluidos = []
                excluidos = {str(x) for x in excluidos if str(x).strip()}
                return [j for j in disponibles if j not in excluidos]

            # Migración del formato anterior: la lista representaba los
            # incluidos. Si estaba vacía, se interpreta como "todos", que es
            # el comportamiento nuevo solicitado.
            incluidos = datos.get(clave_incluidos, datos.get(legado, []))
            if not isinstance(incluidos, list):
                incluidos = []
            incluidos = {str(x) for x in incluidos if str(x).strip()}
            if not incluidos:
                return list(disponibles)
            return [j for j in disponibles if j in incluidos]

        periodicos = cargar_modo(
            "respaldo_automatico_juegos_periodicos_excluidos",
            "respaldo_automatico_juegos_periodicos",
            "respaldo_automatico_juegos",
        )
        cierre = cargar_modo(
            "respaldo_automatico_juegos_cierre_excluidos",
            "respaldo_automatico_juegos_cierre",
            "respaldo_automatico_juegos",
        )
        return (list(dict.fromkeys(periodicos)), list(dict.fromkeys(cierre)))

    def _detectar_cierre_anomalo_juego(self, nombre_juego, exe_detectado=None, ventana_segundos=45):
        """Comprueba si el cierre reciente del juego aparece como crash en Windows.

        Se consultan los eventos 1000/1001 de Application (Application Error /
        Windows Error Reporting) y se busca el ejecutable del juego. No se usa
        esta comprobación para bloquear backups manuales: solo protege el modo
        automático al cerrar. Si Windows no permite consultar el registro o no
        hay evidencia suficiente, devuelve ``None`` para que el cierre quede como
        indeterminado y no se afirme que fue un crash.
        """
        if not _ES_WINDOWS:
            return None

        exe_objetivo = (exe_detectado or "").strip().lower()
        if not exe_objetivo:
            installdir = (self.juegos_installdir or {}).get(nombre_juego, "")
            if installdir:
                if installdir not in self._exes_cache:
                    self._exes_cache[installdir] = _detectar_exes_candidatos(installdir)
                candidatos = self._exes_cache.get(installdir) or []
                if len(candidatos) == 1:
                    exe_objetivo = candidatos[0].lower()
        if not exe_objetivo:
            return None

        try:
            consulta = (
                '*[System[(EventID=1000 or EventID=1001) and '
                f'TimeCreated[timediff(@SystemTime) <= {int(max(10, ventana_segundos)) * 1000}]]]'
            )
            salida = subprocess.check_output(
                ["wevtutil", "qe", "Application", "/q:" + consulta,
                 "/f:xml", "/c:50"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stderr=subprocess.DEVNULL, timeout=8,
            )
            texto_xml = salida.decode("utf-8", errors="ignore")
            # wevtutil puede devolver varios documentos XML independientes,
            # cada uno con su propia declaración <?xml ...?>. Los extraemos
            # individualmente en lugar de envolverlos en otro XML.
            eventos_xml = re.findall(r"<Event\b.*?</Event>", texto_xml, flags=re.DOTALL | re.IGNORECASE)
        except Exception as exc:
            self._log("WARNING", "No se pudo consultar el registro de eventos para %s: %s", nombre_juego, exc)
            return None

        nombres_candidatos = {exe_objetivo}
        try:
            installdir = (self.juegos_installdir or {}).get(nombre_juego, "")
            for candidato in (self._exes_cache.get(installdir) or []):
                nombres_candidatos.add(str(candidato).lower())
        except Exception:
            pass

        for texto_evento in eventos_xml:
            try:
                evento = ET.fromstring(texto_evento)
            except Exception:
                continue
            event_id = None
            for elem in evento.iter():
                if elem.tag.endswith("EventID"):
                    event_id = (elem.text or "").strip()
                    break
            if event_id not in {"1000", "1001"}:
                continue
            datos = {}
            for elem in evento.iter():
                if not elem.tag.endswith("Data"):
                    continue
                nombre = (elem.attrib.get("Name") or "").strip().lower()
                valor = (elem.text or "").strip()
                if nombre and valor:
                    datos[nombre] = valor

            # Los nombres cambian ligeramente entre versiones de Windows.
            campos = [
                datos.get("appname", ""),
                datos.get("applicationname", ""),
                datos.get("faultingapplicationname", ""),
                datos.get("p1", ""),
                datos.get("applicationpath", ""),
                datos.get("faultingapplicationpath", ""),
            ]
            for valor in campos:
                base = os.path.basename(valor.replace("/", "\\")).strip().lower()
                if base in nombres_candidatos:
                    return {
                        "crash": True,
                        "evento": event_id,
                        "exe": base,
                    }

        return False

    def _mostrar_aviso_crash_detectado(self, nombre_juego, exe_detectado=None):
        """Informa al usuario de que el backup al cerrar se ha omitido por crash."""
        def mostrar():
            try:
                detalle = f"\n\nProceso detectado: {exe_detectado}" if exe_detectado else ""
                mb.showwarning(
                    "Crash detectado — backup protegido",
                    f'Arlequin SaveHub ha detectado un cierre anómalo de "{nombre_juego}".'
                    f"{detalle}\n\n"
                    "NO se ha creado el respaldo automático ni se ha subido ese save a la nube.\n\n"
                    "Se conserva el último respaldo conocido como válido para evitar sustituirlo "
                    "por un save que pueda haberse corrompido durante el crash.",
                    parent=self.root,
                )
            except Exception:
                pass
        try:
            self.root.after(0, mostrar)
        except Exception:
            pass

    def _crear_backup_emergencia_crash(self, nombre_juego, exe_detectado=None, evento=None):
        """Conserva una copia de emergencia del save tras un crash detectado.

        Esta copia NO sustituye al backup normal, NO se marca como backup
        válido y NO se sube automáticamente a la nube. Su objetivo es guardar
        exactamente lo que haya quedado en disco después del crash para poder
        inspeccionarlo o recuperarlo manualmente sin poner en riesgo el último
        backup sano.
        """
        try:
            origen = self.juegos.get(nombre_juego)
            if not origen:
                self._log("WARNING", "No se pudo crear backup de emergencia de %s: no hay ruta de save.", nombre_juego)
                return None

            origenes = [origen] if isinstance(origen, str) else list(origen)
            timestamp = self._formatear_fecha_es(time.time())
            raiz_emergencia = os.path.join(
                BKP, "Emergencias Crash", f"{self.limpiar_nombre_juego(nombre_juego)} [{timestamp}]"
            ).replace("\\", "/")
            os.makedirs(raiz_emergencia, exist_ok=True)

            copias = 0
            raices_validas = []
            for orig in origenes:
                if not orig:
                    continue
                ruta_real = orig if os.path.isabs(orig) else os.path.join(UP, orig)
                ruta_real = os.path.normpath(ruta_real).replace("\\", "/")
                valido, motivo = self._validar_origen_para_backup(ruta_real, nombre_juego)
                if not valido or not os.path.isdir(ruta_real):
                    self._log("WARNING", "Backup de emergencia omitido para %s en %s: %s", nombre_juego, ruta_real, motivo or "ruta no disponible")
                    continue
                if self._ruta_es_demasiado_amplia(ruta_real):
                    self._log("WARNING", "Backup de emergencia bloqueado para %s: ruta demasiado amplia (%s)", nombre_juego, ruta_real)
                    continue
                raices_validas.append(ruta_real)

            etiquetas = self._etiquetas_rutas_multiruta(raices_validas) if len(raices_validas) > 1 else {}
            for ruta_real in raices_validas:
                etiqueta = etiquetas.get(ruta_real) or os.path.basename(os.path.normpath(ruta_real)) or "Save"
                destino = os.path.join(raiz_emergencia, etiqueta).replace("\\", "/")
                shutil.copytree(ruta_real, destino, dirs_exist_ok=True)
                copias += 1

            if copias <= 0:
                shutil.rmtree(raiz_emergencia, ignore_errors=True)
                return None

            try:
                with open(os.path.join(raiz_emergencia, "ash_crash_emergency.json"), "w", encoding="utf-8") as f:
                    json.dump({
                        "game": self.limpiar_nombre_juego(nombre_juego),
                        "process": exe_detectado or "",
                        "windows_event": evento or "",
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                        "warning": "Copia de emergencia tras crash. No sustituye al ultimo backup valido y no se sube automaticamente a la nube."
                    }, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

            self._log("WARNING", "Backup de emergencia creado tras crash de %s: %s", nombre_juego, raiz_emergencia)
            return raiz_emergencia
        except Exception as exc:
            self._log("ERROR", "No se pudo crear el backup de emergencia de %s: %s", nombre_juego, exc, exc_info=True)
            return None

    def _avisar_resultado_automatico(self, motivo):
        """Aviso al terminar un respaldo automático, según Opciones
        (Nunca / Solo errores / Siempre)."""
        modo = self._cargar_opciones_generales()["avisos_automaticos"]
        res = getattr(self, "_ultimo_resultado_op", None) or {}
        # "Pospuesto porque el juego está abierto" no es un error: se reintenta solo.
        errores = [f for f in res.get("fallidas", []) if "pospuesto" not in str(f)]
        if modo == "Nunca" or (modo == "Solo errores" and not errores):
            return
        if errores:
            detalle = "\n".join(f"• {e}" for e in errores[:3])
            if len(errores) > 3:
                detalle += f"\n… y {len(errores) - 3} más (ver app.log)"
            self._notificar(f"Respaldo automático ({motivo}): {len(errores)} con problemas", detalle, error=True)
        elif res.get("total"):
            iguales = len(res.get("sin_cambios", []))
            nuevos = res.get("exitosas", 0) - iguales
            texto = f"{nuevos} copia(s) nueva(s)"
            if iguales:
                texto += f" · {iguales} sin cambios"
            self._notificar(f"Respaldo automático ({motivo}) completado", texto)

    def _programar_backup_automatico(self, juegos, motivo):
        """Lanza un backup automático sin bloquear la interfaz y sin duplicar operaciones."""
        if not juegos or getattr(self, "_backup_automatico_en_curso", False):
            return False
        juegos = [j for j in juegos if j in self.juegos and self.juegos.get(j)]
        if not juegos:
            return False

        self._backup_automatico_en_curso = True

        def trabajador():
            try:
                self._log("INFO", "Respaldo automático iniciado (%s): %s", motivo, ", ".join(juegos))
                self._ultimo_resultado_op = None
                exitosos = self.op(1, lista_forzada=juegos, automatico=True) or []
                if exitosos:
                    intervalo, dias, al_cierre, juegos_configurados, ultimos = self._cargar_opciones_respaldos_automaticos()
                    ahora = time.time()
                    for juego in exitosos:
                        ultimos[juego] = ahora
                    self._guardar_opciones_respaldos_automaticos(
                        intervalo, dias, al_cierre, juegos_configurados, ultimos
                    )
                # Si el respaldo local se ha disparado por cierre del juego y
                # está activada la subida de nube al cerrar, subimos el backup
                # recién creado aunque no esté activada la subida de nube tras
                # cada backup. Si ambas opciones están activadas, op() ya habrá
                # programado la subida y no la duplicamos.
                config_nube = self._cargar_config_nube()
                if motivo == "cierre del juego" and config_nube.get("al_cierre") and not config_nube.get("auto") and exitosos:
                    self._programar_subida_nube(exitosos, forzar=True)
                self._log("INFO", "Respaldo automático finalizado (%s): %s correcto(s).", motivo, len(exitosos))
                self._avisar_resultado_automatico(motivo)
            except Exception as exc:
                self._log("ERROR", "Error en respaldo automático (%s): %s", motivo, exc, exc_info=True)
                if self._cargar_opciones_generales()["avisos_automaticos"] != "Nunca":
                    self._notificar("Respaldo automático fallido", str(exc), error=True)
            finally:
                self._backup_automatico_en_curso = False

        # Usa el mismo candado que las operaciones manuales para que nunca se
        # ejecuten a la vez un escaneo/restauración/backup automático.
        self.ejecutar_en_hilo(trabajador)
        return True

    def _cargar_solo_idle_automatico(self):
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    return bool(json.load(f).get("respaldo_automatico_solo_idle", False))
        except Exception:
            pass
        return False

    def _monitorizar_respaldos_automaticos(self):
        """Supervisa intervalos y cierres de juegos en segundo plano.

        Para el modo "al cerrar", solo se dispara cuando se detecta una
        transición real de ABIERTO -> CERRADO. Si el programa arranca con el
        juego ya abierto, no hace un backup inmediato: espera a que se cierre.
        """
        intervalo, dias, al_cierre, juegos_configurados, ultimos = self._cargar_opciones_respaldos_automaticos()
        estado_anterior = {}

        while not getattr(self, "_automaticos_detenidos", threading.Event()).is_set():
            try:
                juegos_periodicos, juegos_cierre = self._cargar_juegos_automaticos_por_modo()
                intervalo, dias, al_cierre, _, ultimos = self._cargar_opciones_respaldos_automaticos()

                # El listado de juegos se construye tras el escaneo inicial.
                disponibles_periodicos = [j for j in juegos_periodicos if j in self.juegos and self.juegos.get(j)]
                disponibles_cierre = [j for j in juegos_cierre if j in self.juegos and self.juegos.get(j)]
                ahora = time.time()

                # Con OBS abierto (grabando, transmitiendo o solo preparado)
                # las tareas automáticas se aplazan para no competir por disco/CPU.
                pausar_automaticos_obs = _obs_esta_abierto_proceso()
                if pausar_automaticos_obs:
                    self._log("INFO", "Tareas automáticas aplazadas: OBS está abierto.")

                if al_cierre and disponibles_cierre and not pausar_automaticos_obs:
                    for juego in disponibles_cierre:
                        activo = bool(self._juego_parece_en_ejecucion(juego))
                        anterior = estado_anterior.get(juego)
                        estado_anterior[juego] = activo

                        if anterior is True and activo is False:
                            # IMPORTANTE: desaparecer del listado de procesos no
                            # significa necesariamente "cierre normal". Antes de
                            # copiar el save consultamos los eventos de Windows
                            # para evitar convertir un save potencialmente
                            # corrupto por un crash en el backup más reciente.
                            exe_detectado = None
                            try:
                                installdir = (self.juegos_installdir or {}).get(juego, "")
                                candidatos = self._exes_cache.get(installdir) or []
                                # No podemos obtener el nombre después de que el
                                # proceso haya desaparecido; si solo hay un .exe
                                # candidato, lo usamos para identificar el crash.
                                if len(candidatos) == 1:
                                    exe_detectado = candidatos[0]
                            except Exception:
                                pass

                            cierre_anomalo = self._detectar_cierre_anomalo_juego(
                                juego, exe_detectado=exe_detectado, ventana_segundos=45
                            )
                            if cierre_anomalo is True or (
                                isinstance(cierre_anomalo, dict) and cierre_anomalo.get("crash")
                            ):
                                evento = cierre_anomalo.get("evento") if isinstance(cierre_anomalo, dict) else None
                                exe_crash = cierre_anomalo.get("exe") if isinstance(cierre_anomalo, dict) else exe_detectado
                                self._log(
                                    "WARNING",
                                    "Crash detectado en %s (evento %s, proceso %s). "
                                    "Se omite el backup automático al cerrar y cualquier subida asociada.",
                                    juego, evento or "?", exe_crash or "?",
                                )
                                self._mostrar_aviso_crash_detectado(juego, exe_crash)
                                self._crear_backup_emergencia_crash(juego, exe_crash, evento)
                                continue

                            config_nube = self._cargar_config_nube()
                            if al_cierre:
                                # Solo llegamos aquí cuando Windows no ha dado
                                # evidencia de crash. En un cierre normal se
                                # puede crear el backup y, si corresponde, subirlo.
                                self._programar_backup_automatico([juego], "cierre del juego")
                            elif config_nube.get("al_cierre"):
                                # Aunque no se haya activado el backup local al
                                # cerrar, solo subimos la última copia conocida
                                # en un cierre que no haya sido identificado como crash.
                                self._programar_subida_nube([juego], forzar=True)

                if intervalo and disponibles_periodicos and not pausar_automaticos_obs:
                    _, _, periodo = self._cargar_intervalo_respaldo_automatico()
                    pendientes = []
                    for juego in disponibles_periodicos:
                        ultimo = float(ultimos.get(juego, 0) or 0)
                        if ultimo <= 0 or ahora - ultimo >= periodo:
                            # Si está abierto, se deja pendiente para una
                            # comprobación posterior en vez de interrumpir al usuario.
                            if self._juego_parece_en_ejecucion(juego):
                                continue
                            pendientes.append(juego)

                    if pendientes:
                        solo_idle = self._cargar_solo_idle_automatico()
                        if solo_idle and not self._pc_esta_inactivo(300):
                            self._log("INFO", "Respaldo periódico aplazado: el PC no está inactivo (Idle).")
                        else:
                            valor_int, unidad_int, _ = self._cargar_intervalo_respaldo_automatico()
                            self._programar_backup_automatico(pendientes, f"cada {valor_int} {unidad_int}")

                # Verificación semanal de las copias locales: solo con el PC
                # inactivo, sin OBS y sin otra verificación en marcha.
                generales = self._cargar_opciones_generales()
                if (generales["verificacion_semanal"] and not pausar_automaticos_obs
                        and not getattr(self, "_verificacion_auto_en_curso", False)
                        and ahora - generales["verificacion_ultima"] >= 7 * 86400
                        and self.backups_existentes is not None
                        and self._pc_esta_inactivo(300)):
                    self._verificacion_auto_en_curso = True

                    def verificar_semanal():
                        try:
                            self._log("INFO", "Verificación semanal automática de copias locales.")
                            self.verificar_backups(silencioso=True)
                        finally:
                            # Aunque falle, no se reintenta cada 5 s: toca la semana que viene.
                            try:
                                _actualizar_config({"opcion_verificacion_ultima": time.time()})
                            except Exception:
                                pass
                            self._verificacion_auto_en_curso = False

                    self.ejecutar_en_hilo(verificar_semanal)
            except Exception as exc:
                self._log("ERROR", "Error en el monitor de respaldos automáticos: %s", exc, exc_info=True)

            try:
                self._automaticos_detenidos.wait(5)
            except Exception:
                time.sleep(5)

    # ------------------------------------------------------------------
    #  GOOGLE DRIVE
    # ------------------------------------------------------------------
    def _ruta_cache_nube_configurada(self):
        """Devuelve la ruta de caché de nube guardada en config.json."""
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                ruta = str(datos.get("cloud_cache_dir", "") or "").strip()
                if ruta:
                    return os.path.abspath(os.path.expandvars(os.path.expanduser(ruta))).replace("\\", "/")
        except Exception:
            pass
        return os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "Google Drive").replace("\\", "/")

    def _aplicar_ruta_cache_nube(self, nueva_ruta=None, mover_existentes=False):
        """Aplica la carpeta de caché de nube y actualiza las rutas globales."""
        global GOOGLE_CLOUD_DIR, GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE
        global GOOGLE_UPLOAD_STATE_FILE, GOOGLE_CLOUD_MANIFEST_FILE, MANIFEST_ETAG_CACHE
        antigua = GOOGLE_CLOUD_DIR
        ruta = nueva_ruta or self._ruta_cache_nube_configurada()
        ruta = os.path.abspath(os.path.expandvars(os.path.expanduser(str(ruta)))).replace("\\", "/")
        if not ruta:
            ruta = os.path.join(APP_ARLEQUIN_SAVEHUB_DIR, "Google Drive").replace("\\", "/")
        os.makedirs(ruta, exist_ok=True)
        nombres = ("client_credentials.json", "token.json", "upload_state.json", "cloud_manifest.json", "ArlequinGameDB.etag")
        if mover_existentes and os.path.normcase(os.path.normpath(antigua)) != os.path.normcase(os.path.normpath(ruta)):
            for nombre in nombres:
                origen = os.path.join(antigua, nombre)
                destino = os.path.join(ruta, nombre)
                if os.path.isfile(origen) and not os.path.exists(destino):
                    try:
                        shutil.move(origen, destino)
                    except Exception as exc:
                        self._log("WARNING", "No se pudo mover la caché de nube %s: %s", nombre, exc)
        GOOGLE_CLOUD_DIR = ruta
        GOOGLE_CREDENTIALS_FILE = os.path.join(ruta, "client_credentials.json").replace("\\", "/")
        GOOGLE_TOKEN_FILE = os.path.join(ruta, "token.json").replace("\\", "/")
        GOOGLE_UPLOAD_STATE_FILE = os.path.join(ruta, "upload_state.json").replace("\\", "/")
        GOOGLE_CLOUD_MANIFEST_FILE = os.path.join(ruta, "cloud_manifest.json").replace("\\", "/")
        MANIFEST_ETAG_CACHE = os.path.join(ruta, "ArlequinGameDB.etag").replace("\\", "/")
        return ruta

    def _google_obtener_espacio_drive(self, creds):
        """Consulta uso/límite de almacenamiento de Google Drive."""
        _, _, datos = self._google_request_json(
            "GET",
            "https://www.googleapis.com/drive/v3/about?fields=user(displayName,emailAddress),storageQuota(limit,usage)",
            creds,
        )
        cuota = datos.get("storageQuota") or {}
        uso = int(cuota.get("usage", 0) or 0)
        limite = cuota.get("limit")
        if limite is None:
            return f"Espacio en Drive: {self._formatear_bytes(uso)} usados"
        limite = int(limite or 0)
        return f"Espacio en Drive: {self._formatear_bytes(uso)} usados de {self._formatear_bytes(limite)}"

    def _pc_esta_inactivo(self, segundos=300):
        """True si Windows lleva al menos `segundos` sin entrada de usuario."""
        if not _ES_WINDOWS:
            return False
        try:
            import ctypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return False
            ahora = ctypes.windll.kernel32.GetTickCount()
            inactivo_ms = (ahora - info.dwTime) & 0xFFFFFFFF
            return inactivo_ms >= int(segundos * 1000)
        except Exception:
            return False

    def _esperar_si_hash_debe_aplazarse(self, motivo="hash", segundos_idle=None):
        """Aplaza el trabajo SHA-256 hasta que el PC esté inactivo, si el usuario lo pide.

        El trabajo permanece en segundo plano: no bloquea la interfaz y evita que un
        escaneo criptográfico grande compita con el juego por CPU/disco durante una partida.
        """
        config = self._cargar_config_nube()
        if not config.get("hash_solo_idle", False):
            return True
        limite = int(segundos_idle or config.get("hash_idle_seconds", 300) or 300)
        limite = max(30, limite)
        if self._pc_esta_inactivo(limite):
            return True
        self._log("INFO", "SHA-256 aplazado (%s): esperando %d s de inactividad del PC.", motivo, limite)
        while not getattr(self, "_automaticos_detenidos", threading.Event()).is_set():
            if self._pc_esta_inactivo(limite):
                self._log("INFO", "PC inactivo: se reanuda SHA-256 (%s).", motivo)
                return True
            time.sleep(5)
        return False

    def _cloud_subida_bloqueada_por_protecciones(self, carpeta, nombre_juego, forzar=False):
        """Devuelve (bloqueada, motivo) antes de comprimir/subir una copia a la nube."""
        config = self._cargar_config_nube()
        if not forzar and config.get("obs_pause_streaming") and _obs_esta_abierto_proceso():
            return True, "OBS está abierto"
        if not forzar and config.get("anti_corrupcion"):
            # Compara el tamaño actual del backup con el último backup válido local.
            actual = self._folder_size_bytes(carpeta)
            anterior = None
            try:
                raiz = os.path.dirname(carpeta.rstrip("\\/"))
                candidatos = []
                for nombre in os.listdir(raiz):
                    ruta = os.path.join(raiz, nombre)
                    if os.path.isdir(ruta) and self._es_backup_historico_con_fecha(nombre):
                        candidatos.append(ruta)
                candidatos.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                if candidatos:
                    anterior = self._folder_size_bytes(candidatos[0])
            except Exception:
                anterior = None
            # Si no encontramos un histórico, usamos la metadata de la copia activa.
            if anterior is None:
                try:
                    with open(os.path.join(carpeta, BACKUP_METADATA_NAME), "r", encoding="utf-8") as f:
                        anterior = int((json.load(f) or {}).get("size_bytes", 0) or 0)
                except Exception:
                    anterior = None
            if anterior and actual >= 0:
                variacion = abs(actual - anterior) / float(anterior) * 100.0
                limite = float(config.get("anti_corrupcion_pct", 30) or 30)
                if variacion > limite:
                    return True, f"el tamaño ha variado un {variacion:.1f}% (límite {limite:.0f}%)"
        return False, ""

    def _pc_usa_red_medida(self):
        """Detección best-effort de red medida en Windows mediante NetworkInformation."""
        if not _ES_WINDOWS:
            return False
        try:
            ps = r"$ErrorActionPreference='SilentlyContinue'; Add-Type -AssemblyName System.Runtime.WindowsRuntime; $p=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile(); if($null -eq $p){exit 2}; $c=$p.GetConnectionCost(); if($c.NetworkCostType.ToString() -eq 'Unrestricted'){exit 0}else{exit 1}"
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.returncode == 1
        except Exception:
            return False

    def _cargar_config_nube(self):
        datos = {}
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
        except Exception:
            datos = {}
        max_copias = datos.get("cloud_max_copias", 5)
        try:
            # 0 = "Sin límite" (no se borra ninguna copia de Drive). Antes se
            # forzaba a un mínimo de 1 y "Sin límite" acababa borrando todas
            # las copias menos la última.
            max_copias = max(0, int(max_copias))
        except Exception:
            max_copias = 5
        limite_subida = datos.get("cloud_upload_limit_kbps", 0)
        try:
            limite_subida = max(0, int(limite_subida))
        except Exception:
            limite_subida = 0
        return {
            "auto": bool(datos.get("cloud_auto_upload", False)),
            "cuando": str(datos.get("cloud_upload_when", "Cada X días")),
            "dias_periodicos": max(1, int(datos.get("cloud_upload_periodic_days", 7) or 7)),
            "periodic_value": max(1, int(datos.get("cloud_upload_periodic_value", datos.get("cloud_upload_periodic_days", 7)) or 7)),
            "periodic_unit": str(datos.get("cloud_upload_periodic_unit", "días") or "días"),
            "al_cierre": bool(datos.get("cloud_upload_on_close", False)),
            "juegos_periodicos": list(datos.get("cloud_periodic_games", []) or []),
            "juegos_cierre": list(datos.get("cloud_close_games", []) or []),
            "juegos_periodicos_excluidos": list(datos.get("cloud_periodic_games_excluded", []) or []),
            "juegos_cierre_excluidos": list(datos.get("cloud_close_games_excluded", []) or []),
            "exclusiones_configuradas": bool(datos.get("cloud_exclusion_configured", False)),
            "max_copias": max_copias,
            "upload_limit_kbps": limite_subida,
            "no_subir_red_medida": bool(datos.get("cloud_no_upload_metered", False)),
            "compresion": str(datos.get("cloud_compression", "Rápido") or "Rápido"),
            "cache_dir": str(datos.get("cloud_cache_dir", "") or ""),
            "hash_solo_idle": bool(datos.get("hash_solo_idle", False)),
            "hash_idle_seconds": max(30, int(datos.get("hash_idle_seconds", 300) or 300)),
            "anti_corrupcion": bool(datos.get("cloud_anti_corruption", False)),
            "anti_corrupcion_pct": max(1, int(datos.get("cloud_anti_corruption_pct", 30) or 30)),
            "obs_pause_streaming": bool(datos.get("obs_pause_streaming", False)),
            "obs_host": str(datos.get("obs_host", "127.0.0.1") or "127.0.0.1"),
            "obs_port": max(1, int(datos.get("obs_port", 4455) or 4455)),
            "obs_password": str(datos.get("obs_password", "") or ""),
            "storage_text": str(datos.get("cloud_storage_text", "") or ""),
            "last_upload": str(datos.get("cloud_last_upload", "")),
            "account": str(datos.get("cloud_account", "")),
            "folder_id": str(datos.get("cloud_folder_id", "")),
            "manifest_folder_id": str(datos.get("cloud_manifest_folder_id", "")),
            "manifest_file_id": str(datos.get("cloud_manifest_file_id", "")),
            "manifest_last_sync": str(datos.get("cloud_manifest_last_sync", "")),
        }

    def _guardar_config_nube(self, **cambios):
        try:
            return _actualizar_config(cambios)
        except Exception as exc:
            self._log("ERROR", "No se pudo guardar la configuración de nube: %s", exc)
            return False

    def _cargar_manifest_nube_local(self):
        """Carga el índice local de copias que ASH conoce en Google Drive."""
        try:
            if os.path.isfile(GOOGLE_CLOUD_MANIFEST_FILE):
                with open(GOOGLE_CLOUD_MANIFEST_FILE, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                if isinstance(datos, dict) and isinstance(datos.get("backups"), dict):
                    return datos
        except Exception as exc:
            self._log("WARNING", "No se pudo cargar el manifiesto local de nube: %s", exc)
        return {"version": 1, "updated_at": "", "backups": {}}

    def _guardar_manifest_nube_local(self, manifest):
        try:
            manifest = dict(manifest or {})
            manifest.setdefault("version", 1)
            manifest.setdefault("backups", {})
            manifest["updated_at"] = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
            os.makedirs(os.path.dirname(GOOGLE_CLOUD_MANIFEST_FILE), exist_ok=True)
            temporal = GOOGLE_CLOUD_MANIFEST_FILE + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            os.replace(temporal, GOOGLE_CLOUD_MANIFEST_FILE)
            self.cloud_manifest = manifest
            return True
        except Exception as exc:
            self._log("WARNING", "No se pudo guardar el manifiesto local de nube: %s", exc)
            return False

    def _clave_nube_juego(self, nombre):
        return _norm(self.limpiar_nombre_juego(str(nombre)))

    def _google_hash_contenido_carpeta(self, carpeta, excluir=None):
        """Huella estable basada solo en el contenido de una carpeta."""
        tam, archivos, hashes, grandes = self._inventario_integridad(carpeta, excluir=excluir)
        base = {"files": archivos, "size_bytes": tam, "hash_algorithm": BACKUP_HASH_ALGORITHM,
                "file_hashes": hashes, "large_file_signatures": grandes}
        raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _google_hash_backup_carpeta(self, carpeta):
        """Genera una huella estable del contenido del backup.

        No es el hash del ZIP: representa el contenido validado por ash_backup.json.
        Sirve para saber si una copia local sigue siendo la misma que la de la nube
        sin tener que descargar el ZIP.
        """
        meta = {}
        ruta_meta = os.path.join(carpeta, BACKUP_METADATA_NAME)
        try:
            if os.path.isfile(ruta_meta):
                with open(ruta_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
        except Exception:
            meta = {}
        base = {
            "format": meta.get("format"),
            "game": meta.get("game"),
            "files": meta.get("files"),
            "size_bytes": meta.get("size_bytes"),
            "hash_algorithm": meta.get("hash_algorithm", BACKUP_HASH_ALGORITHM),
            "file_hashes": meta.get("file_hashes") or {},
            "large_file_signatures": meta.get("large_file_signatures") or {},
        }
        if not base["file_hashes"] and not base["large_file_signatures"]:
            self._esperar_si_hash_debe_aplazarse("fingerprint de backup")
            tam, archivos, hashes, grandes = self._inventario_integridad(carpeta)
            base["files"] = archivos
            base["size_bytes"] = tam
            base["file_hashes"] = hashes
            base["large_file_signatures"] = grandes
        raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _google_preparar_manifest_nube(self, creds):
        """Prepara ArlequinConfigNube.json dentro de la carpeta raíz de ASH en Drive."""
        # Desde beta14 no existe una carpeta separada de configuración en Drive.
        # El único manifiesto remoto vive directamente dentro de "Arlequin SaveHub".
        folder_id = self._google_preparar_carpeta_ash(creds)
        config = self._cargar_config_nube()
        file_id = str(config.get("manifest_file_id", "") or "")

        if file_id:
            try:
                url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?fields=id,name,trashed,parents"
                _, _, datos = self._google_request_json("GET", url, creds)
                if (datos.get("id") and not datos.get("trashed")
                        and folder_id in (datos.get("parents") or [])
                        and str(datos.get("name", "")) == GOOGLE_CLOUD_MANIFEST_NAME):
                    self._guardar_config_nube(cloud_manifest_folder_id=folder_id, cloud_manifest_file_id=file_id)
                    return folder_id, file_id
            except Exception:
                pass
            file_id = ""

        # Buscamos únicamente dentro de Arlequin SaveHub. No hacemos ninguna
        # migración ni búsqueda global de nombres antiguos: el usuario ya ha
        # eliminado la estructura anterior de Drive.
        url = "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode({
            "q": "name='" + GOOGLE_CLOUD_MANIFEST_NAME + "' and '" + folder_id + "' in parents and trashed=false",
            "spaces": "drive", "fields": "files(id,name,parents)", "pageSize": "10"
        })
        _, _, datos = self._google_request_json("GET", url, creds)
        archivos = datos.get("files", [])
        file_id = str(archivos[0].get("id", "")) if archivos else ""

        self._guardar_config_nube(cloud_manifest_folder_id=folder_id, cloud_manifest_file_id=file_id)
        return folder_id, file_id

    def _google_descargar_manifest_nube(self, creds, file_id):
        if not file_id:
            return None
        url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?alt=media"
        try:
            headers = self._google_headers(creds)
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=60) as resp:
                datos = json.loads(resp.read().decode("utf-8"))
            return datos if isinstance(datos, dict) and isinstance(datos.get("backups"), dict) else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def _google_subir_manifest_nube(self, creds, manifest, folder_id, file_id=""):
        contenido = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        if not file_id:
            meta = {"name": GOOGLE_CLOUD_MANIFEST_NAME, "mimeType": "application/json", "parents": [folder_id]}
            _, _, datos = self._google_request_json(
                "POST", "https://www.googleapis.com/drive/v3/files?fields=id,name", creds, meta
            )
            file_id = datos["id"]
            self._guardar_config_nube(cloud_manifest_folder_id=folder_id, cloud_manifest_file_id=file_id)
        headers = self._google_headers(creds)
        headers.update({"Content-Type": "application/json; charset=UTF-8", "Content-Length": str(len(contenido))})
        url = "https://www.googleapis.com/upload/drive/v3/files/" + urllib.parse.quote(file_id) + "?uploadType=media&fields=id,name,modifiedTime,size"
        req = urllib.request.Request(url, data=contenido, headers=headers, method="PATCH")
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            datos = json.loads(raw.decode("utf-8")) if raw else {}
        # Verificación explícita: no damos la sincronización por correcta hasta
        # comprobar que cloud_manifest.json pertenece realmente a la carpeta.
        verificar_url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?fields=id,name,parents,trashed"
        _, _, verificado = self._google_request_json("GET", verificar_url, creds)
        padres = [str(p) for p in (verificado.get("parents") or [])]
        if (not verificado.get("id") or verificado.get("trashed")
                or str(folder_id) not in padres):
            raise RuntimeError(
                "Google Drive creó/actualizó ArlequinConfigNube.json, pero no quedó dentro de "
                "la carpeta 'Arlequin SaveHub'."
            )
        return file_id, datos

    def _google_fusionar_manifestos(self, local, remoto):
        """Fusiona el índice local y el remoto usando la versión más reciente por entrada."""
        local = local if isinstance(local, dict) else {"version": 1, "updated_at": "", "backups": {}}
        remoto = remoto if isinstance(remoto, dict) else {"version": 1, "updated_at": "", "backups": {}}
        fusion = {"version": 1, "updated_at": "", "backups": {}}

        def fecha(valor):
            try:
                return datetime.strptime(str(valor), "%d-%m-%Y %H-%M-%S")
            except Exception:
                return datetime.min

        local_backups = local.get("backups") or {}
        remoto_backups = remoto.get("backups") or {}
        claves = set(remoto_backups.keys()) | set(local_backups.keys())
        local_mas_nuevo = fecha(local.get("updated_at", "")) >= fecha(remoto.get("updated_at", ""))

        for clave in claves:
            entrada_local = local_backups.get(clave)
            entrada_remota = remoto_backups.get(clave)
            if entrada_local is None:
                elegida = entrada_remota
            elif entrada_remota is None:
                elegida = entrada_local
            else:
                # Si el manifiesto local fue actualizado después, conserva su
                # lista de copias completa (incluido el efecto de la purga).
                elegida = entrada_local if local_mas_nuevo else entrada_remota
            if isinstance(elegida, dict):
                fusion["backups"][clave] = dict(elegida)

        # El manifiesto remoto puede ser más reciente aunque la marca local sea
        # igual; en ese caso conservamos su timestamp para que la siguiente
        # sincronización no vuelva a considerarlo antiguo.
        fusion["updated_at"] = max(
            str(local.get("updated_at", "")),
            str(remoto.get("updated_at", "")),
            key=lambda x: fecha(x),
        )
        return fusion

    def _google_sincronizar_manifest_nube(self, creds, mostrar_error=False):
        """Sincroniza el JSON local con Google Drive, evitando sincronizaciones simultáneas."""
        # Si otra tarea ya está sincronizando, esperamos a que termine en vez de
        # lanzar otra ronda de peticiones HTTP en paralelo. Esto es importante
        # cuando el usuario abre Nube y pulsa "Subir ahora" inmediatamente.
        with self._cloud_manifest_sync_lock:
            if self._cloud_manifest_sync_active:
                evento = self._cloud_manifest_sync_event
                esperar = True
            else:
                self._cloud_manifest_sync_active = True
                self._cloud_manifest_sync_event.clear()
                evento = self._cloud_manifest_sync_event
                esperar = False

        if esperar:
            evento.wait(timeout=180)
            return getattr(self, "cloud_manifest", None) or self._cargar_manifest_nube_local()

        try:
            folder_id, file_id = self._google_preparar_manifest_nube(creds)
            local = self._cargar_manifest_nube_local()
            remoto = self._google_descargar_manifest_nube(creds, file_id) if file_id else None
            if remoto is not None:
                manifest = self._google_fusionar_manifestos(local, remoto)
            else:
                manifest = local
            manifest["updated_at"] = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
            self._guardar_manifest_nube_local(manifest)
            file_id, datos_manifest = self._google_subir_manifest_nube(creds, manifest, folder_id, file_id)
            self._guardar_config_nube(
                cloud_manifest_folder_id=folder_id,
                cloud_manifest_file_id=file_id,
                cloud_manifest_last_sync=manifest["updated_at"],
                cloud_manifest_remote_modified_time=str((datos_manifest or {}).get("modifiedTime", "") or ""),
            )
            self.cloud_manifest = manifest
            self._cloud_manifest_sync_monotonic = time.monotonic()
            return manifest
        except Exception as exc:
            self._log("WARNING", "No se pudo sincronizar el manifiesto de nube: %s", exc, exc_info=True)
            if mostrar_error:
                self.root.after(0, lambda error_text=str(exc): mb.showerror(
                    "Nube", "No se pudo sincronizar el índice de copias de Google Drive.\n\n" + error_text,
                    parent=self.root
                ))
                raise RuntimeError(str(exc)) from exc
            return self._cargar_manifest_nube_local()
        finally:
            with self._cloud_manifest_sync_lock:
                self._cloud_manifest_sync_active = False
                self._cloud_manifest_sync_event.set()

    def _google_sincronizar_manifest_nube_en_segundo_plano(self, callback=None):
        """Actualiza el manifiesto al abrir Nube, sin bloquear la interfaz."""
        def trabajador():
            ok = False
            try:
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is not None:
                    self._google_sincronizar_manifest_nube(creds, mostrar_error=False)
                    ok = True
            except Exception as exc:
                self._log("WARNING", "No se pudo sincronizar Nube al abrirla: %s", exc, exc_info=True)
            if callback is not None:
                try:
                    self.root.after(0, lambda ok=ok: callback(ok))
                except Exception:
                    pass
        with self._cloud_manifest_sync_lock:
            if self._cloud_manifest_sync_active:
                # Ya hay una sincronización (por ejemplo, la del arranque).
                # No lanzamos otra petición; la ventana puede esperar a esa misma tarea.
                return False
        threading.Thread(target=trabajador, name="ASHCloudManifestOnOpen", daemon=True).start()
        return True

    def _google_sincronizar_manifest_nube_si_necesario(self, creds, mostrar_error=False, max_age=600.0):
        """Sincroniza el manifiesto solo si no se ha sincronizado recientemente.

        La sincronización completa con Drive implica varias peticiones HTTP.
        Para una comprobación de duplicados no es necesario repetirlas si el
        manifiesto acaba de actualizarse en esta misma sesión. La caché normal
        dura 10 minutos; las operaciones que necesitan información fresca
        pueden pasar max_age=0 para forzar una sincronización.
        """
        ultima = float(getattr(self, "_cloud_manifest_sync_monotonic", 0.0) or 0.0)
        if ultima and (time.monotonic() - ultima) < max_age:
            return getattr(self, "cloud_manifest", None) or self._cargar_manifest_nube_local()
        return self._google_sincronizar_manifest_nube(creds, mostrar_error=mostrar_error)

    def _google_manifest_remoto_sigue_igual(self, creds):
        """Comprueba con una sola petición ligera si ArlequinConfigNube.json cambió en Drive.

        No descarga el manifiesto ni analiza backups. Si el modifiedTime coincide
        con el último que conocemos, la caché local se considera válida.
        """
        config = self._cargar_config_nube()
        file_id = str(config.get("manifest_file_id", "") or "")
        conocido = str(config.get("cloud_manifest_remote_modified_time", "") or "")
        if not file_id or not conocido:
            return False
        try:
            url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?fields=id,name,modifiedTime,trashed,parents"
            _, _, datos = self._google_request_json("GET", url, creds)
            if (not datos.get("id") or datos.get("trashed")
                    or str(config.get("manifest_folder_id", "")) not in (datos.get("parents") or [])):
                return False
            remoto = str(datos.get("modifiedTime", "") or "")
            return bool(remoto and remoto == conocido)
        except Exception as exc:
            self._log("WARNING", "No se pudo comprobar rápidamente la fecha del manifiesto remoto: %s", exc)
            return False

    def _google_preparar_manifest_para_subida(self, creds, max_age=600.0):
        """Prepara el manifiesto para subir usando caché cuando es segura.

        1. Si la caché no caducó, hacemos solo una comprobación barata del
           modifiedTime del manifiesto remoto.
        2. Si sigue igual, reutilizamos el manifest local sin descargarlo ni
           fusionarlo de nuevo.
        3. Si cambió o la caché caducó, hacemos la sincronización completa.
        """
        ultima = float(getattr(self, "_cloud_manifest_sync_monotonic", 0.0) or 0.0)
        cache_valida = bool(ultima and (time.monotonic() - ultima) < max_age)
        if cache_valida and self._google_manifest_remoto_sigue_igual(creds):
            return getattr(self, "cloud_manifest", None) or self._cargar_manifest_nube_local()
        return self._google_sincronizar_manifest_nube(creds, mostrar_error=True)

    def _cloud_tiene_copia(self, nombre_juego):
        clave = self._clave_nube_juego(nombre_juego)
        entrada = (getattr(self, "cloud_manifest", {}) or {}).get("backups", {}).get(clave)
        return bool(entrada and entrada.get("copies"))

    def _cloud_hash_coincide(self, carpeta, nombre_juego):
        clave = self._clave_nube_juego(nombre_juego)
        entrada = (getattr(self, "cloud_manifest", {}) or {}).get("backups", {}).get(clave) or {}
        copias = entrada.get("copies") or []
        if not copias or not os.path.isdir(carpeta):
            return False
        try:
            local_hash = self._google_hash_backup_carpeta(carpeta)
        except Exception:
            return False
        return any(c.get("backup_fingerprint") == local_hash for c in copias if isinstance(c, dict))

    def _actualizar_indicadores_nube(self):
        """Actualiza solo el prefijo de nube de las filas ya mostradas."""
        if not hasattr(self, "box"):
            return
        cambios = []
        for clave in list(self.juegos.keys()):
            nuevo = self._reformatear_fila_estado(clave)
            if nuevo != clave:
                valor = self.juegos.pop(clave)
                self.juegos[nuevo] = valor
                for atributo in ("juegos_confianza", "juegos_evidencia", "juegos_installdir"):
                    diccionario = getattr(self, atributo, None)
                    if isinstance(diccionario, dict) and clave in diccionario:
                        diccionario[nuevo] = diccionario.pop(clave)
                cambios.append((clave, nuevo))
        if cambios:
            por_clave = dict(cambios)
            for idx in range(self.box.size()):
                actual = self.box.get(idx)
                nuevo = por_clave.get(actual)
                if nuevo is not None:
                    seleccionado = idx in self.box.curselection()
                    self.box.delete(idx)
                    self.box.insert(idx, nuevo)
                    if seleccionado:
                        self.box.selection_set(idx)

    def _google_drive_disponible(self):
        return InstalledAppFlow is not None and GoogleCredentials is not None and GoogleAuthRequest is not None

    def _google_headers(self, creds):
        if creds is None:
            raise RuntimeError("No hay credenciales de Google.")
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
            os.makedirs(os.path.dirname(GOOGLE_TOKEN_FILE), exist_ok=True)
            with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        if not creds.token:
            raise RuntimeError("Google no devolvió un token de acceso.")
        return {"Authorization": "Bearer " + creds.token}

    def _google_request_json(self, method, url, creds, body=None, headers=None):
        cabeceras = self._google_headers(creds)
        cabeceras.update(headers or {})
        datos = None
        if body is not None:
            datos = json.dumps(body, ensure_ascii=False).encode("utf-8")
            cabeceras.setdefault("Content-Type", "application/json; charset=UTF-8")
        req = urllib.request.Request(url, data=datos, headers=cabeceras, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                contenido = resp.read()
                return resp.status, resp.headers, json.loads(contenido.decode("utf-8")) if contenido else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                detalle = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                detalle = raw.decode("utf-8", errors="replace")
            raise RuntimeError(f"Google Drive HTTP {exc.code}: {detalle}") from exc

    def _google_obtener_credenciales(self, pedir_json=True):
        if not self._google_drive_disponible():
            raise RuntimeError(
                "Faltan las librerías de Google. Si ejecutas el .py, ASH intentará instalarlas automáticamente."
            )

        os.makedirs(GOOGLE_CLOUD_DIR, exist_ok=True)
        creds = None
        if os.path.exists(GOOGLE_TOKEN_FILE):
            try:
                creds = GoogleCredentials.from_authorized_user_file(
                    GOOGLE_TOKEN_FILE, [GOOGLE_DRIVE_SCOPE]
                )
            except Exception as exc:
                self._log("WARNING", "No se pudo cargar el token de Google: %s", exc)
                creds = None

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
                with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                return creds
            except Exception as exc:
                self._log("WARNING", "No se pudo renovar el token de Google: %s", exc)
                creds = None

        # Sin un token válido solo abrimos el inicio de sesión de Google si
        # el usuario lo ha pedido expresamente (botón "Conectar Google
        # Drive"). Las tareas en segundo plano (arranque, sincronización,
        # reanudar subidas...) no deben abrir el navegador por sorpresa ni
        # quedarse bloqueadas esperando a que alguien inicie sesión.
        if not pedir_json:
            return None

        # Las credenciales OAuth están integradas en ASH y se pasan
        # directamente a la librería, sin copiarlas a disco. Así, si algún
        # día cambia el client_id, todos los usuarios usan el nuevo.
        try:
            config_cliente = json.loads(GOOGLE_EMBEDDED_CLIENT_CONFIG)
        except Exception as exc:
            raise RuntimeError(f"No se pudieron preparar las credenciales de Google: {exc}") from exc
        try:
            if os.path.exists(GOOGLE_CREDENTIALS_FILE):
                os.remove(GOOGLE_CREDENTIALS_FILE)  # copia antigua de versiones previas
        except OSError:
            pass

        flow = InstalledAppFlow.from_client_config(config_cliente, [GOOGLE_DRIVE_SCOPE])
        creds = flow.run_local_server(
            host="localhost", port=0, access_type="offline", prompt="consent"
        )
        os.makedirs(os.path.dirname(GOOGLE_TOKEN_FILE), exist_ok=True)
        with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds

    def _google_about(self, creds):
        _, _, datos = self._google_request_json(
            "GET",
            "https://www.googleapis.com/drive/v3/about?fields=user(displayName,emailAddress)",
            creds,
        )
        return datos.get("user", {})

    def _google_buscar_carpeta(self, creds, nombre, parent_id=None):
        q = (
            "name='" + nombre.replace("'", "\\'") + "' "
            "and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        if parent_id:
            q += " and '" + parent_id + "' in parents"
        url = "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode({
            "q": q, "spaces": "drive", "fields": "files(id,name,parents)", "pageSize": "100"
        })
        _, _, datos = self._google_request_json("GET", url, creds)
        archivos = datos.get("files", [])
        return archivos[0]["id"] if archivos else None

    def _google_crear_carpeta(self, creds, nombre, parent_id=None):
        meta = {"name": nombre, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            meta["parents"] = [parent_id]
        _, _, datos = self._google_request_json(
            "POST", "https://www.googleapis.com/drive/v3/files?fields=id,name", creds, meta
        )
        return datos["id"]

    def _google_preparar_carpeta_ash(self, creds):
        config = self._cargar_config_nube()
        folder_id = config.get("folder_id", "")
        if folder_id:
            try:
                url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(folder_id) + "?fields=id,name,mimeType,trashed"
                _, _, datos = self._google_request_json("GET", url, creds)
                if datos.get("id") and not datos.get("trashed"):
                    return folder_id
            except Exception:
                pass
        folder_id = self._google_buscar_carpeta(creds, "Arlequin SaveHub")
        if not folder_id:
            folder_id = self._google_crear_carpeta(creds, "Arlequin SaveHub")
        self._guardar_config_nube(cloud_folder_id=folder_id)
        return folder_id

    def _google_zip_carpeta(self, carpeta, nombre_juego):
        if not os.path.isdir(carpeta):
            raise FileNotFoundError(carpeta)
        temporal = os.path.join(
            GOOGLE_CLOUD_DIR,
            f"{self._normalizar_nombre_ruta(nombre_juego)[:80] or 'backup'}_{uuid.uuid4().hex[:8]}.zip",
        )
        config = self._cargar_config_nube()
        compresion = str(config.get("compresion", "Rápido") or "Rápido").lower()
        if compresion.startswith("máx") or compresion.startswith("max"):
            nivel = 9
        elif compresion.startswith("equ"):
            nivel = 6
        else:
            nivel = 1
        with zipfile.ZipFile(temporal, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=nivel, allowZip64=True) as zf:
            base = os.path.dirname(carpeta.rstrip("\\/"))
            for raiz, _, archivos in os.walk(carpeta):
                for nombre in archivos:
                    ruta = os.path.join(raiz, nombre)
                    if os.path.abspath(ruta) == os.path.abspath(temporal):
                        continue
                    zf.write(ruta, os.path.relpath(ruta, base))
        return temporal

    def _google_sha256(self, ruta):
        self._esperar_si_hash_debe_aplazarse("SHA-256 del ZIP")
        return _sha256_archivo(ruta)

    def _google_cargar_estado_subida(self):
        try:
            if os.path.exists(GOOGLE_UPLOAD_STATE_FILE):
                with open(GOOGLE_UPLOAD_STATE_FILE, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                return datos if isinstance(datos, dict) else {}
        except Exception:
            pass
        return {}

    def _google_guardar_estado_subida(self, datos):
        os.makedirs(os.path.dirname(GOOGLE_UPLOAD_STATE_FILE), exist_ok=True)
        tmp = GOOGLE_UPLOAD_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, GOOGLE_UPLOAD_STATE_FILE)

    def _google_borrar_estado_subida(self):
        try:
            os.remove(GOOGLE_UPLOAD_STATE_FILE)
        except OSError:
            pass

    def _google_iniciar_sesion_reanudable(self, creds, ruta, nombre, parent_id):
        size = os.path.getsize(ruta)
        meta = {"name": nombre, "parents": [parent_id], "mimeType": "application/zip"}
        headers = self._google_headers(creds)
        headers.update({
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "application/zip",
            "X-Upload-Content-Length": str(size),
        })
        req = urllib.request.Request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
            data=json.dumps(meta).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            session_url = resp.headers.get("Location")
        if not session_url:
            raise RuntimeError("Google no devolvió la URL de sesión reanudable.")
        return session_url

    def _google_consultar_sesion(self, creds, session_url, size):
        headers = self._google_headers(creds)
        headers["Content-Range"] = f"bytes */{size}"
        req = urllib.request.Request(session_url, data=b"", headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                return resp.status, resp.headers, json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code == 308:
                return 308, exc.headers, {}
            if exc.code == 404:
                return 404, exc.headers, {}
            raise

    def _google_subir_reanudable(self, creds, ruta, nombre, parent_id, game_name="", backup_fingerprint="", content_fingerprint=""):
        size = os.path.getsize(ruta)
        sha = self._google_sha256(ruta)
        estado = self._google_cargar_estado_subida()
        valido_estado = (
            estado.get("path") == os.path.abspath(ruta)
            and int(estado.get("size", -1)) == size
            and estado.get("sha256") == sha
            and estado.get("session_url")
            and estado.get("name") == nombre
            and estado.get("parent_id") == parent_id
        )
        session_url = estado.get("session_url") if valido_estado else None
        offset = int(estado.get("offset", 0) or 0) if valido_estado else 0

        if session_url:
            try:
                status, headers, datos = self._google_consultar_sesion(creds, session_url, size)
                if status in (200, 201):
                    self._google_borrar_estado_subida()
                    return datos
                if status == 308:
                    rango = headers.get("Range", "")
                    m = re.search(r"(\d+)-(\d+)", rango)
                    offset = int(m.group(2)) + 1 if m else offset
                elif status == 404:
                    session_url = None
            except Exception as exc:
                self._log("WARNING", "No se pudo consultar la sesión reanudable: %s", exc)
                # Conservamos la sesión para poder reintentarlo en otro momento.

        if not session_url:
            session_url = self._google_iniciar_sesion_reanudable(creds, ruta, nombre, parent_id)
            offset = 0
            self._google_guardar_estado_subida({
                "path": os.path.abspath(ruta), "size": size, "sha256": sha,
                "session_url": session_url, "offset": 0,
                "name": nombre, "parent_id": parent_id, "game": game_name, "backup_fingerprint": backup_fingerprint, "content_fingerprint": content_fingerprint,
            })

        chunk_size = 8 * 1024 * 1024
        with open(ruta, "rb") as f:
            f.seek(offset)
            while offset < size:
                bloque = f.read(min(chunk_size, size - offset))
                if not bloque:
                    break
                fin = offset + len(bloque) - 1
                headers = self._google_headers(creds)
                headers.update({
                    "Content-Length": str(len(bloque)),
                    "Content-Range": f"bytes {offset}-{fin}/{size}",
                    "Content-Type": "application/zip",
                })
                # Persistimos el estado ANTES de enviar cada fragmento. Si
                # ASH se cierra mientras la petición está en curso, al volver
                # a abrirlo Google podrá decirnos mediante Range qué bytes
                # llegaron realmente y podremos continuar desde ahí.
                self._google_guardar_estado_subida({
                    "path": os.path.abspath(ruta), "size": size, "sha256": sha,
                    "session_url": session_url, "offset": offset,
                    "name": nombre, "parent_id": parent_id, "game": game_name, "backup_fingerprint": backup_fingerprint, "content_fingerprint": content_fingerprint,
                })
                req = urllib.request.Request(session_url, data=bloque, headers=headers, method="PUT")
                inicio_envio = time.monotonic()
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        raw = resp.read()
                        if resp.status in (200, 201):
                            datos = json.loads(raw.decode("utf-8")) if raw else {}
                            self._google_borrar_estado_subida()
                            return datos
                        if resp.status == 308:
                            rango = resp.headers.get("Range", "")
                            m = re.search(r"(\d+)-(\d+)", rango)
                            offset = int(m.group(2)) + 1 if m else fin + 1
                            self._google_guardar_estado_subida({
                                "path": os.path.abspath(ruta), "size": size, "sha256": sha,
                                "session_url": session_url, "offset": offset,
                                "name": nombre, "parent_id": parent_id, "game": game_name, "backup_fingerprint": backup_fingerprint, "content_fingerprint": content_fingerprint,
                            })
                    config_limite = self._cargar_config_nube()
                    limite_kbps = int(config_limite.get("upload_limit_kbps", 0) or 0)
                    if limite_kbps > 0 and offset < size:
                        objetivo = len(bloque) / (limite_kbps * 1024.0)
                        transcurrido = time.monotonic() - inicio_envio
                        espera = max(0.0, objetivo - transcurrido)
                        if espera > 0:
                            time.sleep(espera)
                except urllib.error.HTTPError as exc:
                    if exc.code == 308:
                        rango = exc.headers.get("Range", "")
                        m = re.search(r"(\d+)-(\d+)", rango)
                        offset = int(m.group(2)) + 1 if m else fin + 1
                        self._google_guardar_estado_subida({
                            "path": os.path.abspath(ruta), "size": size, "sha256": sha,
                            "session_url": session_url, "offset": offset,
                            "name": nombre, "parent_id": parent_id, "game": game_name, "backup_fingerprint": backup_fingerprint, "content_fingerprint": content_fingerprint,
                        })
                    elif exc.code in (404, 408, 429, 500, 502, 503, 504):
                        self._google_guardar_estado_subida({
                            "path": os.path.abspath(ruta), "size": size, "sha256": sha,
                            "session_url": session_url, "offset": offset,
                            "name": nombre, "parent_id": parent_id, "game": game_name, "backup_fingerprint": backup_fingerprint, "content_fingerprint": content_fingerprint,
                        })
                        raise RuntimeError(f"Carga interrumpida por Google (HTTP {exc.code}).") from exc
                    else:
                        raw = exc.read()
                        detalle = raw.decode("utf-8", errors="replace")
                        raise RuntimeError(f"Google Drive HTTP {exc.code}: {detalle}") from exc
                except Exception:
                    self._google_guardar_estado_subida({
                        "path": os.path.abspath(ruta), "size": size, "sha256": sha,
                        "session_url": session_url, "offset": offset,
                        "name": nombre, "parent_id": parent_id, "game": game_name, "backup_fingerprint": backup_fingerprint, "content_fingerprint": content_fingerprint,
                    })
                    raise

        raise RuntimeError("La carga reanudable terminó sin confirmación de Google.")

    def _google_listar_subidas_juego(self, creds, parent_id):
        q = "'" + parent_id + "' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"
        url = "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode({
            "q": q, "spaces": "drive", "orderBy": "createdTime desc",
            "fields": "files(id,name,createdTime,size)", "pageSize": "100"
        })
        _, _, datos = self._google_request_json("GET", url, creds)
        return datos.get("files", [])

    def _google_subir_backup_carpeta(self, creds, carpeta, nombre_juego, parent_id, zip_preparado=None):
        # El ZIP temporal puede haberse preparado en segundo plano al abrir
        # la ventana Nube. Si existe, se reutiliza para no volver a comprimir.
        # Solo se elimina después de que Google confirme la subida completa.
        zip_path = zip_preparado or self._google_zip_carpeta(carpeta, nombre_juego)
        completado = False
        try:
            marca = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
            nombre = f"{self._normalizar_nombre_ruta(nombre_juego)[:80] or 'Backup'} - {marca}.zip"
            zip_sha256 = self._google_sha256(zip_path)
            backup_fingerprint = self._google_hash_backup_carpeta(carpeta)
            content_fingerprint = self._google_hash_contenido_carpeta(carpeta)
            datos = self._google_subir_reanudable(
                creds, zip_path, nombre, parent_id, nombre_juego, backup_fingerprint, content_fingerprint
            )
            if isinstance(datos, dict):
                datos["_ash_zip_sha256"] = zip_sha256
                datos["_ash_backup_fingerprint"] = backup_fingerprint
                datos["_ash_content_fingerprint"] = content_fingerprint
            completado = True
            return datos
        finally:
            if completado:
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
                with self._cloud_prepared_lock:
                    for clave, info in list(self._cloud_prepared_zips.items()):
                        if info.get("zip_path") == zip_path:
                            self._cloud_prepared_zips.pop(clave, None)

    def _google_preparar_zips_nube(self):
        """Prepara en segundo plano los ZIP de los backups que podrían subirse.

        Primero calcula fingerprints para evitar comprimir backups que ya están
        en Drive. Los ZIP preparados se mantienen solo mientras resulten útiles
        para una subida iniciada desde la ventana Nube.
        """
        try:
            creds = self._google_obtener_credenciales(pedir_json=False)
            if creds is None:
                return
            root_id = self._google_preparar_carpeta_ash(creds)
            self._google_sincronizar_manifest_nube(creds, mostrar_error=False)
            manifest_actual = self._cargar_manifest_nube_local()
            candidatos = []
            for raiz, dirs, _ in os.walk(self.dest):
                for d in dirs:
                    if self._es_backup_historico_con_fecha(d):
                        continue
                    ruta = os.path.join(raiz, d)
                    if os.path.isfile(os.path.join(ruta, BACKUP_METADATA_NAME)):
                        candidatos.append((d, ruta))
            vistos = set()
            candidatos = [(n, p) for n, p in candidatos if not (os.path.normcase(os.path.normpath(p)) in vistos or vistos.add(os.path.normcase(os.path.normpath(p))))]
            for nombre_juego, carpeta in candidatos:
                clave = self._clave_nube_juego(nombre_juego)
                with self._cloud_prepared_lock:
                    info_existente = self._cloud_prepared_zips.get(clave)
                    if info_existente and info_existente.get("path") == os.path.abspath(carpeta):
                        continue
                entrada_actual = ((manifest_actual.get("backups") or {}).get(clave) or {})
                copias_actuales = [c for c in (entrada_actual.get("copies") or []) if isinstance(c, dict)]

                # Comprobación rápida: primero usamos el fingerprint derivado de
                # ash_backup.json, sin volver a hashear todos los archivos.
                huella_legacy = self._google_hash_backup_carpeta(carpeta)
                copia_igual = any(c.get("backup_fingerprint") == huella_legacy for c in copias_actuales)
                if copia_igual:
                    continue

                # Solo en los casos que no coinciden hacemos la comprobación
                # completa del contenido antes de preparar un ZIP.
                contenido_actual = self._google_hash_contenido_carpeta(carpeta)
                copia_igual = any(c.get("content_fingerprint") == contenido_actual for c in copias_actuales)
                if copia_igual:
                    continue
                # Si hay una preparación previa en curso para este juego, no
                # lanzamos otra; el upload esperará a la misma preparación.
                with self._cloud_prepared_lock:
                    info = self._cloud_prepared_zips.get(clave)
                    if info is not None:
                        continue
                    evento = threading.Event()
                    self._cloud_prepared_zips[clave] = {
                        "event": evento, "path": os.path.abspath(carpeta),
                        "zip_path": "", "content_fingerprint": contenido_actual,
                        "backup_fingerprint": huella_legacy, "error": None,
                        "discard": False,
                        "compression": str(self._cargar_config_nube().get("compresion", "Rápido")),
                    }
                try:
                    zip_path = self._google_zip_carpeta(carpeta, nombre_juego)
                    with self._cloud_prepared_lock:
                        info = self._cloud_prepared_zips.get(clave)
                        if info is not None:
                            if info.get("discard"):
                                try:
                                    os.remove(zip_path)
                                except OSError:
                                    pass
                                self._cloud_prepared_zips.pop(clave, None)
                            else:
                                info["zip_path"] = zip_path
                                info["event"].set()
                except Exception as exc:
                    with self._cloud_prepared_lock:
                        info = self._cloud_prepared_zips.get(clave)
                        if info is not None:
                            info["error"] = str(exc)
                            info["event"].set()
                            self._cloud_prepared_zips.pop(clave, None)
                    self._log("WARNING", "No se pudo preparar ZIP en segundo plano para %s: %s", nombre_juego, exc)
        except Exception as exc:
            self._log("WARNING", "No se pudo preparar la caché de ZIPs de nube: %s", exc, exc_info=True)

    def _google_obtener_zip_preparado(self, carpeta, nombre_juego):
        """Devuelve un ZIP preparado, esperando si ya se estaba generando."""
        clave = self._clave_nube_juego(nombre_juego)
        ruta_abs = os.path.abspath(carpeta)
        with self._cloud_prepared_lock:
            info = self._cloud_prepared_zips.get(clave)
            if info is None or info.get("path") != ruta_abs:
                evento = threading.Event()
                info = {"event": evento, "path": ruta_abs, "zip_path": "",
                        "content_fingerprint": "", "backup_fingerprint": "",
                        "error": None, "discard": False, "compression": str(self._cargar_config_nube().get("compresion", "Rápido"))}
                self._cloud_prepared_zips[clave] = info
                creador = True
            else:
                creador = False
            evento = info["event"]
        if creador:
            try:
                zip_path = self._google_zip_carpeta(carpeta, nombre_juego)
                with self._cloud_prepared_lock:
                    info = self._cloud_prepared_zips.get(clave)
                    if info and not info.get("discard"):
                        info["zip_path"] = zip_path
                        info["event"].set()
                    else:
                        try:
                            os.remove(zip_path)
                        except OSError:
                            pass
                        raise RuntimeError("La preparación del ZIP fue cancelada.")
            except Exception as exc:
                with self._cloud_prepared_lock:
                    info = self._cloud_prepared_zips.get(clave)
                    if info:
                        info["error"] = str(exc)
                        info["event"].set()
                raise
        else:
            evento.wait()
        with self._cloud_prepared_lock:
            info = self._cloud_prepared_zips.get(clave)
            if not info:
                raise RuntimeError("No quedó disponible el ZIP preparado para la nube.")
            if info.get("error"):
                raise RuntimeError(info["error"])
            zip_path = info.get("zip_path")
            if not zip_path or not os.path.isfile(zip_path):
                raise RuntimeError("El ZIP preparado para la nube ya no está disponible.")
            huella_preparada = str(info.get("content_fingerprint", ""))
            compresion_preparada = str(info.get("compression", "Rápido"))

        compresion_actual = str(self._cargar_config_nube().get("compresion", "Rápido"))
        if compresion_preparada != compresion_actual:
            with self._cloud_prepared_lock:
                info = self._cloud_prepared_zips.pop(clave, None)
            if info:
                viejo_zip = info.get("zip_path")
                if viejo_zip:
                    try:
                        os.remove(viejo_zip)
                    except OSError:
                        pass
            return self._google_obtener_zip_preparado(carpeta, nombre_juego)

        # El save puede haber cambiado mientras el ZIP se preparaba. En ese
        # caso no reutilizamos una instantánea antigua: la descartamos y
        # volvemos a preparar el ZIP con el contenido actual.
        if huella_preparada:
            huella_actual = self._google_hash_contenido_carpeta(carpeta)
            if huella_actual != huella_preparada:
                with self._cloud_prepared_lock:
                    info = self._cloud_prepared_zips.pop(clave, None)
                if info:
                    viejo_zip = info.get("zip_path")
                    if viejo_zip:
                        try:
                            os.remove(viejo_zip)
                        except OSError:
                            pass
                return self._google_obtener_zip_preparado(carpeta, nombre_juego)
        return zip_path

    def _google_descartar_zips_preparados(self):
        """Descarta los ZIP preparados cuando el usuario cierra Nube sin subir."""
        with self._cloud_prepared_lock:
            items = list(self._cloud_prepared_zips.items())
            for clave, info in items:
                info["discard"] = True
                zip_path = info.get("zip_path")
                if zip_path:
                    try:
                        os.remove(zip_path)
                    except OSError:
                        pass
                    info["zip_path"] = ""
                # Si todavía está comprimiendo, el worker verá discard=True y
                # eliminará el ZIP justo cuando termine.
                if info.get("event") and info["event"].is_set():
                    self._cloud_prepared_zips.pop(clave, None)

    def _google_purgar_copias_remotas(self, creds, parent_id, max_copias):
        archivos = self._google_listar_subidas_juego(creds, parent_id)
        if max_copias <= 0 or len(archivos) <= max_copias:
            return
        for archivo in archivos[max_copias:]:
            try:
                self._google_request_json(
                    "DELETE",
                    "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(archivo["id"]),
                    creds,
                )
            except Exception as exc:
                self._log("WARNING", "No se pudo eliminar copia remota %s: %s", archivo.get("name"), exc)

    # -- DESCARGA DE BACKUPS DESDE GOOGLE DRIVE -----------------------------
    #
    # Flujo de cada juego (todas las comprobaciones deben pasar; si una falla,
    # no se toca NADA de la carpeta de backups local):
    #   1. Metadatos de Drive: el archivo existe, no está en la papelera y se
    #      conoce su tamaño y MD5.
    #   2. Espacio libre suficiente para el ZIP.
    #   3. Descarga a un .part (reanudable) calculando SHA-256 y MD5 a la vez.
    #   4. Tamaño == Drive, MD5 == Drive y SHA-256 == el registrado al subir.
    #   5. ZIP seguro: sin rutas absolutas ni "..", sin enlaces simbólicos,
    #      sin nombres duplicados, sin ratios de compresión sospechosos y CRC
    #      correcto en todos los archivos (testzip).
    #   6. Espacio libre suficiente para el contenido descomprimido.
    #   7. Extracción a una carpeta temporal en el MISMO disco que el destino.
    #   8. Integridad con ash_backup.json (SHA-256 de cada archivo, número de
    #      archivos y tamaño total) y huella igual a la registrada en la nube.
    #   9. Solo entonces: la copia local actual pasa a histórico con fecha y la
    #      descargada ocupa su lugar (rename en el mismo disco). Si algo falla
    #      al colocarla, se devuelve la copia anterior a su sitio.
    #
    # La descarga NO restaura nada en la carpeta del juego: deja la copia en
    # "Backups" para que el usuario la restaure con el flujo normal (vista
    # previa, comprobación de juego abierto, archivado de la carpeta actual).

    NUBE_CARPETA_SIN_UBICACION = "Descargados de la nube"
    NUBE_ZIP_MAX_ARCHIVOS = 200_000
    NUBE_ZIP_MAX_RATIO = 1000  # un save real nunca se comprime 1000:1

    def _ruta_relativa_segura(self, rel):
        """Devuelve partes seguras de una ruta relativa o None si no lo es."""
        rel = str(rel or "").replace("\\", "/").strip()
        if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
            return None
        partes = [p for p in rel.split("/") if p not in ("", ".")]
        if not partes or any(p == ".." for p in partes):
            return None
        return partes

    def _ruta_backup_local_para_juego_nube(self, nombre_juego, entrada=None):
        """Decide dónde debe quedar en este PC el backup descargado de un juego.

        Prioridad:
          1. El juego está detectado en este PC: la misma carpeta que usaría un
             backup normal, para que "Restaurar" lo encuentre directamente.
          2. La ubicación relativa que se registró al subirlo (local_rel).
          3. "<Backups>/Descargados de la nube/<Juego>".
        Devuelve (ruta, origen) con origen en {"detectado", "registrado", "generico"}.
        """
        nombre_limpio = self.limpiar_nombre_juego(nombre_juego)
        clave_buscada = _norm(nombre_limpio)
        for clave, origen in list((self.juegos or {}).items()):
            if not origen or _norm(self.limpiar_nombre_juego(clave)) != clave_buscada:
                continue
            origenes = [origen] if isinstance(origen, str) else list(origen)
            try:
                raices = self._raices_pc_unicas(origenes, nombre_limpio)
                if len(raices) > 1:
                    return self._backup_game_root_multiruta(nombre_limpio), "detectado"
                for orig in origenes:
                    ruta_real = orig if os.path.isabs(orig) else os.path.join(UP, orig)
                    return self._backup_game_root(ruta_real, nombre_limpio), "detectado"
            except Exception as exc:
                self._log("WARNING", "No se pudo calcular la carpeta de backup de %s: %s", nombre_limpio, exc)
            break

        partes = self._ruta_relativa_segura((entrada or {}).get("local_rel"))
        if partes:
            return os.path.join(self.dest, *partes).replace("\\", "/"), "registrado"

        carpeta = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre_limpio).strip(" .") or "Juego"
        return os.path.join(self.dest, self.NUBE_CARPETA_SIN_UBICACION, carpeta).replace("\\", "/"), "generico"

    def _huella_backup_local_rapida(self, carpeta):
        """Huella del backup local SOLO si tiene ash_backup.json (lectura rápida).

        Sin metadata devolvería un hash completo de todos los archivos, que
        puede ser lento; en ese caso se devuelve "" (estado desconocido).
        """
        if not carpeta or not os.path.isfile(os.path.join(carpeta, BACKUP_METADATA_NAME)):
            return ""
        try:
            return self._google_hash_backup_carpeta(carpeta)
        except Exception:
            return ""

    def _google_copias_ordenadas(self, entrada):
        copias = [c for c in ((entrada or {}).get("copies") or []) if isinstance(c, dict) and c.get("id")]
        copias.sort(key=lambda c: str(c.get("createdTime", "")), reverse=True)
        return copias

    def _fecha_drive_a_local(self, texto, formato="%d/%m/%Y %H:%M"):
        try:
            instante = datetime.fromisoformat(str(texto).replace("Z", "+00:00")).astimezone()
            return instante.strftime(formato), instante.timestamp()
        except Exception:
            return "", None

    def _google_listar_backups_para_descarga(self, creds):
        """Filas para la ventana de descarga: una por juego, con su copia más reciente."""
        manifest = self._google_sincronizar_manifest_nube_si_necesario(creds, mostrar_error=False, max_age=600.0)
        manifest = manifest or self._cargar_manifest_nube_local()
        filas = []
        for clave, entrada in ((manifest or {}).get("backups") or {}).items():
            if not isinstance(entrada, dict):
                continue
            copias = self._google_copias_ordenadas(entrada)
            if not copias:
                continue
            copia = copias[0]
            juego = str(entrada.get("game") or clave)
            destino, origen_destino = self._ruta_backup_local_para_juego_nube(juego, entrada)
            if os.path.isdir(destino):
                huella_local = self._huella_backup_local_rapida(destino)
                huella_nube = str(copia.get("backup_fingerprint") or "")
                if huella_local and huella_nube and huella_local == huella_nube:
                    estado = "igual"
                else:
                    estado = "distinta"
            else:
                estado = "no_local"
            fecha_txt, _ = self._fecha_drive_a_local(copia.get("createdTime"))
            filas.append({
                "clave": clave,
                "game": juego,
                "entrada": entrada,
                "copy": copia,
                "copies_total": len(copias),
                "size": int(copia.get("size", 0) or 0),
                "fecha": fecha_txt or str(copia.get("uploaded_at", "") or ""),
                "estado": estado,
                "destino": destino,
                "origen_destino": origen_destino,
            })
        filas.sort(key=lambda f: f["game"].lower())
        return filas

    def _google_metadatos_archivo(self, creds, file_id):
        url = ("https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id)
               + "?fields=id,name,size,md5Checksum,trashed")
        try:
            _, _, datos = self._google_request_json("GET", url, creds)
            return datos
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def _google_descargar_archivo(self, creds, file_id, ruta_part, size_total, cancelar=None, progreso=None):
        """Descarga un archivo de Drive a ruta_part, reanudando si ya existe.

        Devuelve (sha256_hex, md5_hex). Si se cancela, el .part se conserva
        para continuar la próxima vez.
        """
        os.makedirs(os.path.dirname(ruta_part), exist_ok=True)
        sha = hashlib.sha256()
        md5 = hashlib.md5()
        ya = 0
        if os.path.isfile(ruta_part):
            ya = os.path.getsize(ruta_part)
            if ya > size_total:
                os.remove(ruta_part)
                ya = 0
            else:
                with open(ruta_part, "rb") as f:
                    for bloque in iter(lambda: f.read(1024 * 1024), b""):
                        sha.update(bloque)
                        md5.update(bloque)
        if ya == size_total and size_total > 0:
            return sha.hexdigest(), md5.hexdigest()

        url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?alt=media"
        cabeceras = self._google_headers(creds)
        if ya > 0:
            cabeceras["Range"] = f"bytes={ya}-"
        req = urllib.request.Request(url, headers=cabeceras, method="GET")
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and ya > 0:
                os.remove(ruta_part)  # el rango ya no vale: empezamos de cero
                return self._google_descargar_archivo(creds, file_id, ruta_part, size_total, cancelar, progreso)
            detalle = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Google Drive HTTP {exc.code}: {detalle}") from exc

        with resp:
            if ya > 0 and resp.status != 206:
                # El servidor ignoró el Range y manda el archivo completo.
                ya = 0
                sha = hashlib.sha256()
                md5 = hashlib.md5()
            modo = "ab" if ya > 0 else "wb"
            descargado = ya
            with open(ruta_part, modo) as f:
                while True:
                    if cancelar is not None and cancelar.is_set():
                        raise InterruptedError("Descarga cancelada por el usuario.")
                    bloque = resp.read(1024 * 1024)
                    if not bloque:
                        break
                    f.write(bloque)
                    sha.update(bloque)
                    md5.update(bloque)
                    descargado += len(bloque)
                    if progreso:
                        progreso(descargado, size_total)
                f.flush()
                os.fsync(f.fileno())
        return sha.hexdigest(), md5.hexdigest()

    def _validar_zip_backup(self, ruta_zip):
        """Comprueba que el ZIP es seguro y está sano ANTES de descomprimir.

        Devuelve (ok, detalle, bytes_descomprimidos, carpeta_raiz_o_None).
        """
        try:
            with zipfile.ZipFile(ruta_zip, "r") as zf:
                infos = zf.infolist()
                if not infos:
                    return False, "el ZIP está vacío", 0, None
                if len(infos) > self.NUBE_ZIP_MAX_ARCHIVOS:
                    return False, f"el ZIP tiene demasiados archivos ({len(infos):,})", 0, None
                vistos = set()
                total = 0
                raices = set()
                for info in infos:
                    nombre = info.filename.replace("\\", "/")
                    partes = self._ruta_relativa_segura(nombre)
                    if partes is None:
                        return False, f"ruta no permitida dentro del ZIP: {info.filename}", 0, None
                    if any(":" in p for p in partes):
                        return False, f"nombre no válido en Windows: {info.filename}", 0, None
                    tipo = (info.external_attr >> 16) & 0o170000
                    if tipo == 0o120000:
                        return False, f"el ZIP contiene un enlace simbólico: {info.filename}", 0, None
                    clave = "/".join(partes).lower()
                    if clave in vistos:
                        return False, f"nombre duplicado dentro del ZIP: {info.filename}", 0, None
                    vistos.add(clave)
                    if not info.is_dir():
                        if (info.compress_size > 0 and info.file_size > 100 * 1024 * 1024
                                and info.file_size / info.compress_size > self.NUBE_ZIP_MAX_RATIO):
                            return False, f"ratio de compresión sospechoso en {info.filename}", 0, None
                        total += info.file_size
                    raices.add(partes[0] if (len(partes) > 1 or info.is_dir()) else "")
                malo = zf.testzip()
                if malo is not None:
                    return False, f"CRC incorrecto en {malo} (archivo dañado)", 0, None
            raiz = next(iter(raices)) if len(raices) == 1 and "" not in raices else None
            return True, "ZIP correcto", total, raiz
        except zipfile.BadZipFile as exc:
            return False, f"no es un ZIP válido: {exc}", 0, None
        except Exception as exc:
            return False, f"no se pudo leer el ZIP: {exc}", 0, None

    def _extraer_zip_seguro(self, ruta_zip, destino_tmp, cancelar=None):
        """Extrae el ZIP (ya validado) dentro de destino_tmp, sin salir de ella."""
        base = os.path.abspath(destino_tmp)
        with zipfile.ZipFile(ruta_zip, "r") as zf:
            for info in zf.infolist():
                if cancelar is not None and cancelar.is_set():
                    raise InterruptedError("Descarga cancelada por el usuario.")
                partes = self._ruta_relativa_segura(info.filename)
                destino = os.path.abspath(os.path.join(base, *partes))
                if os.path.commonpath([base, destino]) != base:
                    raise RuntimeError(f"ruta fuera de la carpeta temporal: {info.filename}")
                if info.is_dir():
                    os.makedirs(destino, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with zf.open(info, "r") as origen, open(destino, "wb") as salida:
                    shutil.copyfileobj(origen, salida, 1024 * 1024)
                try:
                    instante = time.mktime(info.date_time + (0, 0, -1))
                    os.utime(destino, (instante, instante))
                except Exception:
                    pass

    def _restaurar_fechas_archivos_grandes(self, carpeta):
        """Devuelve a los archivos grandes la fecha exacta registrada en ash_backup.json.

        Los archivos > 256 MB se verifican por tamaño + fecha (no por SHA-256).
        El ZIP solo guarda la fecha con 2 s de precisión, así que sin esto la
        verificación fallaría aunque el archivo sea idéntico.
        """
        ruta_meta = os.path.join(carpeta, BACKUP_METADATA_NAME)
        try:
            with open(ruta_meta, "r", encoding="utf-8") as f:
                grandes = (json.load(f).get("large_file_signatures") or {})
        except Exception:
            return
        for rel, firma in grandes.items():
            partes = self._ruta_relativa_segura(rel)
            if not partes or not isinstance(firma, dict):
                continue
            ruta = os.path.join(carpeta, *partes)
            try:
                if os.path.getsize(ruta) == int(firma.get("size", -1)) and firma.get("mtime_ns"):
                    ns = int(firma["mtime_ns"])
                    os.utime(ruta, ns=(ns, ns))
            except Exception:
                continue

    def _google_descargar_un_backup(self, creds, fila, cancelar=None, avisar=None):
        """Descarga, verifica y coloca un backup. Devuelve (estado, detalle).

        estado: "ok", "igual", "error" o "cancelado".
        """
        avisar = avisar or (lambda *_: None)
        juego = fila["game"]
        copia = fila["copy"]
        file_id = str(copia.get("id", ""))
        destino = fila["destino"]
        dir_descargas = os.path.join(GOOGLE_CLOUD_DIR, "Descargas").replace("\\", "/")
        ruta_part = os.path.join(dir_descargas, f"{file_id}.zip.part")
        ruta_zip = os.path.join(dir_descargas, f"{file_id}.zip")
        tmp_extraccion = None
        completado = False
        try:
            # 0. ¿Ya lo tenemos igual?
            huella_nube = str(copia.get("backup_fingerprint") or "")
            if os.path.isdir(destino) and huella_nube and self._huella_backup_local_rapida(destino) == huella_nube:
                completado = True
                return "igual", "ya tenías esta misma copia en el PC"

            # 1. Metadatos de Drive
            avisar("Comprobando en Google Drive…", None)
            meta = self._google_metadatos_archivo(creds, file_id)
            if not meta:
                return "error", "la copia ya no existe en Google Drive (pulsa Sincronizar)"
            if meta.get("trashed"):
                return "error", "la copia está en la papelera de Google Drive"
            size_total = int(meta.get("size", 0) or 0)
            md5_drive = str(meta.get("md5Checksum", "") or "").lower()
            if size_total <= 0:
                return "error", "Google Drive indica que el archivo está vacío"

            # 2. Espacio para el ZIP
            ya = os.path.getsize(ruta_part) if os.path.isfile(ruta_part) else 0
            resultado_espacio = self._espacio_suficiente(dir_descargas, max(0, size_total - ya))
            if not resultado_espacio[0]:
                return "error", (f"no hay espacio para descargar el ZIP "
                                 f"(necesario {self._formatear_bytes(resultado_espacio[2])}, "
                                 f"libre {self._formatear_bytes(resultado_espacio[1])})")

            # 3. Descarga
            if os.path.isfile(ruta_zip):
                os.remove(ruta_zip)
            sha_zip, md5_zip = self._google_descargar_archivo(
                creds, file_id, ruta_part, size_total, cancelar,
                lambda hecho, total: avisar("Descargando…", hecho / total if total else None),
            )

            # 4. Tamaño, MD5 (Drive) y SHA-256 (registrado al subir)
            avisar("Verificando descarga…", None)
            if os.path.getsize(ruta_part) != size_total:
                os.remove(ruta_part)
                return "error", "el tamaño descargado no coincide con Google Drive"
            if md5_drive and md5_zip != md5_drive:
                os.remove(ruta_part)
                return "error", "el MD5 no coincide con Google Drive (descarga dañada)"
            sha_esperado = str(copia.get("zip_sha256", "") or "").lower()
            if sha_esperado and sha_zip != sha_esperado:
                os.remove(ruta_part)
                return "error", "el SHA-256 del ZIP no coincide con el registrado al subirlo"
            os.replace(ruta_part, ruta_zip)

            # 5. ZIP seguro y sano
            avisar("Comprobando el ZIP…", None)
            ok, detalle, total_descomprimido, carpeta_raiz = self._validar_zip_backup(ruta_zip)
            if not ok:
                return "error", detalle

            # 6. Espacio para descomprimir (en el disco de destino)
            padre_destino = os.path.dirname(destino)
            resultado_espacio = self._espacio_suficiente(padre_destino, total_descomprimido)
            if not resultado_espacio[0]:
                return "error", (f"no hay espacio para descomprimir "
                                 f"(necesario {self._formatear_bytes(resultado_espacio[2])}, "
                                 f"libre {self._formatear_bytes(resultado_espacio[1])})")

            # 7. Extracción a carpeta temporal en el mismo disco
            avisar("Descomprimiendo…", None)
            tmp_extraccion = os.path.join(padre_destino, f".ash_nube_{uuid.uuid4().hex[:10]}").replace("\\", "/")
            os.makedirs(tmp_extraccion, exist_ok=False)
            self._extraer_zip_seguro(ruta_zip, tmp_extraccion, cancelar)
            contenido = os.path.join(tmp_extraccion, carpeta_raiz) if carpeta_raiz else tmp_extraccion
            self._restaurar_fechas_archivos_grandes(contenido)

            # 8. Integridad con ash_backup.json
            avisar("Verificando integridad (SHA-256)…", None)
            ok, detalle = self._verificar_integridad_backup(contenido)
            if not ok:
                return "error", f"la copia descargada no supera la verificación: {detalle}"
            if huella_nube and os.path.isfile(os.path.join(contenido, BACKUP_METADATA_NAME)):
                if self._google_hash_backup_carpeta(contenido) != huella_nube:
                    return "error", "la copia descargada no es la que indica el índice de la nube"

            # 9. Colocar: la actual pasa a histórico y la nueva ocupa su sitio
            avisar("Guardando en tus backups…", None)
            if cancelar is not None and cancelar.is_set():
                raise InterruptedError("Descarga cancelada por el usuario.")
            _, instante = self._fecha_drive_a_local(copia.get("createdTime"))
            if instante:
                try:
                    os.utime(contenido, (instante, instante))
                except Exception:
                    pass
            archivado = None
            if os.path.exists(destino):
                archivado = self.rotar_a_old(destino)
                if archivado is False:
                    return "error", "no se pudo archivar tu copia local actual; no se ha cambiado nada"
            try:
                os.makedirs(padre_destino, exist_ok=True)
                shutil.move(contenido, destino)
            except Exception as exc:
                if archivado and not os.path.exists(destino):
                    try:
                        shutil.move(archivado, destino)
                    except Exception:
                        pass
                return "error", f"no se pudo colocar la copia descargada: {exc}"
            try:
                self._purgar_backups_historicos_antiguos(destino)
            except Exception:
                pass
            completado = True
            extra = " (tu copia anterior se ha guardado como histórica)" if archivado else ""
            return "ok", destino + extra
        except InterruptedError:
            return "cancelado", "cancelado (la descarga parcial se conserva para continuar después)"
        except Exception as exc:
            self._log("ERROR", "Error al descargar %s de la nube: %s", juego, exc, exc_info=True)
            return "error", str(exc)
        finally:
            if tmp_extraccion and os.path.isdir(tmp_extraccion):
                shutil.rmtree(tmp_extraccion, ignore_errors=True)
            # El ZIP completo ya no sirve (se ha colocado o no pasó las
            # comprobaciones). El .part solo se conserva si la descarga quedó a
            # medias, para poder continuarla después.
            for ruta in ((ruta_zip, ruta_part) if completado else (ruta_zip,)):
                try:
                    os.remove(ruta)
                except OSError:
                    pass

    def _google_descargar_backups(self, filas, ventana_progreso=None):
        """Descarga varios backups en orden. Se ejecuta en un hilo de fondo."""
        if getattr(self, "_cloud_upload_active", False):
            self.root.after(0, lambda: mb.showwarning(
                "Nube", "Hay una subida a Google Drive en curso. Espera a que termine para descargar.",
                parent=self.root))
            if ventana_progreso:
                self.root.after(0, ventana_progreso["cerrar"])
            return
        cancelar = ventana_progreso["cancelar"] if ventana_progreso else threading.Event()
        self._cloud_download_active = True
        resultados = []
        try:
            creds = self._google_obtener_credenciales(pedir_json=False)
            if creds is None:
                raise RuntimeError("Google Drive no está conectado. Conecta la cuenta desde ☁ Nube.")
            total = len(filas)
            for i, fila in enumerate(filas, 1):
                if cancelar.is_set():
                    resultados.append((fila["game"], "cancelado", "no iniciado"))
                    continue

                def avisar(texto, fraccion, i=i, fila=fila):
                    if ventana_progreso:
                        self.root.after(0, lambda: ventana_progreso["actualizar"](
                            f"({i}/{total}) {fila['game']}", texto, fraccion))

                estado, detalle = self._google_descargar_un_backup(creds, fila, cancelar, avisar)
                self._log("INFO", "Descarga de nube %s: %s (%s)", fila["game"], estado, detalle)
                resultados.append((fila["game"], estado, detalle))
        except Exception as exc:
            self._log("ERROR", "Error en la descarga desde Google Drive: %s", exc, exc_info=True)
            resultados.append(("Google Drive", "error", str(exc)))
        finally:
            self._cloud_download_active = False
            if ventana_progreso:
                self.root.after(0, ventana_progreso["cerrar"])

        ok = [r for r in resultados if r[1] == "ok"]
        iguales = [r for r in resultados if r[1] == "igual"]
        errores = [r for r in resultados if r[1] == "error"]
        cancelados = [r for r in resultados if r[1] == "cancelado"]
        lineas = [f"Descargados y verificados: {len(ok)}"]
        if iguales:
            lineas.append(f"Ya los tenías iguales: {len(iguales)}")
        if cancelados:
            lineas.append(f"Cancelados: {len(cancelados)}")
        if errores:
            lineas.append(f"Con error: {len(errores)}")
            lineas.append("")
            for juego, _, detalle in errores[:8]:
                lineas.append(f"• {juego}: {detalle}")
            if len(errores) > 8:
                lineas.append(f"… y {len(errores) - 8} más (ver log)")
        if ok:
            lineas.append("")
            lineas.append("Las copias están en tu carpeta de backups. Para usarlas, "
                          "selecciona el juego y pulsa Restaurar.")
        texto = "\n".join(lineas)
        icono = mb.showwarning if errores else mb.showinfo
        self.root.after(0, lambda: icono("Descarga desde la nube", texto, parent=self.root))
        if ok:
            try:
                self.scan()
            except Exception as exc:
                self._log("WARNING", "No se pudo refrescar la lista tras la descarga: %s", exc)

    def _google_subir_backups(self, juegos=None, mostrar_resultado=False, forzar=False):
        self._cloud_upload_active = True
        try:
            try:
                config_pre = self._cargar_config_nube()
                if config_pre.get("no_subir_red_medida") and self._pc_usa_red_medida() and not forzar:
                    self._log("INFO", "Subida a Google Drive omitida: la conexión actual parece ser una red medida.")
                    if mostrar_resultado:
                        self.root.after(0, lambda: mb.showinfo("Nube", "La subida se ha omitido porque estás usando una red medida."))
                    return 0
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is None:
                    raise RuntimeError("Google Drive no está conectado. Conecta la cuenta desde ☁ Nube.")
                config = self._cargar_config_nube()
                root_id = self._google_preparar_carpeta_ash(creds)
                # Antes de subir no forzamos siempre una sincronización completa.
                # Si la caché sigue vigente y ArlequinConfigNube.json no ha cambiado
                # en Drive, reutilizamos el manifiesto y evitamos repetir el
                # análisis completo. Solo sincronizamos de verdad si la caché
                # caducó o el manifiesto remoto cambió.
                self._google_preparar_manifest_para_subida(creds, max_age=600.0)
                candidatos = []
                if juegos:
                    for juego in juegos:
                        if juego in self.juegos and self.juegos.get(juego):
                            origen = self.juegos[juego]
                            origenes = [origen] if isinstance(origen, str) else list(origen)
                            nombre_limpio = self.limpiar_nombre_juego(juego)
                            raices = self._raices_pc_unicas(origenes, nombre_limpio)
                            if len(raices) > 1:
                                game_root = self._backup_game_root_multiruta(nombre_limpio)
                                if self._backup_multiruta_completo(game_root, raices):
                                    candidatos.append((nombre_limpio, game_root))
                            else:
                                for orig in origenes:
                                    ruta_real = orig if os.path.isabs(orig) else os.path.join(UP, orig)
                                    game_root = self._backup_game_root(ruta_real, nombre_limpio)
                                    if os.path.isdir(game_root):
                                        candidatos.append((nombre_limpio, game_root))
                                        break
                else:
                    for raiz, dirs, _ in os.walk(self.dest):
                        for d in dirs:
                            if self._es_backup_historico_con_fecha(d):
                                continue
                            ruta = os.path.join(raiz, d)
                            if os.path.isfile(os.path.join(ruta, BACKUP_METADATA_NAME)):
                                candidatos.append((d, ruta))

                vistos = set()
                candidatos = [(n, p) for n, p in candidatos if not (os.path.normcase(os.path.normpath(p)) in vistos or vistos.add(os.path.normcase(os.path.normpath(p))))]
                subidos = 0
                omitidos_duplicados = 0
                for nombre_juego, carpeta in candidatos:
                    bloqueada, motivo_bloqueo = self._cloud_subida_bloqueada_por_protecciones(carpeta, nombre_juego, forzar=forzar)
                    if bloqueada:
                        omitidos_duplicados += 1
                        self._log("WARNING", "Subida a nube bloqueada para %s: %s", nombre_juego, motivo_bloqueo)
                        continue
                    # Si Drive ya conoce una copia con el mismo contenido, no
                    # generamos ni subimos otro ZIP idéntico. Esta comprobación
                    # se hace ANTES de buscar la carpeta del juego en Drive,
                    # evitando otra petición HTTP por cada backup ya existente.
                    manifest_actual = getattr(self, "cloud_manifest", None) or self._cargar_manifest_nube_local()
                    entrada_actual = ((manifest_actual.get("backups") or {}).get(self._clave_nube_juego(nombre_juego)) or {})
                    copias_actuales = [c for c in (entrada_actual.get("copies") or []) if isinstance(c, dict)]

                    # Vía rápida: ash_backup.json ya contiene los hashes necesarios
                    # para construir backup_fingerprint. Evitamos recorrer y hashear
                    # todos los archivos cuando el backup ya está en Drive.
                    huella_legacy = self._google_hash_backup_carpeta(carpeta)
                    copia_igual = any(c.get("backup_fingerprint") == huella_legacy for c in copias_actuales)
                    if copia_igual:
                        omitidos_duplicados += 1
                        self._log("INFO", "Subida a nube omitida para %s: ya existe una copia idéntica (comprobación rápida).", nombre_juego)
                        continue

                    # Solo si la comprobación rápida no coincide calculamos la
                    # huella completa del contenido para detectar equivalencias
                    # heredadas o casos en los que el metadato no sea suficiente.
                    contenido_actual = self._google_hash_contenido_carpeta(carpeta)
                    copia_igual = any(c.get("content_fingerprint") == contenido_actual for c in copias_actuales)
                    if copia_igual:
                        omitidos_duplicados += 1
                        self._log("INFO", "Subida a nube omitida para %s: ya existe una copia idéntica.", nombre_juego)
                        continue

                    # Solo necesitamos hablar con Drive para un backup que
                    # realmente vaya a subirse. Si el manifiesto ya conoce la
                    # carpeta del juego, reutilizamos su ID.
                    game_id = str(entrada_actual.get("folder_id", "") or "")
                    if not game_id:
                        game_id = self._google_buscar_carpeta(creds, nombre_juego, root_id)
                    if not game_id:
                        game_id = self._google_crear_carpeta(creds, nombre_juego, root_id)

                    zip_preparado = self._google_obtener_zip_preparado(carpeta, nombre_juego)
                    datos_subida = self._google_subir_backup_carpeta(creds, carpeta, nombre_juego, game_id, zip_preparado=zip_preparado)
                    self._google_purgar_copias_remotas(creds, game_id, config["max_copias"])
                    archivos_remotos = self._google_listar_subidas_juego(creds, game_id)
                    manifest = self._cargar_manifest_nube_local()
                    clave_nube = self._clave_nube_juego(nombre_juego)
                    anterior = ((manifest.get("backups") or {}).get(clave_nube) or {})
                    hashes_previos = {str(c.get("id")): c for c in (anterior.get("copies") or []) if isinstance(c, dict) and c.get("id")}
                    fingerprint = str((datos_subida or {}).get("_ash_backup_fingerprint", "")) or self._google_hash_backup_carpeta(carpeta)
                    nuevo_id = str((datos_subida or {}).get("id", ""))
                    copias_manifest = []
                    for archivo in archivos_remotos:
                        aid = str(archivo.get("id", ""))
                        previo = hashes_previos.get(aid, {})
                        copia = {
                            "id": aid,
                            "name": archivo.get("name", ""),
                            "createdTime": archivo.get("createdTime", ""),
                            "size": int(archivo.get("size", 0) or 0),
                            "zip_sha256": previo.get("zip_sha256", ""),
                            "backup_fingerprint": previo.get("backup_fingerprint", ""),
                            "content_fingerprint": previo.get("content_fingerprint", ""),
                            "uploaded_at": previo.get("uploaded_at", ""),
                        }
                        if aid == nuevo_id:
                            copia["zip_sha256"] = str((datos_subida or {}).get("_ash_zip_sha256", ""))
                            copia["backup_fingerprint"] = fingerprint
                            copia["content_fingerprint"] = str((datos_subida or {}).get("_ash_content_fingerprint", ""))
                            copia["uploaded_at"] = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
                        copias_manifest.append(copia)
                    manifest.setdefault("version", 1)
                    manifest.setdefault("backups", {})
                    # Ubicación relativa dentro de la carpeta de backups. Permite
                    # que otro PC que descargue esta copia la coloque en el mismo
                    # sitio aunque el juego todavía no esté instalado allí.
                    try:
                        local_rel = os.path.relpath(carpeta, self.dest).replace("\\", "/")
                        if local_rel.startswith("..") or os.path.isabs(local_rel):
                            local_rel = ""
                    except ValueError:
                        local_rel = ""
                    manifest["backups"][clave_nube] = {
                        "game": nombre_juego,
                        "folder_id": game_id,
                        "copies": copias_manifest,
                        "local_rel": local_rel or anterior.get("local_rel", ""),
                    }
                    self._guardar_manifest_nube_local(manifest)
                    # El backup nuevo ya está incorporado al manifiesto local.
                    # Si la caché sigue siendo válida y el manifiesto remoto no
                    # cambió mientras trabajábamos, publicamos directamente el
                    # manifiesto: una subida pequeña, sin volver a descargar ni
                    # fusionar todo. Si cambió, hacemos la sincronización completa
                    # para no pisar cambios hechos desde otro dispositivo.
                    config_actual = self._cargar_config_nube()
                    folder_manifest = str(config_actual.get("manifest_folder_id", "") or "")
                    file_manifest = str(config_actual.get("manifest_file_id", "") or "")
                    if folder_manifest and file_manifest and self._google_manifest_remoto_sigue_igual(creds):
                        file_manifest, datos_manifest = self._google_subir_manifest_nube(
                            creds, manifest, folder_manifest, file_manifest
                        )
                        self._guardar_config_nube(
                            cloud_manifest_folder_id=folder_manifest,
                            cloud_manifest_file_id=file_manifest,
                            cloud_manifest_last_sync=manifest.get("updated_at", ""),
                            cloud_manifest_remote_modified_time=str((datos_manifest or {}).get("modifiedTime", "") or ""),
                        )
                        self._cloud_manifest_sync_monotonic = time.monotonic()
                    else:
                        self._google_sincronizar_manifest_nube(creds, mostrar_error=True)
                    subidos += 1
                ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                cuenta = config.get("account", "")
                self._guardar_config_nube(cloud_last_upload=ahora, cloud_account=cuenta)
                self._log("INFO", "Subida a Google Drive completada: %d nuevo(s), %d omitido(s) por duplicado.", subidos, omitidos_duplicados)
                if mostrar_resultado:
                    texto_resultado = f"Sincronización completada.\n\nBackups subidos: {subidos}\nYa estaban en la nube: {omitidos_duplicados}"
                    self.root.after(0, lambda texto_resultado=texto_resultado: mb.showinfo("Nube", texto_resultado))
                return subidos
            except Exception as exc:
                self._log("ERROR", "Error al subir backups a Google Drive: %s", exc, exc_info=True)
                if mostrar_resultado:
                    error_text = str(exc)
                    self.root.after(0, lambda error_text=error_text: mb.showerror("Nube", f"No se pudo completar la subida.\n\n{error_text}"))
                return 0
        finally:
            self._cloud_upload_active = False

    def _reanudar_subida_nube_pendiente(self):
        """Reanuda al arrancar una subida que quedó pendiente al cerrar ASH."""
        estado = self._google_cargar_estado_subida()
        if not estado.get("path") or not estado.get("session_url"):
            return
        ruta = estado.get("path", "")
        if not os.path.isfile(ruta):
            self._log("WARNING", "Se encontró una subida pendiente pero ya no existe el ZIP local: %s", ruta)
            self._google_borrar_estado_subida()
            return

        def trabajador():
            self._cloud_upload_active = True
            try:
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is None:
                    self._log("WARNING", "Hay una subida pendiente, pero Google Drive no está conectado.")
                    return
                parent_id = str(estado.get("parent_id", ""))
                nombre = str(estado.get("name", ""))
                if not parent_id or not nombre:
                    self._log("WARNING", "El estado de subida pendiente está incompleto.")
                    self._google_borrar_estado_subida()
                    return
                zip_sha256 = self._google_sha256(ruta)
                backup_fingerprint = str(estado.get("backup_fingerprint", ""))
                content_fingerprint = str(estado.get("content_fingerprint", ""))
                datos = self._google_subir_reanudable(
                    creds, ruta, nombre, parent_id, str(estado.get("game", "")), backup_fingerprint, content_fingerprint
                )
                if isinstance(datos, dict):
                    datos["_ash_zip_sha256"] = zip_sha256
                    datos["_ash_backup_fingerprint"] = backup_fingerprint
                    datos["_ash_content_fingerprint"] = content_fingerprint
                # Google ya ha confirmado la subida: el ZIP temporal sobra.
                try:
                    os.remove(ruta)
                except OSError:
                    pass
                with self._cloud_prepared_lock:
                    for clave_zip, info_zip in list(self._cloud_prepared_zips.items()):
                        if info_zip.get("zip_path") == ruta:
                            self._cloud_prepared_zips.pop(clave_zip, None)
                config = self._cargar_config_nube()
                self._google_purgar_copias_remotas(creds, parent_id, config["max_copias"])
                archivos_remotos = self._google_listar_subidas_juego(creds, parent_id)
                manifest = self._cargar_manifest_nube_local()
                juego = str(estado.get("game", "")) or self._normalizar_nombre_ruta(nombre).split(" - ")[0]
                clave_nube = self._clave_nube_juego(juego)
                anterior = ((manifest.get("backups") or {}).get(clave_nube) or {})
                hashes_previos = {str(c.get("id")): c for c in (anterior.get("copies") or []) if isinstance(c, dict) and c.get("id")}
                fingerprint = str((datos or {}).get("_ash_backup_fingerprint", "")) or str(estado.get("backup_fingerprint", ""))
                if not fingerprint:
                    fingerprint = zip_sha256
                nuevo_id = str((datos or {}).get("id", ""))
                copias_manifest = []
                for archivo in archivos_remotos:
                    aid = str(archivo.get("id", ""))
                    previo = hashes_previos.get(aid, {})
                    copia = {"id": aid, "name": archivo.get("name", ""), "createdTime": archivo.get("createdTime", ""),
                             "size": int(archivo.get("size", 0) or 0), "zip_sha256": previo.get("zip_sha256", ""),
                              "backup_fingerprint": previo.get("backup_fingerprint", ""), "content_fingerprint": previo.get("content_fingerprint", ""), "uploaded_at": previo.get("uploaded_at", "")}
                    if aid == nuevo_id:
                        copia["zip_sha256"] = str((datos or {}).get("_ash_zip_sha256", ""))
                        copia["backup_fingerprint"] = fingerprint
                        copia["content_fingerprint"] = str((datos or {}).get("_ash_content_fingerprint", ""))
                        copia["uploaded_at"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                    copias_manifest.append(copia)
                manifest.setdefault("version", 1)
                manifest.setdefault("backups", {})
                manifest["backups"][clave_nube] = {"game": juego, "folder_id": parent_id, "copies": copias_manifest,
                                                   "local_rel": anterior.get("local_rel", "")}
                self._guardar_manifest_nube_local(manifest)
                self._google_sincronizar_manifest_nube(creds, mostrar_error=False)
                ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                self._guardar_config_nube(cloud_last_upload=ahora, cloud_account=config.get("account", ""))
                self._log("INFO", "Subida pendiente reanudada y completada: %s", nombre)
                self.root.after(0, lambda: mb.showinfo(
                    "Nube",
                    "La subida pendiente de Google Drive se ha reanudado y completado correctamente.",
                    parent=self.root,
                ))
            except Exception as exc:
                self._log("ERROR", "No se pudo reanudar la subida pendiente: %s", exc, exc_info=True)
                error_text = str(exc)
                self.root.after(0, lambda error_text=error_text: mb.showwarning(
                    "Nube",
                    "Hay una subida pendiente de Google Drive que no se ha podido reanudar todavía.\n\n" + error_text,
                    parent=self.root,
                ))
            finally:
                self._cloud_upload_active = False

        self.root.after(1500, lambda: self.ejecutar_en_hilo(trabajador))

    def _sincronizar_manifest_nube_al_arranque(self):
        config = self._cargar_config_nube()
        if not config.get("account") or not os.path.exists(GOOGLE_TOKEN_FILE):
            return
        def trabajador():
            try:
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is None:
                    return
                self._google_sincronizar_manifest_nube(creds, mostrar_error=False)
                self.root.after(0, self._actualizar_indicadores_nube)
            except Exception as exc:
                self._log("WARNING", "No se pudo actualizar el estado de nube al arrancar: %s", exc, exc_info=True)
        threading.Thread(target=trabajador, name="ASHCloudManifestSync", daemon=True).start()

    def _programar_subida_nube(self, juegos=None, forzar=False):
        config = self._cargar_config_nube()
        if not config["auto"] and not (forzar and config.get("al_cierre")):
            return False
        def trabajador():
            self._google_subir_backups(juegos=juegos, mostrar_resultado=False)
        self.ejecutar_en_hilo(trabajador)
        return True

    def conectar_google_drive(self, ventana=None, estado_label=None):
        def trabajador():
            try:
                creds = self._google_obtener_credenciales(pedir_json=True)
                if creds is None:
                    return
                usuario = self._google_about(creds)
                email = usuario.get("emailAddress", "")
                self._google_preparar_carpeta_ash(creds)
                self._guardar_config_nube(cloud_account=email)
                self._google_sincronizar_manifest_nube(creds, mostrar_error=True)
                def actualizar():
                    if estado_label is not None and estado_label.winfo_exists():
                        estado_label.config(text=f"✓ Conectado a Google Drive\nCuenta: {email}", fg="#2ecc71")
                    if ventana is not None and ventana.winfo_exists():
                        ventana.destroy()
                        self.mostrar_nube()
                    else:
                        self.mostrar_nube()
                self.root.after(0, actualizar)
            except Exception as exc:
                self._log("ERROR", "No se pudo conectar Google Drive: %s", exc, exc_info=True)
                # Las variables de excepción de un `except` se eliminan al salir del bloque.
                # Guardamos el texto antes de crear la lambda para que Tkinter pueda mostrarlo
                # cuando el callback se ejecute en el hilo principal.
                error_text = str(exc)
                self.root.after(0, lambda error_text=error_text: mb.showerror(
                    "Google Drive",
                    f"No se pudo conectar con Google Drive.\n\n{error_text}",
                    parent=ventana or self.root
                ))
        threading.Thread(target=trabajador, name="ASHGoogleOAuth", daemon=True).start()

    def desconectar_google_drive(self, ventana=None):
        try:
            if os.path.exists(GOOGLE_TOKEN_FILE):
                os.remove(GOOGLE_TOKEN_FILE)
        except OSError:
            pass
        self._google_borrar_estado_subida()
        self._guardar_config_nube(cloud_account="", cloud_folder_id="", cloud_last_upload="", cloud_auto_upload=False,
                                  cloud_manifest_folder_id="", cloud_manifest_file_id="", cloud_manifest_last_sync="", cloud_manifest_remote_modified_time="")
        self.cloud_manifest = {"version": 1, "updated_at": "", "backups": {}}
        self._cloud_manifest_sync_monotonic = 0.0
        try:
            os.remove(GOOGLE_CLOUD_MANIFEST_FILE)
        except OSError:
            pass
        if ventana is not None and ventana.winfo_exists():
            ventana.destroy()
        self.mostrar_nube()

    def mostrar_nube(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("☁ Nube")
        # La ventana Nube se ajusta automáticamente al contenido para no dejar
        # grandes espacios vacíos. La anchura se limita a un tamaño cómodo y
        # la altura se calcula después de crear los controles.
        ventana.geometry("520x260")
        ventana.resizable(False, False)
        ventana.configure(bg="#2c3e50")
        ventana.transient(self.root)
        ventana.grab_set()
        self.aplicar_icono_ventana(ventana)

        def ajustar_tamano_nube():
            ventana.update_idletasks()
            ancho = max(500, min(620, ventana.winfo_reqwidth() + 20))
            alto = ventana.winfo_reqheight() + 12
            self.centrar_ventana(ventana, ancho, alto)

        tk.Label(ventana, text="☁ Nube", font=("Arial", 17, "bold"), fg="white", bg="#2c3e50").pack(pady=(18, 8))
        config = self._cargar_config_nube()
        conectado = os.path.exists(GOOGLE_TOKEN_FILE) and bool(config.get("account"))

        if not conectado:
            aviso_pruebas = tk.Frame(ventana, bg="#34495e", bd=1, relief="solid")
            aviso_pruebas.pack(fill="x", padx=18, pady=(5, 8))
            tk.Label(
                aviso_pruebas, text="⚠️ VERSIÓN DE PRUEBA",
                font=("Arial", 11, "bold"), fg="#f1c40f", bg="#34495e"
            ).pack(pady=(10, 6))
            tk.Label(
                aviso_pruebas,
                text=(
                    "La integración con Google Drive se encuentra actualmente en fase de pruebas.\n\n"
                    "Para poder conectar tu cuenta, debes solicitar acceso previamente. "
                    "Contacta conmigo para que pueda añadir tu correo electrónico a la lista de usuarios autorizados.\n\n"
                    "📧 Contacto: arlequinsavehub@gmail.com\n\n"
                    "⏳ ACCESO TEMPORAL\n\n"
                    "Una vez te haya dado acceso, podrás utilizar la conexión con Google Drive durante 1 semana.\n\n"
                    "Cuando transcurra ese periodo, el acceso caducará y tendrás que volver a solicitarme acceso "
                    "si quieres seguir utilizando la nube de Google.\n\n"
                    "Este sistema temporal se mantendrá mientras termino de completar y validar la integración con Google.\n\n"
                    "Después de completar la validación, el sistema de acceso podrá cambiar."
                ),
                font=("Arial", 9), fg="white", bg="#34495e", wraplength=470,
                justify="left"
            ).pack(padx=12, pady=(0, 10))
            tk.Label(ventana, text="Conecta una cuenta para guardar tus backups en la nube.",
                     font=("Arial", 10), fg="#bdc3c7", bg="#2c3e50", wraplength=500,
                     justify="center").pack(pady=(5, 10))
            tk.Button(ventana, text="☁ Conectar Google Drive", command=lambda: self.conectar_google_drive(ventana),
                      bg="#4285f4", fg="white", font=("Arial", 11, "bold"), bd=0,
                      padx=18, pady=9, cursor="hand2").pack(pady=8)
            tk.Label(ventana, text="Google abrirá su página oficial de inicio de sesión en el navegador.",
                     font=("Arial", 9), fg="#95a5a6", bg="#2c3e50", wraplength=480,
                     justify="center").pack(pady=8)
            tk.Button(ventana, text="Cerrar", command=ventana.destroy, bg="#7f8c8d", fg="white",
                      font=("Arial", 10), bd=0, padx=20, pady=6, cursor="hand2").pack(side="bottom", pady=20)
            ajustar_tamano_nube()
            return

        marco = tk.Frame(ventana, bg="#34495e", bd=1, relief="solid")
        marco.pack(fill="x", padx=25, pady=10)
        tk.Label(marco, text="✓ Conectado a Google Drive", font=("Arial", 12, "bold"),
                 fg="#2ecc71", bg="#34495e").pack(anchor="w", padx=15, pady=(14, 3))
        tk.Label(marco, text=f"Cuenta: {config.get('account') or 'Cuenta de Google'}",
                 font=("Arial", 10), fg="white", bg="#34495e").pack(anchor="w", padx=15, pady=3)
        tk.Label(marco, text=f"Última subida: {config.get('last_upload') or 'Nunca'}",
                 font=("Arial", 10), fg="#bdc3c7", bg="#34495e").pack(anchor="w", padx=15, pady=(3, 3))
        lbl_espacio_nube = tk.Label(
            marco, text="Espacio en Drive: consultando…",
            font=("Arial", 9), fg="#95a5a6", bg="#34495e", anchor="w",
        )
        lbl_espacio_nube.pack(anchor="w", padx=15, pady=(0, 6))
        lbl_sincronizacion_nube = tk.Label(
            marco, text="✓ Estado de nube disponible",
            font=("Arial", 9), fg="#2ecc71", bg="#34495e", anchor="w",
        )
        lbl_sincronizacion_nube.pack(anchor="w", padx=15, pady=(0, 10))

        def consultar_espacio_nube():
            try:
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is None:
                    return
                texto_espacio = self._google_obtener_espacio_drive(creds)
                self._guardar_config_nube(cloud_storage_text=texto_espacio)
                ventana.after(0, lambda: lbl_espacio_nube.config(text=texto_espacio))
            except Exception as exc:
                self._log("WARNING", "No se pudo consultar el espacio de Google Drive: %s", exc)
                cache_text = str(config.get("storage_text", "") or "")
                if cache_text:
                    ventana.after(0, lambda: lbl_espacio_nube.config(text=cache_text))

        if config.get("storage_text"):
            lbl_espacio_nube.config(text=str(config.get("storage_text")))
        threading.Thread(target=consultar_espacio_nube, name="ASHDriveQuotaNube", daemon=True).start()

        def actualizar_estado_sincronizacion(ok):
            if not ventana.winfo_exists():
                return
            if ok:
                lbl_sincronizacion_nube.config(
                    text="✓ Sincronizado con Google Drive", fg="#2ecc71"
                )
            else:
                lbl_sincronizacion_nube.config(
                    text="⚠ No se pudo actualizar ahora; se usará el último estado conocido",
                    fg="#f1c40f"
                )

        # No hay un temporizador periódico. Al abrir Nube solo se sincroniza si
        # la última sincronización tiene más de 10 minutos. Si sigue dentro de
        # ese margen, mostramos inmediatamente el estado conocido sin hacer
        # peticiones HTTP. Si hay una sincronización en curso, se reutiliza.
        cache_valida = False
        ultima_sync = float(getattr(self, "_cloud_manifest_sync_monotonic", 0.0) or 0.0)
        if ultima_sync:
            cache_valida = (time.monotonic() - ultima_sync) < 600.0

        if cache_valida:
            lbl_sincronizacion_nube.config(
                text="✓ Sincronizado con Google Drive", fg="#2ecc71"
            )
        elif self._google_sincronizar_manifest_nube_en_segundo_plano(actualizar_estado_sincronizacion) is False:
            if not getattr(self, "_cloud_manifest_sync_active", False):
                lbl_sincronizacion_nube.config(
                    text="✓ Estado de nube disponible", fg="#2ecc71"
                )
            else:
                def esperar_sincronizacion_actual():
                    evento = self._cloud_manifest_sync_event
                    evento.wait(timeout=180)
                    try:
                        self.root.after(0, lambda: actualizar_estado_sincronizacion(True))
                    except Exception:
                        pass
                threading.Thread(target=esperar_sincronizacion_actual, name="ASHCloudManifestWait", daemon=True).start()
        else:
            lbl_sincronizacion_nube.config(
                text="🔄 Sincronizando con Google Drive…", fg="#f1c40f"
            )

        # Mientras el usuario tiene abierta la ventana Nube, ASH prepara en
        # segundo plano los ZIP que realmente podrían necesitar subirse.
        # Si se pulsa "Subir ahora", se reutiliza el ZIP ya preparado.
        threading.Thread(target=self._google_preparar_zips_nube, name="ASHCloudZipPreparer", daemon=True).start()

        # Las preferencias de nube se gestionan desde ⚙️ Opciones.
        # Esta ventana queda dedicada a estado, conexión y acciones puntuales.
        marco_acciones = tk.Frame(ventana, bg="#2c3e50")
        marco_acciones.pack(fill="x", padx=25, pady=(18, 12))
        marco_acciones.grid_columnconfigure(0, weight=1)
        marco_acciones.grid_columnconfigure(1, weight=1)
        marco_acciones.grid_columnconfigure(2, weight=1)

        def subir_ahora_desde_nube():
            ventana.destroy()
            self.ejecutar_en_hilo(lambda: self._google_subir_backups(juegos=None, mostrar_resultado=True))

        def cerrar_nube_sin_subir():
            self._google_descartar_zips_preparados()
            ventana.destroy()

        def sincronizar_ahora_desde_nube():
            # El botón ignora deliberadamente la caché de 10 minutos. Si ya hay
            # otra sincronización en curso, el candado interno hace que se
            # reutilice esa misma operación en lugar de duplicar peticiones.
            lbl_sincronizacion_nube.config(
                text="🔄 Sincronizando con Google Drive…", fg="#f1c40f"
            )
            try:
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is None:
                    lbl_sincronizacion_nube.config(
                        text="⚠ No hay una conexión válida con Google Drive", fg="#f1c40f"
                    )
                    return
                self._cloud_manifest_sync_monotonic = 0.0
                def trabajador_forzado():
                    ok = False
                    try:
                        self._google_sincronizar_manifest_nube(creds, mostrar_error=True)
                        ok = True
                    except Exception as exc:
                        self._log("WARNING", "No se pudo forzar la sincronización de Nube: %s", exc, exc_info=True)
                    try:
                        ventana.after(0, lambda: actualizar_estado_sincronizacion(ok))
                    except Exception:
                        pass
                threading.Thread(target=trabajador_forzado, name="ASHCloudManifestForceSync", daemon=True).start()
            except Exception as exc:
                self._log("WARNING", "No se pudo iniciar la sincronización forzada de Nube: %s", exc, exc_info=True)
                lbl_sincronizacion_nube.config(
                    text="⚠ No se pudo iniciar la sincronización", fg="#f1c40f"
                )

        # Desconectar queda aparte, arriba a la derecha, para no pulsarlo por
        # error junto a las acciones habituales.
        btn_desconectar = tk.Button(ventana, text="⏏ Desconectar", command=lambda: self.desconectar_google_drive(ventana),
                                    bg="#e74c3c", fg="white", font=("Arial", 9), bd=0,
                                    padx=10, pady=4, cursor="hand2")
        btn_desconectar.place(relx=1.0, x=-14, y=14, anchor="ne")

        # Las cuatro acciones quedan en una única fila y a la misma altura.
        marco_acciones.grid_columnconfigure(3, weight=1)
        tk.Button(marco_acciones, text="↻ Sincronizar", command=sincronizar_ahora_desde_nube,
                  bg="#9b59b6", fg="white", font=("Arial", 10, "bold"), bd=0,
                  padx=13, pady=7, cursor="hand2").grid(row=0, column=0, sticky="w")
        tk.Button(marco_acciones, text="☁ Subir ahora", command=subir_ahora_desde_nube,
                  bg="#3498db", fg="white", font=("Arial", 10, "bold"), bd=0,
                  padx=13, pady=7, cursor="hand2").grid(row=0, column=1)
        tk.Button(marco_acciones, text="⬇ Descargar", command=lambda: self.mostrar_descarga_nube(ventana),
                  bg="#27ae60", fg="white", font=("Arial", 10, "bold"), bd=0,
                  padx=13, pady=7, cursor="hand2").grid(row=0, column=2)
        tk.Button(marco_acciones, text="Cerrar", command=cerrar_nube_sin_subir,
                  bg="#7f8c8d", fg="white", font=("Arial", 10), bd=0,
                  padx=17, pady=7, cursor="hand2").grid(row=0, column=3, sticky="e")

        ventana.protocol("WM_DELETE_WINDOW", cerrar_nube_sin_subir)
        ajustar_tamano_nube()

    def _ventana_progreso_descarga_nube(self):
        """Ventana pequeña de progreso con botón Cancelar. Devuelve un dict de control."""
        ventana = tk.Toplevel(self.root)
        ventana.title("⬇ Descargando de la nube")
        ventana.resizable(False, False)
        ventana.configure(bg="#2c3e50")
        ventana.transient(self.root)
        self.aplicar_icono_ventana(ventana)
        cancelar = threading.Event()

        lbl_juego = tk.Label(ventana, text="Preparando…", font=("Arial", 11, "bold"),
                             fg="white", bg="#2c3e50", wraplength=420, justify="left")
        lbl_juego.pack(anchor="w", padx=20, pady=(18, 4))
        lbl_paso = tk.Label(ventana, text="", font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50")
        lbl_paso.pack(anchor="w", padx=20, pady=(0, 8))
        barra = ttk.Progressbar(ventana, orient="horizontal", length=420, mode="indeterminate")
        barra.pack(padx=20, pady=(0, 12))
        barra.start(12)

        def pedir_cancelar():
            cancelar.set()
            lbl_paso.config(text="Cancelando… (se termina el paso actual)")
            btn_cancelar.config(state="disabled")

        btn_cancelar = tk.Button(ventana, text="Cancelar", command=pedir_cancelar,
                                 bg="#7f8c8d", fg="white", font=("Arial", 10), bd=0,
                                 padx=18, pady=6, cursor="hand2")
        btn_cancelar.pack(pady=(0, 16))
        ventana.protocol("WM_DELETE_WINDOW", pedir_cancelar)
        self.centrar_ventana(ventana, 460, 170)

        def actualizar(juego, paso, fraccion):
            if not ventana.winfo_exists():
                return
            lbl_juego.config(text=juego)
            lbl_paso.config(text=paso if not cancelar.is_set() else "Cancelando…")
            if fraccion is None:
                if str(barra.cget("mode")) != "indeterminate":
                    barra.config(mode="indeterminate")
                    barra.start(12)
            else:
                if str(barra.cget("mode")) != "determinate":
                    barra.stop()
                    barra.config(mode="determinate", maximum=1000)
                barra["value"] = int(max(0.0, min(1.0, fraccion)) * 1000)
                lbl_paso.config(text=f"{paso} {fraccion * 100:.0f}%")

        def cerrar():
            try:
                if ventana.winfo_exists():
                    barra.stop()
                    ventana.destroy()
            except Exception:
                pass

        return {"cancelar": cancelar, "actualizar": actualizar, "cerrar": cerrar}

    def _elegir_copia_nube(self, padre, fila, al_elegir, elegida_actual=None):
        """Ventana para elegir qué copia de Google Drive descargar de un juego
        con varias copias. Se llama desde el hilo de Tk. `al_elegir(copia)`
        recibe la copia elegida; si se cancela no se llama."""
        copias = self._google_copias_ordenadas(fila.get("entrada"))
        if not copias:
            return
        huella_local = ""
        if os.path.isdir(fila.get("destino") or ""):
            huella_local = self._huella_backup_local_rapida(fila["destino"])

        top = tk.Toplevel(padre)
        top.title("Elegir copia de la nube")
        top.configure(bg="#2c3e50")
        top.resizable(False, False)
        top.transient(padre)
        top.grab_set()
        self.aplicar_icono_ventana(top)

        tk.Label(top, text=f"\"{fila['game']}\"\nHay {len(copias)} copias en Google Drive. ¿Cuál quieres descargar?",
                 font=("Arial", 11, "bold"), fg="white", bg="#2c3e50", justify="center",
                 wraplength=460).pack(padx=20, pady=(18, 10))

        marco = tk.Frame(top, bg="#2c3e50")
        marco.pack(padx=20, fill="both")
        lista = tk.Listbox(marco, font=("Consolas", 10), height=min(12, len(copias)), width=58,
                           bg="#34495e", fg="white", selectbackground="#1e8449",
                           activestyle="none", exportselection=False)
        barra = ttk.Scrollbar(marco, orient="vertical", command=lista.yview)
        lista.configure(yscrollcommand=barra.set)
        lista.pack(side="left", fill="both", expand=True)
        if len(copias) > 12:
            barra.pack(side="right", fill="y")

        seleccion_inicial = 0
        for i, copia in enumerate(copias):
            fecha_txt, _ = self._fecha_drive_a_local(copia.get("createdTime"))
            fecha_txt = fecha_txt or str(copia.get("uploaded_at", "") or "fecha desconocida")
            texto = f"{fecha_txt:<17} {self._formatear_bytes(int(copia.get('size', 0) or 0)):>10}"
            notas = []
            if i == 0:
                notas.append("más reciente")
            huella = str(copia.get("backup_fingerprint") or "")
            if huella_local and huella and huella == huella_local:
                notas.append("igual que tu copia local")
            if notas:
                texto += "   (" + ", ".join(notas) + ")"
            lista.insert("end", texto)
            if elegida_actual and copia.get("id") == elegida_actual.get("id"):
                seleccion_inicial = i
        lista.selection_set(seleccion_inicial)
        lista.see(seleccion_inicial)

        def aceptar(*_):
            sel = lista.curselection()
            if not sel:
                return
            copia = copias[sel[0]]
            top.destroy()
            al_elegir(copia)

        lista.bind("<Double-Button-1>", aceptar)
        lista.bind("<Return>", aceptar)
        top.bind("<Escape>", lambda _e: top.destroy())

        botones = tk.Frame(top, bg="#2c3e50")
        botones.pack(fill="x", padx=20, pady=(10, 16))
        tk.Button(botones, text="✔ Aceptar", command=aceptar, bg="#27ae60", fg="white",
                  font=("Arial", 10, "bold"), bd=0, padx=16, pady=6, cursor="hand2").pack(side="right")
        tk.Button(botones, text="Cancelar", command=top.destroy, bg="#7f8c8d", fg="white",
                  bd=0, padx=14, pady=6, cursor="hand2").pack(side="right", padx=(0, 8))
        tk.Label(botones, text="Doble clic también acepta.", font=("Arial", 8),
                 fg="#95a5a6", bg="#2c3e50").pack(side="left")

        top.update_idletasks()
        self.centrar_ventana(top, top.winfo_width(), top.winfo_height())
        lista.focus_set()

    def mostrar_descarga_nube(self, ventana_nube=None):
        """Lista los juegos que hay en la nube para elegir cuáles descargar."""
        padre = ventana_nube if (ventana_nube is not None and ventana_nube.winfo_exists()) else self.root
        if getattr(self, "_cloud_upload_active", False):
            mb.showwarning("Nube", "Hay una subida a Google Drive en curso. Espera a que termine para descargar.",
                           parent=padre)
            return
        if getattr(self, "_cloud_download_active", False):
            mb.showinfo("Nube", "Ya hay una descarga en curso.", parent=padre)
            return

        selector = tk.Toplevel(padre)
        selector.title("⬇ Descargar de la nube")
        selector.resizable(True, True)
        selector.minsize(640, 420)
        selector.configure(bg="#2c3e50")
        selector.transient(padre)
        selector.grab_set()
        self.aplicar_icono_ventana(selector)
        self.centrar_ventana(selector, 760, 600)

        tk.Label(selector, text="⬇ Descargar backups de Google Drive", font=("Arial", 13, "bold"),
                 fg="white", bg="#2c3e50").pack(pady=(14, 2))
        tk.Label(selector,
                 text="Se descarga la copia más reciente de cada juego marcado y se verifica antes de guardarla.\n"
                      "Si un juego tiene varias copias, al marcarlo podrás elegir cuál (doble clic para cambiarla).",
                 font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50", justify="center").pack(pady=(0, 8))

        marco_busqueda = tk.Frame(selector, bg="#2c3e50")
        marco_busqueda.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(marco_busqueda, text="Buscar:", font=("Arial", 10, "bold"),
                 fg="white", bg="#2c3e50").pack(side="left")
        var_busqueda = tk.StringVar()
        tk.Entry(marco_busqueda, textvariable=var_busqueda, font=("Arial", 10)).pack(
            side="left", padx=(8, 0), fill="x", expand=True)

        estilo = ttk.Style(selector)
        estilo.configure("Nube.Treeview", background="#34495e", fieldbackground="#34495e",
                         foreground="white", rowheight=24, font=("Arial", 10))
        estilo.configure("Nube.Treeview.Heading", font=("Arial", 10, "bold"))
        estilo.map("Nube.Treeview", background=[("selected", "#34495e")], foreground=[("selected", "white")])

        marco_lista = tk.Frame(selector, bg="#2c3e50")
        marco_lista.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        columnas = ("sel", "juego", "fecha", "tamano", "estado")
        arbol = ttk.Treeview(marco_lista, columns=columnas, show="headings", style="Nube.Treeview",
                             selectmode="none")
        for col, texto, ancho, anclaje in (
            ("sel", "", 34, "center"), ("juego", "Juego", 290, "w"), ("fecha", "Copia", 175, "center"),
            ("tamano", "Tamaño", 90, "e"), ("estado", "En este PC", 150, "w"),
        ):
            arbol.heading(col, text=texto, anchor=anclaje)
            arbol.column(col, width=ancho, anchor=anclaje, stretch=(col == "juego"))
        arbol.tag_configure("marcado", background="#1e8449")
        arbol.tag_configure("igual", foreground="#95a5a6")
        barra = ttk.Scrollbar(marco_lista, orient="vertical", command=arbol.yview)
        arbol.configure(yscrollcommand=barra.set)
        arbol.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        lbl_resumen = tk.Label(selector, text="Cargando la lista de la nube…", font=("Arial", 9),
                               fg="#f1c40f", bg="#2c3e50", anchor="w")
        lbl_resumen.pack(fill="x", padx=20, pady=(0, 4))
        tk.Label(selector,
                 text="Se guardan en tu carpeta de backups. Si ya tienes una copia local de ese juego, "
                      "no se borra: pasa a copia histórica con fecha. Después usa Restaurar como siempre.",
                 font=("Arial", 8), fg="#95a5a6", bg="#2c3e50", wraplength=700, justify="left",
                 anchor="w").pack(fill="x", padx=20, pady=(0, 8))

        filas = []
        marcados = set()
        visibles = []
        copia_elegida = {}    # idx -> copia de Drive elegida (si no es la más reciente)
        huellas_locales = {}  # idx -> huella del backup local (caché)
        textos_estado = {"igual": "✓ Igual que la local", "distinta": "≠ Distinta a la local",
                         "no_local": "— No está en este PC"}

        def fila_efectiva(idx):
            """La fila con la copia que se va a descargar (la elegida o la más reciente)."""
            fila = filas[idx]
            copia = copia_elegida.get(idx)
            if not copia or copia.get("id") == fila["copy"].get("id"):
                return fila
            if fila["estado"] == "no_local":
                estado = "no_local"
            else:
                if idx not in huellas_locales:
                    huellas_locales[idx] = self._huella_backup_local_rapida(fila["destino"])
                huella = str(copia.get("backup_fingerprint") or "")
                estado = "igual" if huella and huella == huellas_locales[idx] else "distinta"
            fecha_txt, _ = self._fecha_drive_a_local(copia.get("createdTime"))
            return dict(fila, copy=copia, size=int(copia.get("size", 0) or 0), estado=estado,
                        fecha=fecha_txt or str(copia.get("uploaded_at", "") or ""), antigua=True)

        def refrescar(*_):
            termino = var_busqueda.get().strip().lower()
            arbol.delete(*arbol.get_children())
            visibles.clear()
            for idx in range(len(filas)):
                fila = fila_efectiva(idx)
                if termino and termino not in fila["game"].lower():
                    continue
                visibles.append(idx)
                etiquetas = []
                if idx in marcados:
                    etiquetas.append("marcado")
                if fila["estado"] == "igual":
                    etiquetas.append("igual")
                arbol.insert("", "end", iid=str(idx), tags=tuple(etiquetas), values=(
                    "☑" if idx in marcados else "☐",
                    fila["game"] + (f"  ({fila['copies_total']} copias)" if fila["copies_total"] > 1 else ""),
                    fila["fecha"] + (" (anterior)" if fila.get("antigua") else ""),
                    self._formatear_bytes(fila["size"]), textos_estado.get(fila["estado"], ""),
                ))
            if filas:
                total = sum(fila_efectiva(i)["size"] for i in marcados)
                lbl_resumen.config(
                    text=f"{len(filas)} juego(s) en la nube · Marcados: {len(marcados)} · "
                         f"Total a descargar: {self._formatear_bytes(total)}",
                    fg="#bdc3c7")
            btn_descargar.config(state="normal" if marcados else "disabled")

        def elegir_copia(idx):
            def al_elegir(copia):
                if not selector.winfo_exists():
                    return
                copia_elegida[idx] = copia
                marcados.add(idx)
                refrescar()
            self._elegir_copia_nube(selector, filas[idx], al_elegir, copia_elegida.get(idx))

        def alternar(event):
            iid = arbol.identify_row(event.y)
            if iid:
                idx = int(iid)
                if idx in marcados:
                    marcados.discard(idx)
                    # Se recuerda por si este clic es el primero de un doble
                    # clic para cambiar la copia (ver cambiar_copia).
                    ultimo_desmarcado.update(idx=idx, copia=copia_elegida.pop(idx, None))
                elif filas[idx]["copies_total"] > 1:
                    # Varias copias: se pregunta cuál antes de marcarlo.
                    elegir_copia(idx)
                    return "break"
                else:
                    marcados.add(idx)
                refrescar()
            return "break"

        ultimo_desmarcado = {}

        def cambiar_copia(event):
            iid = arbol.identify_row(event.y)
            if iid and filas[int(iid)]["copies_total"] > 1:
                idx = int(iid)
                # El primer clic del doble clic lo desmarcó: se vuelve a marcar
                # con su copia, para que "Cancelar" en el selector no lo pierda.
                if ultimo_desmarcado.get("idx") == idx:
                    marcados.add(idx)
                    if ultimo_desmarcado.get("copia"):
                        copia_elegida[idx] = ultimo_desmarcado["copia"]
                    refrescar()
                elegir_copia(idx)
            ultimo_desmarcado.clear()
            return "break"

        def marcar_todo():
            # "Marcar todo" usa la copia más reciente; se puede cambiar con doble clic.
            marcados.update(visibles)
            refrescar()

        def desmarcar_todo():
            for idx in visibles:
                marcados.discard(idx)
                copia_elegida.pop(idx, None)
            refrescar()

        def descargar():
            elegidas = [fila_efectiva(i) for i in sorted(marcados, key=lambda i: filas[i]["game"].lower())]
            if not elegidas:
                return
            distintas = [f["game"] for f in elegidas if f["estado"] == "distinta"]
            if distintas:
                lista_txt = "\n".join("• " + n for n in distintas[:10])
                if len(distintas) > 10:
                    lista_txt += f"\n… y {len(distintas) - 10} más"
                if not mb.askyesno(
                    "Confirmar descarga",
                    "Estos juegos ya tienen una copia local distinta:\n\n" + lista_txt +
                    "\n\nTu copia local no se borra: se guardará como copia histórica con fecha "
                    "y la de la nube pasará a ser la copia actual.\n\n¿Continuar?",
                    parent=selector,
                ):
                    return
            selector.destroy()
            if ventana_nube is not None:
                try:
                    if ventana_nube.winfo_exists():
                        self._google_descartar_zips_preparados()
                        ventana_nube.destroy()
                except Exception:
                    pass
            progreso = self._ventana_progreso_descarga_nube()
            self.ejecutar_en_hilo(lambda: self._google_descargar_backups(elegidas, progreso))

        var_busqueda.trace_add("write", refrescar)
        arbol.bind("<Button-1>", alternar)
        arbol.bind("<Double-Button-1>", cambiar_copia)

        marco_acciones = tk.Frame(selector, bg="#2c3e50")
        marco_acciones.pack(fill="x", padx=20, pady=(0, 14))
        tk.Button(marco_acciones, text="Marcar todo", command=marcar_todo, bg="#16a085", fg="white",
                  bd=0, padx=12, pady=6, cursor="hand2").pack(side="left")
        tk.Button(marco_acciones, text="Desmarcar todo", command=desmarcar_todo, bg="#7f8c8d", fg="white",
                  bd=0, padx=12, pady=6, cursor="hand2").pack(side="left", padx=(8, 0))
        btn_descargar = tk.Button(marco_acciones, text="⬇ Descargar", command=descargar, bg="#27ae60",
                                  fg="white", font=("Arial", 10, "bold"), bd=0, padx=16, pady=6,
                                  cursor="hand2", state="disabled")
        btn_descargar.pack(side="right")
        tk.Button(marco_acciones, text="Cancelar", command=selector.destroy, bg="#7f8c8d", fg="white",
                  bd=0, padx=14, pady=6, cursor="hand2").pack(side="right", padx=(0, 8))

        def cargar():
            try:
                creds = self._google_obtener_credenciales(pedir_json=False)
                if creds is None:
                    raise RuntimeError("No hay una conexión válida con Google Drive.")
                datos = self._google_listar_backups_para_descarga(creds)
                error = None
            except Exception as exc:
                self._log("WARNING", "No se pudo cargar la lista de la nube: %s", exc, exc_info=True)
                datos, error = [], str(exc)

            def pintar():
                if not selector.winfo_exists():
                    return
                filas[:] = datos
                refrescar()
                if error:
                    lbl_resumen.config(text="⚠ No se pudo cargar la lista: " + error, fg="#e74c3c")
                elif not filas:
                    lbl_resumen.config(text="No hay backups en la nube todavía.", fg="#f1c40f")
            try:
                self.root.after(0, pintar)
            except Exception:
                pass

        threading.Thread(target=cargar, name="ASHCloudDownloadList", daemon=True).start()

    def _cargar_opciones_generales(self):
        """Opciones de la sección "General" (todas activadas por defecto, que
        es el comportamiento que tenía el programa antes de existir)."""
        try:
            with open(M_CFG, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception:
            datos = {}
        avisos = str(datos.get("opcion_avisos_automaticos", "Solo errores"))
        if avisos not in self.OPCIONES_AVISOS:
            avisos = "Solo errores"
        return {
            "comprobar_actualizaciones": bool(datos.get("opcion_comprobar_actualizaciones", True)),
            "mostrar_sin_datos": bool(datos.get("opcion_mostrar_sin_datos", True)),
            "mostrar_previstos": bool(datos.get("opcion_mostrar_previstos", True)),
            "mostrar_online": bool(datos.get("opcion_mostrar_online", False)),
            "avisos_automaticos": avisos,
            "verificacion_semanal": bool(datos.get("opcion_verificacion_semanal", False)),
            "verificacion_ultima": float(datos.get("opcion_verificacion_ultima", 0) or 0),
            "copia_antes_restaurar": bool(datos.get("opcion_copia_antes_restaurar", True)),
            "patrones_exclusion": str(datos.get("opcion_patrones_exclusion", "") or ""),
        }

    OPCIONES_AVISOS = ("Nunca", "Solo errores", "Siempre")

    def _patrones_exclusion(self):
        """Patrones de archivos/carpetas que no se copian al hacer backup
        (separados por ';' o ','), p. ej. "*.log; ShaderCache; *.tmp"."""
        texto = self._cargar_opciones_generales()["patrones_exclusion"]
        patrones = []
        for p in re.split(r"[;,\n]", texto):
            p = p.strip().strip('"')
            # Solo nombres/comodines: nada de rutas, para que un patrón no
            # pueda apuntar fuera de la carpeta del juego.
            if p and "/" not in p and "\\" not in p and p not in (".", ".."):
                patrones.append(p)
        return list(dict.fromkeys(patrones))

    def _notificar(self, titulo, texto, error=False):
        """Aviso no bloqueante: globo de la bandeja si ASH está en la bandeja;
        si no, una tarjeta pequeña en la esquina inferior derecha que se
        cierra sola. Se puede llamar desde cualquier hilo."""
        icono = getattr(self, "_tray_icon", None)
        if icono is not None:
            try:
                icono.notify(texto, titulo)
                return
            except Exception:
                pass

        def mostrar():
            try:
                t = tk.Toplevel(self.root)
                t.overrideredirect(True)
                t.attributes("-topmost", True)
                color = "#c0392b" if error else "#16a085"
                t.configure(bg=color)
                interior = tk.Frame(t, bg="#2c3e50")
                interior.pack(padx=(4, 0), fill="both", expand=True)
                tk.Label(interior, text=titulo, font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
                         anchor="w").pack(fill="x", padx=12, pady=(10, 2))
                tk.Label(interior, text=texto, font=("Arial", 9), fg="#ecf0f1", bg="#2c3e50",
                         wraplength=320, justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 10))
                t.update_idletasks()
                ancho, alto = max(340, t.winfo_reqwidth()), t.winfo_reqheight()
                x = t.winfo_screenwidth() - ancho - 16
                y = t.winfo_screenheight() - alto - 60
                t.geometry(f"{ancho}x{alto}+{x}+{y}")
                for w in (t, interior, *interior.winfo_children()):
                    w.bind("<Button-1>", lambda _e: t.destroy())
                t.after(9000 if error else 6000, lambda: t.winfo_exists() and t.destroy())
            except Exception as exc:
                self._log("WARNING", "No se pudo mostrar el aviso: %s", exc)

        try:
            self.root.after(0, mostrar)
        except Exception:
            pass

    def mostrar_opciones(self):
        """Muestra las opciones: General arriba; Local (izquierda) y Nube (derecha) debajo."""
        iniciar_windows, iniciar_minimizado, minimizar_en_bandeja = self._cargar_opciones_inicio()
        intervalo, dias, al_cierre, juegos_auto, _ = self._cargar_opciones_respaldos_automaticos()
        juegos_auto_periodicos, juegos_auto_cierre = self._cargar_juegos_automaticos_por_modo()
        intervalo_valor_actual, intervalo_unidad_actual, _ = self._cargar_intervalo_respaldo_automatico()
        seleccion_actual = self.get_sel_list()

        ventana = tk.Toplevel(self.root)
        ventana.title("Opciones")
        ventana.geometry("720x780")
        ventana.resizable(False, False)
        ventana.configure(bg="#2c3e50")
        ventana.transient(self.root)
        # No usamos grab_set(): Opciones es una ventana secundaria de la
        # aplicación, pero el usuario debe poder cerrar ASH desde la ventana
        # principal aunque Opciones permanezca abierta.
        self.aplicar_icono_ventana(ventana)
        self.centrar_ventana(ventana, 720, 780)

        tk.Label(
            ventana, text="⚙️ Opciones", font=("Arial", 16, "bold"),
            fg="white", bg="#2c3e50",
        ).pack(pady=(16, 10))

        var_windows = tk.BooleanVar(value=iniciar_windows)
        var_minimizado = tk.BooleanVar(value=iniciar_minimizado)
        var_bandeja = tk.BooleanVar(value=minimizar_en_bandeja)
        var_intervalo = tk.BooleanVar(value=intervalo)
        var_cierre = tk.BooleanVar(value=al_cierre)
        var_solo_idle = tk.BooleanVar(value=self._cargar_solo_idle_automatico())
        var_dias = tk.StringVar(value=str(intervalo_valor_actual))
        var_unidad_intervalo = tk.StringVar(value=intervalo_unidad_actual)
        opciones_max_backups = ["Sin límite", "1", "2", "3", "5", "10", "15", "20"]
        valor_actual_max = "Sin límite" if self.max_backups_historicos == 0 else str(self.max_backups_historicos)
        if valor_actual_max not in opciones_max_backups:
            opciones_max_backups.append(valor_actual_max)
        var_max_backups = tk.StringVar(value=valor_actual_max)

        # Opciones de subida automática a la nube. Cada modalidad tiene su
        # propia selección de juegos para que el usuario pueda decidir qué
        # juegos se suben periódicamente y cuáles al cerrar el juego.
        config_nube = self._cargar_config_nube()
        var_nube_periodica = tk.BooleanVar(value=bool(config_nube.get("auto", False)))
        var_nube_dias = tk.StringVar(value=str(config_nube.get("periodic_value", config_nube.get("dias_periodicos", 7))))
        var_nube_unidad = tk.StringVar(value=str(config_nube.get("periodic_unit", "días") or "días"))
        if var_nube_unidad.get() not in ("horas", "días", "semanas"):
            var_nube_unidad.set("días")
        var_nube_cierre = tk.BooleanVar(value=bool(config_nube.get("al_cierre", False)))
        opciones_max_copias_nube = ["Sin límite", "1", "2", "3", "5", "10", "15", "20"]
        max_nube_actual = int(config_nube.get("max_copias", 5))
        valor_actual_max_nube = "Sin límite" if max_nube_actual == 0 else str(max_nube_actual)
        if valor_actual_max_nube not in opciones_max_copias_nube:
            opciones_max_copias_nube.append(valor_actual_max_nube)
        var_max_copias_nube = tk.StringVar(value=valor_actual_max_nube)
        var_hash_solo_idle = tk.BooleanVar(value=bool(config_nube.get("hash_solo_idle", False)))
        var_hash_idle_seconds = tk.StringVar(value=str(int(config_nube.get("hash_idle_seconds", 300) or 300) // 60))
        var_anti_corrupcion = tk.BooleanVar(value=bool(config_nube.get("anti_corrupcion", False)))
        var_anti_corrupcion_pct = tk.StringVar(value=str(int(config_nube.get("anti_corrupcion_pct", 30) or 30)))
        var_limite_subida = tk.StringVar(value=str(int(config_nube.get("upload_limit_kbps", 0) or 0)))
        var_no_red_medida = tk.BooleanVar(value=bool(config_nube.get("no_subir_red_medida", False)))
        var_compresion = tk.StringVar(value=str(config_nube.get("compresion", "Rápido") or "Rápido"))
        if var_compresion.get() not in ("Rápido", "Equilibrado", "Máximo"):
            var_compresion.set("Rápido")
        var_obs_pause = tk.BooleanVar(value=bool(config_nube.get("obs_pause_streaming", False)))
        # La nube usa la misma lógica de exclusión que los respaldos locales:
        # todos los juegos están incluidos por defecto y el selector solo guarda
        # las excepciones que el usuario decide excluir. Se migra de forma
        # transparente la configuración antigua, que guardaba juegos incluidos.
        juegos_disponibles_nube = [j for j, r in self.juegos.items() if r]
        juegos_disponibles_nube = list(dict.fromkeys(juegos_disponibles_nube))
        disponibles_nube_set = set(juegos_disponibles_nube)

        exclusiones_nube_configuradas = bool(config_nube.get("exclusiones_configuradas", False))

        def cargar_incluidos_nube(clave_excluidos, clave_incluidos):
            # Sin configuración previa, todos los juegos están incluidos.
            # Evita que restos de versiones antiguas aparezcan como
            # "todos excluidos" al actualizar ASH.
            if not exclusiones_nube_configuradas:
                return list(juegos_disponibles_nube)

            if clave_excluidos in config_nube:
                excluidos = config_nube.get(clave_excluidos, []) or []
                excluidos = {str(x) for x in excluidos if str(x).strip()}
                return [j for j in juegos_disponibles_nube if j not in excluidos]
            antiguos = config_nube.get(clave_incluidos, None)
            if isinstance(antiguos, list) and antiguos:
                antiguos = {str(x) for x in antiguos if str(x).strip()}
                return [j for j in juegos_disponibles_nube if j in antiguos]
            return list(juegos_disponibles_nube)

        juegos_nube_periodicos = cargar_incluidos_nube(
            "juegos_periodicos_excluidos", "juegos_periodicos"
        )
        juegos_nube_cierre = cargar_incluidos_nube(
            "juegos_cierre_excluidos", "juegos_cierre"
        )

        # ---------------------------------------------------------------
        # Distribución: "General" arriba (a lo ancho); debajo, dos columnas:
        # "💾 Local" a la izquierda y "☁ Nube" a la derecha.
        # ---------------------------------------------------------------
        opciones_generales = self._cargar_opciones_generales()
        var_comprobar_updates = tk.BooleanVar(value=opciones_generales["comprobar_actualizaciones"])
        var_lista_sin_datos = tk.BooleanVar(value=opciones_generales["mostrar_sin_datos"])
        var_lista_previstos = tk.BooleanVar(value=opciones_generales["mostrar_previstos"])
        var_lista_online = tk.BooleanVar(value=opciones_generales["mostrar_online"])
        var_avisos = tk.StringVar(value=opciones_generales["avisos_automaticos"])
        var_verificacion_semanal = tk.BooleanVar(value=opciones_generales["verificacion_semanal"])
        var_copia_antes_restaurar = tk.BooleanVar(value=opciones_generales["copia_antes_restaurar"])
        var_patrones = tk.StringVar(value=opciones_generales["patrones_exclusion"])

        def subtitulo(padre, texto):
            tk.Label(padre, text=texto, font=("Arial", 10, "bold"), fg="#1abc9c",
                     bg="#2c3e50").pack(anchor="w", padx=12, pady=(8, 2))

        def casilla(padre, texto, variable, negrita=False, **pack):
            chk = tk.Checkbutton(
                padre, text=texto, variable=variable,
                font=("Arial", 10, "bold" if negrita else "normal"), fg="white", bg="#2c3e50",
                activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
                anchor="w", justify="left",
            )
            chk.pack(**({"anchor": "w", "padx": 12, "pady": (0, 4)} | pack))
            return chk

        marco_general = tk.LabelFrame(
            ventana, text="General", font=("Arial", 10, "bold"),
            fg="white", bg="#2c3e50", bd=1, relief="groove",
        )
        marco_general.pack(fill="x", padx=22, pady=(0, 10))
        marco_general.columnconfigure(0, weight=1, uniform="general")
        marco_general.columnconfigure(1, weight=1, uniform="general")
        marco_inicio = tk.Frame(marco_general, bg="#2c3e50")
        marco_inicio.grid(row=0, column=0, sticky="nw")
        marco_general_der = tk.Frame(marco_general, bg="#2c3e50")
        marco_general_der.grid(row=0, column=1, sticky="nw")
        subtitulo(marco_inicio, "Inicio")

        tk.Checkbutton(
            marco_inicio, text="Abrir Arlequin SaveHub con Windows", variable=var_windows,
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(anchor="w", padx=12, pady=5)
        chk_minimizado = tk.Checkbutton(
            marco_inicio, text="Abrir minimizado cuando inicie Windows", variable=var_minimizado,
            font=("Arial", 10), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        )
        chk_minimizado.pack(anchor="w", padx=12, pady=(0, 5))

        def actualizar_estado_minimizado(*_):
            if var_windows.get():
                chk_minimizado.configure(state="normal")
            else:
                var_minimizado.set(False)
                chk_minimizado.configure(state="disabled")

        var_windows.trace_add("write", actualizar_estado_minimizado)
        actualizar_estado_minimizado()

        tk.Checkbutton(
            marco_inicio, text="Ocultar en la bandeja del sistema al minimizar", variable=var_bandeja,
            font=("Arial", 10), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(anchor="w", padx=12, pady=(0, 4))
        casilla(marco_inicio, "Comprobar si hay una versión nueva al iniciar", var_comprobar_updates,
                pady=(0, 8))

        subtitulo(marco_general_der, "Lista y rendimiento")
        casilla(marco_general_der, "Mostrar juegos instalados sin save conocido", var_lista_sin_datos)
        casilla(marco_general_der, "Mostrar juegos a la espera de su primer uso", var_lista_previstos)
        casilla(marco_general_der, "Mostrar juegos 100% online (progreso en el servidor)", var_lista_online)

        fila_avisos = tk.Frame(marco_inicio, bg="#2c3e50")
        fila_avisos.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(fila_avisos, text="Avisos de tareas automáticas:", font=("Arial", 10),
                 fg="white", bg="#2c3e50").pack(side="left")
        ttk.Combobox(fila_avisos, textvariable=var_avisos, values=self.OPCIONES_AVISOS,
                     state="readonly", width=12, font=("Arial", 9)).pack(side="left", padx=(8, 0))

        # Dos columnas: Local (izquierda) y Nube (derecha).
        columnas = tk.Frame(ventana, bg="#2c3e50")
        columnas.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        columnas.columnconfigure(0, weight=1, uniform="columnas")
        columnas.columnconfigure(1, weight=1, uniform="columnas")
        columnas.rowconfigure(0, weight=1)

        marco_auto = tk.LabelFrame(
            columnas, text="💾 Local", font=("Arial", 10, "bold"),
            fg="white", bg="#2c3e50", bd=1, relief="groove",
        )
        marco_auto.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        subtitulo(marco_auto, "Respaldos automáticos")

        fila_periodico_local = tk.Frame(marco_auto, bg="#2c3e50")
        fila_periodico_local.pack(fill="x", padx=12, pady=(2, 2))
        fila_periodico_local_excl = tk.Frame(marco_auto, bg="#2c3e50")
        fila_periodico_local_excl.pack(fill="x", padx=34, pady=(0, 4))
        tk.Checkbutton(
            fila_periodico_local, text="Hacer un respaldo cada", variable=var_intervalo,
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(side="left")
        tk.Spinbox(
            fila_periodico_local, from_=1, to=10000, textvariable=var_dias, width=5,
            font=("Arial", 10), justify="center",
        ).pack(side="left", padx=(8, 5))
        ttk.Combobox(
            fila_periodico_local, textvariable=var_unidad_intervalo,
            values=("horas", "días", "semanas"), state="readonly", width=8,
            font=("Arial", 9),
        ).pack(side="left")

        def seleccionar_juegos_automaticos(modo="periodicos"):
            """Selector independiente para los juegos de cada modalidad local."""
            lista_objetivo = juegos_auto_periodicos if modo == "periodicos" else juegos_auto_cierre
            # En este selector se marcan los juegos que se QUIEREN EXCLUIR.
            # Internamente seguimos guardando la lista de incluidos para que
            # el resto del sistema pueda trabajar con todos los juegos por defecto.
            seleccionados_local = set()
            selector = tk.Toplevel(ventana)
            selector.title("Seleccionar juegos para respaldo automático")
            selector.geometry("680x660")
            selector.resizable(False, True)
            selector.configure(bg="#2c3e50")
            selector.transient(ventana)
            selector.grab_set()
            self.aplicar_icono_ventana(selector)
            self.centrar_ventana(selector, 680, 660)

            titulo_modo = "respaldo periódico" if modo == "periodicos" else "respaldo al cerrar el juego"
            tk.Label(selector, text=f"Excluir juegos del {titulo_modo}",
                     font=("Arial", 12, "bold"), fg="white", bg="#2c3e50").pack(pady=(14, 4))
            tk.Label(selector, text="Los juegos marcados se excluirán de este modo.",
                     font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50").pack(pady=(0, 10))

            marco_busqueda = tk.Frame(selector, bg="#2c3e50")
            marco_busqueda.pack(fill="x", padx=20, pady=(0, 8))
            tk.Label(marco_busqueda, text="Buscar:", font=("Arial", 10, "bold"),
                     fg="white", bg="#2c3e50").pack(side="left")
            var_busqueda = tk.StringVar()
            entrada_busqueda = tk.Entry(marco_busqueda, textvariable=var_busqueda, font=("Arial", 10))
            entrada_busqueda.pack(side="left", padx=(8, 0), fill="x", expand=True)

            juegos_disponibles = sorted(
                [clave for clave, ruta in self.juegos.items() if ruta],
                key=lambda x: self.limpiar_nombre_juego(x).lower(),
            )
            # Todo juego está incluido por defecto; los marcados aquí son las excepciones.
            seleccionados_local = set(juegos_disponibles) - set(lista_objetivo)

            filas_visibles = []
            marco_lista = tk.Frame(selector, bg="#2c3e50")
            marco_lista.pack(fill="both", expand=True, padx=20, pady=(0, 10))
            lista = tk.Listbox(marco_lista, font=("Arial", 11), bg="#34495e", fg="white",
                               selectbackground="#34495e", selectforeground="white",
                               activestyle="none", exportselection=False)
            barra = tk.Scrollbar(marco_lista, orient="vertical", command=lista.yview)
            lista.configure(yscrollcommand=barra.set)
            lista.pack(side="left", fill="both", expand=True)
            barra.pack(side="right", fill="y")

            def actualizar_lista(*_):
                termino = var_busqueda.get().strip().lower()
                lista.delete(0, tk.END)
                filas_visibles.clear()
                for clave in juegos_disponibles:
                    nombre = self.limpiar_nombre_juego(clave)
                    if termino and termino not in nombre.lower():
                        continue
                    filas_visibles.append(clave)
                    marcado = clave in seleccionados_local
                    lista.insert(tk.END, ("☒ " if marcado else "☐ ") + nombre)
                    lista.itemconfig(tk.END, background="#c0392b" if marcado else "#34495e", foreground="white")
                lista.selection_clear(0, tk.END)

            def alternar(event):
                idx = lista.nearest(event.y)
                if 0 <= idx < len(filas_visibles):
                    clave = filas_visibles[idx]
                    if clave in seleccionados_local:
                        seleccionados_local.remove(clave)
                    else:
                        seleccionados_local.add(clave)
                    actualizar_lista()
                return "break"

            def marcar_todo():
                # Marcar = excluir. Solo afecta a los resultados visibles de la búsqueda.
                seleccionados_local.update(filas_visibles)
                actualizar_lista()

            def desmarcar_todo():
                # Desmarcar = volver a incluir.
                for clave in filas_visibles:
                    seleccionados_local.discard(clave)
                actualizar_lista()

            def guardar_selector():
                incluidos = [
                    clave for clave in juegos_disponibles
                    if clave not in seleccionados_local
                ]
                lista_objetivo[:] = sorted(incluidos, key=lambda x: self.limpiar_nombre_juego(x).lower())
                actualizar_boton_excluidos_local()
                actualizar_boton_excluidos_cierre()
                selector.destroy()

            var_busqueda.trace_add("write", actualizar_lista)
            lista.bind("<Button-1>", alternar)

            marco_acciones = tk.Frame(selector, bg="#2c3e50")
            marco_acciones.pack(fill="x", padx=20, pady=(0, 8))
            tk.Button(marco_acciones, text="Excluir todo", command=marcar_todo,
                      bg="#e74c3c", fg="white", bd=0, padx=12, pady=5, cursor="hand2").pack(side="left")
            tk.Button(marco_acciones, text="No excluir ninguno", command=desmarcar_todo,
                      bg="#3498db", fg="white", bd=0, padx=12, pady=5, cursor="hand2").pack(side="left", padx=8)

            marco_final = tk.Frame(selector, bg="#2c3e50")
            marco_final.pack(fill="x", padx=20, pady=(0, 14))
            tk.Button(marco_final, text="Guardar", command=guardar_selector,
                      bg="#2ecc71", fg="white", font=("Arial", 10, "bold"), bd=0, padx=18, pady=6, cursor="hand2").pack(side="left")
            tk.Button(marco_final, text="Cancelar", command=selector.destroy,
                      bg="#7f8c8d", fg="white", font=("Arial", 10), bd=0, padx=18, pady=6, cursor="hand2").pack(side="right")

            actualizar_lista()
            entrada_busqueda.focus_set()

        def actualizar_boton_excluidos_local():
            disponibles = [j for j, r in self.juegos.items() if r]
            excluidos = max(0, len(disponibles) - len(juegos_auto_periodicos))
            boton_excluidos_periodicos.config(text=f"{excluidos} juego(s) excluidos")

        def actualizar_boton_excluidos_cierre():
            disponibles = [j for j, r in self.juegos.items() if r]
            excluidos = max(0, len(disponibles) - len(juegos_auto_cierre))
            boton_excluidos_cierre.config(text=f"{excluidos} juego(s) excluidos")

        def abrir_selector_periodicos():
            seleccionar_juegos_automaticos("periodicos")

        boton_excluidos_periodicos = tk.Button(
            fila_periodico_local_excl, text="0 juego(s) excluidos", command=abrir_selector_periodicos,
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2",
        )
        boton_excluidos_periodicos.pack(side="left")

        tk.Checkbutton(
            marco_auto, text="Ejecutar solo si el PC está inactivo (Idle)", variable=var_solo_idle,
            font=("Arial", 9), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(anchor="w", padx=34, pady=(0, 4))
        tk.Label(
            marco_auto, text="Solo afecta al respaldo periódico; si estás usando el PC, se aplaza.",
            font=("Arial", 8), fg="#95a5a6", bg="#2c3e50", wraplength=380, justify="left",
        ).pack(anchor="w", padx=55, pady=(0, 5))

        fila_cierre_local = tk.Frame(marco_auto, bg="#2c3e50")
        fila_cierre_local.pack(fill="x", padx=12, pady=(5, 8))
        tk.Checkbutton(
            fila_cierre_local, text="Respaldar juegos cuando se cierren", variable=var_cierre,
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(side="left")
        boton_excluidos_cierre = tk.Button(
            fila_cierre_local, text="0 juego(s) excluidos",
            command=lambda: seleccionar_juegos_automaticos("cierre"),
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2",
        )
        boton_excluidos_cierre.pack(side="left", padx=(10, 0))

        subtitulo(marco_auto, "Copias")
        fila_max_backups = tk.Frame(marco_auto, bg="#2c3e50")
        fila_max_backups.pack(fill="x", padx=12, pady=(0, 2))
        tk.Label(
            fila_max_backups, text="Máximo de copias por juego:",
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
        ).pack(side="left", padx=(0, 8))
        menu_max_backups = tk.OptionMenu(
            fila_max_backups, var_max_backups, *opciones_max_backups
        )
        menu_max_backups.config(
            bg="#34495e", fg="white", font=("Arial", 10, "bold"),
            bd=0, highlightthickness=0, cursor="hand2",
            activebackground="#1abc9c", activeforeground="white",
        )
        menu_max_backups["menu"].config(bg="#34495e", fg="white", font=("Arial", 10))
        menu_max_backups.pack(side="left")
        tk.Label(
            marco_auto, text="Sin límite = conservar todas las copias históricas.",
            font=("Arial", 8), fg="#bdc3c7", bg="#2c3e50",
        ).pack(anchor="w", padx=12, pady=(0, 4))
        casilla(marco_auto, "Guardar lo que había antes de restaurar (para deshacer)",
                var_copia_antes_restaurar)
        casilla(marco_auto, "Comprobar la integridad de las copias cada semana",
                var_verificacion_semanal)
        tk.Label(marco_auto, text="Se hace con el PC inactivo; solo avisa si encuentra problemas.",
                 font=("Arial", 8), fg="#95a5a6", bg="#2c3e50").pack(anchor="w", padx=34, pady=(0, 4))

        subtitulo(marco_auto, "No copiar estos archivos o carpetas")
        tk.Entry(marco_auto, textvariable=var_patrones, font=("Arial", 10),
                 bg="#34495e", fg="white", insertbackground="white", relief="flat").pack(
            fill="x", padx=12, pady=(0, 2), ipady=3)
        tk.Label(marco_auto,
                 text="Separados por ; — ejemplo: *.log; *.tmp; ShaderCache; Crashes\n"
                      "Ocupan menos, pero al restaurar esos archivos no se recuperan.",
                 font=("Arial", 8), fg="#95a5a6", bg="#2c3e50", justify="left").pack(anchor="w", padx=12, pady=(0, 6))

        tk.Label(
            marco_auto,
            text="El modo de cierre solo actúa tras detectar ABIERTO → CERRADO. Antes de copiar, ASH comprueba los eventos recientes de Windows para intentar detectar un crash; si lo detecta, protege el último backup válido y no copia el save sospechoso.\n"
                 "Si un juego está abierto cuando toca el respaldo periódico, se espera a que esté cerrado.",
            font=("Arial", 8), fg="#95a5a6", bg="#2c3e50", wraplength=400, justify="left",
        ).pack(anchor="w", padx=12, pady=(4, 10))

        def seleccionar_juegos_nube(lista_actual, titulo):
            """Selector por EXCLUSIÓN para una modalidad concreta de nube."""
            juegos_disponibles = sorted(
                [clave for clave, ruta in self.juegos.items() if ruta],
                key=lambda x: self.limpiar_nombre_juego(x).lower(),
            )
            excluidos_local = set(juegos_disponibles) - set(lista_actual)

            selector = tk.Toplevel(ventana)
            selector.title(titulo)
            selector.geometry("680x660")
            selector.resizable(False, True)
            selector.configure(bg="#2c3e50")
            selector.transient(ventana)
            selector.grab_set()
            self.aplicar_icono_ventana(selector)
            self.centrar_ventana(selector, 680, 660)

            tk.Label(
                selector, text="Excluir juegos de esta subida automática",
                font=("Arial", 12, "bold"), fg="white", bg="#2c3e50",
            ).pack(pady=(14, 4))
            tk.Label(
                selector, text="Los juegos marcados se excluirán. Los demás se subirán automáticamente.",
                font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50",
            ).pack(pady=(0, 10))

            marco_busqueda = tk.Frame(selector, bg="#2c3e50")
            marco_busqueda.pack(fill="x", padx=20, pady=(0, 8))
            tk.Label(marco_busqueda, text="Buscar:", font=("Arial", 10, "bold"),
                     fg="white", bg="#2c3e50").pack(side="left")
            var_busqueda_nube = tk.StringVar()
            entrada_busqueda = tk.Entry(marco_busqueda, textvariable=var_busqueda_nube,
                                         font=("Arial", 10), width=55)
            entrada_busqueda.pack(side="left", padx=(8, 0), fill="x", expand=True)

            filas_visibles = []
            marco_lista = tk.Frame(selector, bg="#2c3e50")
            marco_lista.pack(fill="both", expand=True, padx=20, pady=(0, 10))
            lista = tk.Listbox(
                marco_lista, font=("Arial", 11),
                bg="#34495e", fg="white", selectbackground="#34495e",
                selectforeground="white", activestyle="none", exportselection=False,
            )
            barra = tk.Scrollbar(marco_lista, orient="vertical", command=lista.yview)
            lista.configure(yscrollcommand=barra.set)
            lista.pack(side="left", fill="both", expand=True)
            barra.pack(side="right", fill="y")

            def actualizar_lista_nube(*_):
                termino = var_busqueda_nube.get().strip().lower()
                lista.delete(0, tk.END)
                filas_visibles.clear()
                for clave in juegos_disponibles:
                    nombre = self.limpiar_nombre_juego(clave)
                    if termino and termino not in nombre.lower():
                        continue
                    filas_visibles.append(clave)
                    marcado = clave in excluidos_local
                    lista.insert(tk.END, ("☒ " if marcado else "☐ ") + nombre)
                    lista.itemconfig(
                        tk.END, background="#c0392b" if marcado else "#34495e",
                        foreground="white"
                    )
                lista.selection_clear(0, tk.END)

            def alternar_nube(event):
                idx = lista.nearest(event.y)
                if 0 <= idx < len(filas_visibles):
                    clave = filas_visibles[idx]
                    if clave in excluidos_local:
                        excluidos_local.remove(clave)
                    else:
                        excluidos_local.add(clave)
                    actualizar_lista_nube()
                return "break"

            def excluir_todo():
                excluidos_local.update(filas_visibles)
                actualizar_lista_nube()

            def no_excluir_ninguno():
                for clave in filas_visibles:
                    excluidos_local.discard(clave)
                actualizar_lista_nube()

            def guardar_nube():
                incluidos = [
                    clave for clave in juegos_disponibles
                    if clave not in excluidos_local
                ]
                lista_actual[:] = sorted(
                    incluidos, key=lambda x: self.limpiar_nombre_juego(x).lower()
                )
                try:
                    actualizar_excluidos_nube()
                except Exception:
                    pass
                selector.destroy()

            var_busqueda_nube.trace_add("write", actualizar_lista_nube)
            lista.bind("<Button-1>", alternar_nube)

            marco_acciones = tk.Frame(selector, bg="#2c3e50")
            marco_acciones.pack(fill="x", padx=20, pady=(0, 8))
            tk.Button(
                marco_acciones, text="Excluir todo", command=excluir_todo,
                bg="#e74c3c", fg="white", bd=0, padx=12, pady=5, cursor="hand2"
            ).pack(side="left")
            tk.Button(
                marco_acciones, text="No excluir ninguno", command=no_excluir_ninguno,
                bg="#3498db", fg="white", bd=0, padx=12, pady=5, cursor="hand2"
            ).pack(side="left", padx=8)

            marco_final = tk.Frame(selector, bg="#2c3e50")
            marco_final.pack(fill="x", padx=20, pady=(0, 14))
            tk.Button(
                marco_final, text="Guardar", command=guardar_nube,
                bg="#2ecc71", fg="white", font=("Arial", 10, "bold"),
                bd=0, padx=18, pady=6, cursor="hand2"
            ).pack(side="left")
            tk.Button(
                marco_final, text="Cancelar", command=selector.destroy,
                bg="#7f8c8d", fg="white", font=("Arial", 10),
                bd=0, padx=18, pady=6, cursor="hand2"
            ).pack(side="right")

            actualizar_lista_nube()
            entrada_busqueda.focus_set()

        # ---------------------------------------------------------------
        # Opciones de nube
        # La configuración de cuenta, conexión y espacio se muestra
        # exclusivamente en la ventana ☁ Nube. Aquí dejamos únicamente
        # el encabezado de las futuras opciones de subida.
        # ---------------------------------------------------------------
        marco_nube = tk.LabelFrame(
            columnas, text="☁ Nube", font=("Arial", 10, "bold"),
            fg="white", bg="#2c3e50", bd=1, relief="groove",
        )
        marco_nube.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        subtitulo(marco_nube, "Subidas automáticas")

        fila_nube_periodica = tk.Frame(marco_nube, bg="#2c3e50")
        fila_nube_periodica.pack(fill="x", padx=12, pady=(2, 2))
        fila_nube_periodica_excl = tk.Frame(marco_nube, bg="#2c3e50")
        fila_nube_periodica_excl.pack(fill="x", padx=34, pady=(0, 4))
        tk.Checkbutton(
            fila_nube_periodica, text="Subir cada", variable=var_nube_periodica,
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(side="left")
        tk.Spinbox(
            fila_nube_periodica, from_=1, to=10000, textvariable=var_nube_dias, width=5,
            font=("Arial", 10), justify="center",
        ).pack(side="left", padx=(5, 5))
        ttk.Combobox(
            fila_nube_periodica, textvariable=var_nube_unidad,
            values=("horas", "días", "semanas"), state="readonly", width=8,
            font=("Arial", 9),
        ).pack(side="left", padx=(0, 8))
        boton_nube_excluidos_periodicos = tk.Button(
            fila_nube_periodica_excl, text="0 juego(s) excluidos",
            command=lambda: seleccionar_juegos_nube(juegos_nube_periodicos, "Juegos — subida automática periódica"),
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2",
        )
        boton_nube_excluidos_periodicos.pack(side="left")

        fila_nube_cierre = tk.Frame(marco_nube, bg="#2c3e50")
        fila_nube_cierre.pack(fill="x", padx=12, pady=(5, 8))
        tk.Checkbutton(
            fila_nube_cierre, text="Subir al cerrar el juego", variable=var_nube_cierre,
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
            activebackground="#2c3e50", activeforeground="white", selectcolor="#34495e",
        ).pack(side="left")
        boton_nube_excluidos_cierre = tk.Button(
            fila_nube_cierre, text="0 juego(s) excluidos",
            command=lambda: seleccionar_juegos_nube(juegos_nube_cierre, "Juegos — subida al cerrar el juego"),
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2",
        )
        boton_nube_excluidos_cierre.pack(side="left", padx=(12, 0))

        subtitulo(marco_nube, "Copias")
        fila_max_nube = tk.Frame(marco_nube, bg="#2c3e50")
        fila_max_nube.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(
            fila_max_nube, text="Máximo de copias por juego:",
            font=("Arial", 10, "bold"), fg="white", bg="#2c3e50",
        ).pack(side="left", padx=(0, 8))
        menu_max_copias_nube = tk.OptionMenu(
            fila_max_nube, var_max_copias_nube, *opciones_max_copias_nube
        )
        menu_max_copias_nube.config(
            bg="#34495e", fg="white", font=("Arial", 10, "bold"),
            bd=0, highlightthickness=0, cursor="hand2",
        )
        menu_max_copias_nube["menu"].config(
            bg="#34495e", fg="white", font=("Arial", 10),
        )
        menu_max_copias_nube.pack(side="left")

        def actualizar_excluidos_nube():
            disponibles = [j for j, r in self.juegos.items() if r]
            boton_nube_excluidos_periodicos.config(text=f"{max(0, len(disponibles) - len(juegos_nube_periodicos))} juego(s) excluidos")
            boton_nube_excluidos_cierre.config(text=f"{max(0, len(disponibles) - len(juegos_nube_cierre))} juego(s) excluidos")

        actualizar_boton_excluidos_local()
        actualizar_boton_excluidos_cierre()
        actualizar_excluidos_nube()

        # --- General (columna derecha): SHA-256 lo usan tanto los backups
        # locales como la nube, por eso va en "General".
        casilla(marco_general_der, "Aplazar SHA-256 hasta que el PC esté inactivo", var_hash_solo_idle,
                pady=(4, 2))
        fila_hash = tk.Frame(marco_general_der, bg="#2c3e50")
        fila_hash.pack(fill="x", padx=34, pady=(0, 8))
        tk.Label(fila_hash, text="Esperar", font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50").pack(side="left")
        tk.Spinbox(fila_hash, from_=1, to=120, textvariable=var_hash_idle_seconds, width=5, font=("Arial", 9), justify="center").pack(side="left", padx=6)
        tk.Label(fila_hash, text="min de inactividad antes de calcular hashes", font=("Arial", 9), fg="#bdc3c7", bg="#2c3e50").pack(side="left")

        # --- Nube: red, compresión y protecciones.
        subtitulo(marco_nube, "Red y compresión")
        fila_red = tk.Frame(marco_nube, bg="#2c3e50")
        fila_red.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(fila_red, text="Límite de subida (KB/s):", font=("Arial", 9, "bold"), fg="white", bg="#2c3e50").pack(side="left")
        tk.Spinbox(fila_red, from_=0, to=1048576, textvariable=var_limite_subida, width=8, font=("Arial", 9), justify="center").pack(side="left", padx=6)
        tk.Label(fila_red, text="0 = sin límite", font=("Arial", 8), fg="#bdc3c7", bg="#2c3e50").pack(side="left")
        casilla(marco_nube, "No subir con conexiones de uso medido", var_no_red_medida)

        fila_comp = tk.Frame(marco_nube, bg="#2c3e50")
        fila_comp.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(fila_comp, text="Compresión ZIP:", font=("Arial", 9, "bold"), fg="white", bg="#2c3e50").pack(side="left")
        menu_comp = tk.OptionMenu(fila_comp, var_compresion, "Rápido", "Equilibrado", "Máximo")
        menu_comp.config(bg="#34495e", fg="white", font=("Arial", 9, "bold"), bd=0, highlightthickness=0)
        menu_comp["menu"].config(bg="#34495e", fg="white", font=("Arial", 9))
        menu_comp.pack(side="left", padx=8)
        tk.Label(fila_comp, text="Rápido = menos CPU · Máximo = menos tamaño", font=("Arial", 8), fg="#bdc3c7", bg="#2c3e50").pack(side="left")

        subtitulo(marco_nube, "Protección")
        fila_seg = tk.Frame(marco_nube, bg="#2c3e50")
        fila_seg.pack(fill="x", padx=12, pady=(0, 0))
        tk.Checkbutton(
            fila_seg, text="Bloquear subida si el tamaño cambia más de", variable=var_anti_corrupcion,
            font=("Arial", 9, "bold"), fg="white", bg="#2c3e50", activebackground="#2c3e50",
            activeforeground="white", selectcolor="#34495e",
        ).pack(side="left")
        tk.Spinbox(fila_seg, from_=1, to=500, textvariable=var_anti_corrupcion_pct, width=5, font=("Arial", 9), justify="center").pack(side="left", padx=5)
        tk.Label(fila_seg, text="%", font=("Arial", 9, "bold"), fg="white", bg="#2c3e50").pack(side="left")
        tk.Label(marco_nube, text="Respecto a la copia anterior: evita subir un save que parece dañado.",
                 font=("Arial", 8), fg="#95a5a6", bg="#2c3e50", wraplength=380,
                 justify="left").pack(anchor="w", padx=34, pady=(0, 6))

        casilla(marco_nube, "No subir a la nube mientras OBS esté abierto", var_obs_pause)
        tk.Label(marco_nube, text="Grabando o transmitiendo: no gasta red ni disco durante la sesión.",
                 font=("Arial", 8), fg="#95a5a6", bg="#2c3e50", wraplength=380,
                 justify="left").pack(anchor="w", padx=34, pady=(0, 10))

        marco_botones = tk.Frame(ventana, bg="#2c3e50")
        marco_botones.pack(fill="x", padx=20, pady=(0, 5))

        def guardar():
            try:
                nuevo_dias = max(1, int(var_dias.get()))
            except Exception:
                mb.showerror("Opciones", "El intervalo debe ser un número entero mayor que 0.", parent=ventana)
                return

            # La selección de la interfaz representa los juegos INCLUIDOS.
            # Al guardar convertimos esa selección en una lista de EXCLUSIONES: 
            # si se activa el modo, todos entran por defecto y solo se guardan
            # los juegos que el usuario haya quitado desde su botón rojo.
            disponibles_config = [j for j, r in self.juegos.items() if r]
            incluidos_periodicos = set(juegos_auto_periodicos)
            incluidos_cierre = set(juegos_auto_cierre)
            excluidos_periodicos = sorted(
                [j for j in disponibles_config if j not in incluidos_periodicos],
                key=lambda x: self.limpiar_nombre_juego(x).lower(),
            )
            excluidos_cierre = sorted(
                [j for j in disponibles_config if j not in incluidos_cierre],
                key=lambda x: self.limpiar_nombre_juego(x).lower(),
            )
            juegos_periodicos_guardar = list(dict.fromkeys(juegos_auto_periodicos))
            juegos_cierre_guardar = list(dict.fromkeys(juegos_auto_cierre))
            nuevos_juegos = list(dict.fromkeys(juegos_periodicos_guardar + juegos_cierre_guardar))
            # Una lista vacía de incluidos es válida: significa que el usuario
            # ha excluido todos los juegos para ese modo.

            # "Abrir minimizado" solo puede estar activo si ASH se inicia con Windows.
            if not var_windows.get():
                var_minimizado.set(False)
            if not self._guardar_opciones_inicio(bool(var_windows.get()), bool(var_minimizado.get()), bool(var_bandeja.get())):
                mb.showerror("Opciones", "No se pudieron guardar las opciones de inicio.", parent=ventana)
                return
            if not self._actualizar_inicio_windows(bool(var_windows.get()), bool(var_minimizado.get())):
                mb.showerror("Opciones", "No se pudo actualizar el inicio automático de Windows.", parent=ventana)
                return

            self.minimizar_en_bandeja = bool(var_bandeja.get())

            # Si cambia la lista de juegos, conservamos los últimos backups de
            # los juegos que siguen configurados y descartamos los demás.
            _, _, _, _, ultimos_actuales = self._cargar_opciones_respaldos_automaticos()
            ultimos_actuales = {k: v for k, v in ultimos_actuales.items() if k in nuevos_juegos}
            if var_intervalo.get():
                ahora_configuracion = time.time()
                for juego in nuevos_juegos:
                    ultimos_actuales.setdefault(juego, ahora_configuracion)

            nuevo_max_backups = 0 if var_max_backups.get() == "Sin límite" else int(var_max_backups.get())
            self.max_backups_historicos = nuevo_max_backups
            self._guardar_max_backups(nuevo_max_backups)

            try:
                valor_nube = max(1, int(var_nube_dias.get()))
            except Exception:
                mb.showerror("Opciones", "El intervalo de subida a la nube debe ser un número entero mayor que 0.", parent=ventana)
                return

            # Guardamos las dos listas por separado. Se conserva también
            # cloud_auto_upload por compatibilidad con el sistema de subida
            # existente: ahora representa la modalidad periódica.
            nuevo_max_copias_nube = 0 if var_max_copias_nube.get() == "Sin límite" else int(var_max_copias_nube.get())

            self._guardar_config_nube(
                cloud_exclusion_configured=True,
                cloud_auto_upload=bool(var_nube_periodica.get()),
                cloud_upload_when="Cada X días",
                cloud_upload_periodic_days=(valor_nube if var_nube_unidad.get() == "días" else max(1, int(round(valor_nube * ({"horas": 1/24, "semanas": 7}[var_nube_unidad.get()]))))),
                cloud_upload_periodic_value=valor_nube,
                cloud_upload_periodic_unit=var_nube_unidad.get(),
                cloud_upload_on_close=bool(var_nube_cierre.get()),
                cloud_max_copias=nuevo_max_copias_nube,
                cloud_upload_limit_kbps=max(0, int(var_limite_subida.get())),
                cloud_no_upload_metered=bool(var_no_red_medida.get()),
                cloud_compression=var_compresion.get(),
                hash_solo_idle=bool(var_hash_solo_idle.get()),
                hash_idle_seconds=max(30, int(var_hash_idle_seconds.get()) * 60),
                cloud_anti_corruption=bool(var_anti_corrupcion.get()),
                cloud_anti_corruption_pct=max(1, int(var_anti_corrupcion_pct.get())),
                obs_pause_streaming=bool(var_obs_pause.get()),  # ahora significa "OBS abierto"
                cloud_periodic_games=list(dict.fromkeys(juegos_nube_periodicos)),
                cloud_close_games=list(dict.fromkeys(juegos_nube_cierre)),
                cloud_periodic_games_excluded=sorted(
                    [j for j in disponibles_config if j not in set(juegos_nube_periodicos)],
                    key=lambda x: self.limpiar_nombre_juego(x).lower(),
                ),
                cloud_close_games_excluded=sorted(
                    [j for j in disponibles_config if j not in set(juegos_nube_cierre)],
                    key=lambda x: self.limpiar_nombre_juego(x).lower(),
                ),
            )

            factores = {"horas": 3600, "días": 86400, "semanas": 604800}
            intervalo_segundos = max(1, int(var_dias.get())) * factores[var_unidad_intervalo.get()]
            nuevo_dias_legacy = max(1, int(round(intervalo_segundos / 86400)))
            if not self._guardar_opciones_respaldos_automaticos(
                bool(var_intervalo.get()), nuevo_dias_legacy, bool(var_cierre.get()),
                nuevos_juegos, ultimos_actuales, solo_idle=bool(var_solo_idle.get()),
                juegos_periodicos=juegos_periodicos_guardar, juegos_cierre=juegos_cierre_guardar,
                juegos_periodicos_excluidos=excluidos_periodicos,
                juegos_cierre_excluidos=excluidos_cierre,
                intervalo_valor=int(var_dias.get()), intervalo_unidad=var_unidad_intervalo.get(),
            ):
                mb.showerror("Opciones", "No se pudieron guardar los respaldos automáticos.", parent=ventana)
                return

            generales_nuevas = {
                "comprobar_actualizaciones": bool(var_comprobar_updates.get()),
                "mostrar_sin_datos": bool(var_lista_sin_datos.get()),
                "mostrar_previstos": bool(var_lista_previstos.get()),
                "mostrar_online": bool(var_lista_online.get()),
                "avisos_automaticos": var_avisos.get() if var_avisos.get() in self.OPCIONES_AVISOS else "Solo errores",
                "verificacion_semanal": bool(var_verificacion_semanal.get()),
                "copia_antes_restaurar": bool(var_copia_antes_restaurar.get()),
                "patrones_exclusion": var_patrones.get().strip(),
            }
            try:
                _actualizar_config({f"opcion_{k}": v for k, v in generales_nuevas.items()})
            except Exception as exc:
                self._log("ERROR", "No se pudieron guardar las opciones generales: %s", exc)
            cambia_lista = any(generales_nuevas[k] != opciones_generales[k]
                               for k in ("mostrar_sin_datos", "mostrar_previstos", "mostrar_online"))

            ventana.destroy()
            if cambia_lista and not getattr(self, "_escaneo_en_curso", False):
                # La lista cambia de contenido: se vuelve a construir.
                self.ejecutar_en_hilo(self.scan)

        # Los tres botones quedan en la misma fila inferior, respetando los
        # márgenes de la ventana: Nube a la izquierda y Guardar/Cancelar a la derecha.
        tk.Button(
            marco_botones, text="☁ Nube", command=lambda: (ventana.destroy(), self.mostrar_nube()),
            bg="#3498db", fg="white", font=("Arial", 10, "bold"),
            bd=0, padx=20, pady=6, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            marco_botones, text="Instrucciones avanzadas", command=lambda: self.mostrar_instrucciones_avanzadas(ventana),
            bg="#8e44ad", fg="white", font=("Arial", 9, "bold"),
            bd=0, padx=14, pady=6, cursor="hand2",
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            marco_botones, text="Cancelar", command=ventana.destroy, bg="#7f8c8d", fg="white",
            font=("Arial", 10), bd=0, padx=20, pady=6, cursor="hand2",
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            marco_botones, text="Guardar", command=guardar, bg="#2ecc71", fg="white",
            font=("Arial", 10, "bold"), bd=0, padx=20, pady=6, cursor="hand2",
        ).pack(side="right")

        # Ajustar la ventana al contenido para que no queden controles ocultos
        # ni un gran espacio vacío al final.
        ventana.update_idletasks()
        req_w = max(720, ventana.winfo_reqwidth() + 10)
        req_h = ventana.winfo_reqheight() + 12
        try:
            max_h = ventana.winfo_screenheight() - 70
        except Exception:
            max_h = 900
        req_h = min(req_h, max_h)
        self.centrar_ventana(ventana, req_w, req_h)

    def _iniciar_respaldo_manual(self):
        """Captura la selección actual, la limpia inmediatamente y lanza el backup.

        La selección se toma en el hilo de la interfaz antes de arrancar el
        trabajo de fondo. De este modo, el usuario puede seleccionar otros
        juegos mientras el backup está en curso sin que el final del backup
        borre esas nuevas selecciones.
        """
        lista_seleccionados = self.get_sel_list()
        if not lista_seleccionados:
            mb.showwarning(
                "Atención",
                "Por favor, selecciona uno o varios elementos de la lista haciendo clic sobre ellos."
            )
            return

        # IMPORTANTE: esto ocurre inmediatamente al pulsar el botón y en el
        # hilo de Tk. Solo se limpia la selección que acaba de iniciar este
        # backup; las selecciones que el usuario haga después quedan intactas.
        self.deseleccionar_todo_el_listado()

        # Pasamos la lista capturada al worker para que no tenga que volver a
        # leer la selección visual, que ahora ya está vacía.
        self.ejecutar_en_hilo(
            lambda seleccion=lista_seleccionados: self.op(1, lista_forzada=seleccion)
        )

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

    # -- Indicadores de la lista principal: "[💾 3 locales] [☁ 2 en nube] Juego"
    #
    # Cada indicador ocupa una columna de ANCHO FIJO medido en píxeles con la
    # fuente real del Listbox (Arial no es monoespaciada: "1 local" y
    # "12 locales" miden distinto). El hueco que falta se rellena con espacios
    # normales y, para el ajuste fino, espacios finos (U+200A), así los nombres
    # empiezan siempre en la misma columna, tengan o no copias.
    _RELLENO_FINO = " "
    _RE_INDICADOR = re.compile(
        r"^\[(?:👍 Copia Ok|☁ Nube|💾 \d+ locales?|☁ \d+ en nube)\][    ]*")
    _RE_COPIAS_LOCALES = re.compile(r"\[💾 (\d+) locales?\]")

    @staticmethod
    def _texto_copias_locales(n):
        return f"[💾 {n} {'local' if n == 1 else 'locales'}]"

    @staticmethod
    def _texto_copias_nube(n):
        return f"[☁ {n} en nube]"

    def _medir_texto_lista(self, texto):
        """Ancho en píxeles de `texto` con la fuente del Listbox (con caché)."""
        cache = self.__dict__.setdefault("_cache_medidas_lista", {})
        if texto in cache:
            return cache[texto]
        try:
            fuente = self.__dict__.get("_fuente_lista")
            if fuente is None:
                fuente = tkfont.Font(font=self.box.cget("font"))
                self._fuente_lista = fuente
            ancho = fuente.measure(texto)
        except Exception:
            ancho = len(texto) * 8  # sin Listbox todavía: estimación
        cache[texto] = ancho
        return ancho

    def _ancho_columna_indicador(self, cual):
        """Ancho de la columna = el indicador más ancho posible + separación."""
        muestra = self._texto_copias_locales(88) if cual == "local" else self._texto_copias_nube(88)
        return self._medir_texto_lista(muestra) + self._medir_texto_lista("  ")

    def _rellenar_hasta(self, texto, ancho_objetivo):
        falta = ancho_objetivo - self._medir_texto_lista(texto)
        if falta <= 0:
            return texto + " "
        espacio = max(1, self._medir_texto_lista(" "))
        fino = self._medir_texto_lista(self._RELLENO_FINO)
        n_espacios = falta // espacio
        resto = falta - n_espacios * espacio
        n_finos = int(round(resto / fino)) if 0 < fino < espacio else 0
        return texto + " " * n_espacios + self._RELLENO_FINO * n_finos

    def _columna_indicador(self, cual, n):
        ancho = self._ancho_columna_indicador(cual)
        if not n:
            return self._rellenar_hasta("", ancho)
        texto = self._texto_copias_locales(n) if cual == "local" else self._texto_copias_nube(n)
        return self._rellenar_hasta(texto, ancho)

    def _sangria_filas_info(self):
        """Sangría de las filas informativas (sin copias posibles), alineada
        con los nombres de las filas normales."""
        return self._columna_indicador("local", 0) + self._columna_indicador("nube", 0)

    def limpiar_nombre_juego(self, texto_fila):
        res = str(texto_fila).lstrip("    ")
        # Indicadores del formato actual y del anterior ("Copia Ok"/"Nube").
        while True:
            nuevo = self._RE_INDICADOR.sub("", res, count=1)
            if nuevo == res:
                break
            res = nuevo.lstrip("    ")
        res = res.replace("[Solo en Backup] ", "")
        res = res.strip()
        if " (" in res:
            partes = res.split(" (")
            res = " (".join(partes[:-1])
        return res.strip()

    def _contar_backups_en_disco(self, game_root):
        """Nº de copias restaurables de un juego: la actual + las históricas
        fechadas (las mismas que ofrece el selector de restauración)."""
        if not game_root:
            return 0
        game_root = os.path.normpath(game_root).replace("\\", "/")
        total = 1 if os.path.isdir(game_root) else 0
        padre, base = os.path.dirname(game_root), os.path.basename(game_root)
        patron = re.compile(rf"^{re.escape(base)} \[\d{{2}}-\d{{2}}-\d{{4}}\s\d{{2}}-\d{{2}}-\d{{2}}(?:\s+#\d+)?\]$", re.I)
        try:
            for nombre in os.listdir(padre):
                if nombre.startswith(base + " [") and patron.match(nombre) and os.path.isdir(os.path.join(padre, nombre)):
                    total += 1
        except OSError:
            pass
        return total

    def _contar_copias_locales(self, nombre, rutas):
        """Nº de copias locales de un juego detectado (0 si no tiene)."""
        try:
            nombre_limpio = self.limpiar_nombre_juego(nombre)
            origenes = [rutas] if isinstance(rutas, str) else list(rutas or [])
            raices = self._raices_pc_unicas(origenes, nombre_limpio)
            if not raices:
                return 0
            base = (self._backup_game_root_multiruta(nombre_limpio) if len(raices) > 1
                    else self._backup_game_root(raices[0], nombre_limpio))
            # Se recuerda qué carpetas de backup pertenecen a juegos ya listados,
            # para no repetirlas en "Solo en carpeta backup".
            raices_listadas = getattr(self, "_raices_backup_en_lista", None)
            if raices_listadas is not None:
                raices_listadas.add(os.path.normcase(os.path.normpath(base)))
            return self._contar_backups_en_disco(base)
        except Exception:
            return 0

    def _copias_locales_fila(self, nombre, rutas):
        """Para construir una fila: cuántas copias locales tiene el juego. Cuenta
        las mismas carpetas que ofrece "Restaurar"; si no hay ninguna ahí pero
        check_bkp reconoce un backup por otra vía, cuenta 1."""
        n = self._contar_copias_locales(nombre, rutas)
        if n:
            return n
        return 1 if self.check_bkp(nombre, rutas) else 0

    def _contar_copias_nube(self, nombre_juego):
        clave = self._clave_nube_juego(nombre_juego)
        entrada = (getattr(self, "cloud_manifest", {}) or {}).get("backups", {}).get(clave) or {}
        return len([c for c in (entrada.get("copies") or []) if isinstance(c, dict) and c.get("id")])

    def _fila_tiene_copia(self, texto_fila):
        texto = str(texto_fila)
        return (bool(self._RE_COPIAS_LOCALES.search(texto)) or "[👍 Copia Ok] " in texto
                or "[Solo en Backup] " in texto)

    def _copias_locales_en_texto(self, texto_fila):
        m = self._RE_COPIAS_LOCALES.search(str(texto_fila))
        if m:
            return int(m.group(1))
        return 1 if self._fila_tiene_copia(texto_fila) else 0

    def _formatear_fila_estado(self, nombre, copias_locales, copias_nube, fila_anterior=None):
        """copias_locales / copias_nube: número de copias (True cuenta como 1)."""
        n_local = int(copias_locales or 0)
        n_nube = int(copias_nube or 0)
        return (f"{self._columna_indicador('local', n_local)}"
                f"{self._columna_indicador('nube', n_nube)}{str(nombre).strip()}")

    def _reformatear_fila_estado(self, fila, tiene_copia=None, tiene_nube=None):
        """Conserva el texto informativo de la fila y sustituye solo los indicadores.

        tiene_copia: None = conservar el número actual; True = volver a contar
        en disco (p. ej. tras un backup); un número = usar ese número.
        tiene_nube: None = contar según el índice de la nube; o un número."""
        texto = str(fila)
        nombre = self.limpiar_nombre_juego(texto)
        es_solo_backup = "[Solo en Backup] " in texto
        if tiene_copia is None:
            n_local = self._copias_locales_en_texto(texto)
        elif tiene_copia is True:
            rutas = (self.juegos or {}).get(fila)
            if es_solo_backup and isinstance(rutas, str):
                n_local = self._contar_backups_en_disco(rutas)
            else:
                n_local = self._contar_copias_locales(nombre, rutas)
            n_local = max(1, n_local)
        else:
            n_local = int(tiene_copia or 0)
        if tiene_nube is None:
            n_nube = self._contar_copias_nube(nombre)
        else:
            n_nube = int(tiene_nube or 0)
        nombre_visual = f"[Solo en Backup] {nombre}" if es_solo_backup else nombre
        # Todo lo que queda desde el último " (" es tamaño/confianza y no debe perderse.
        limpio = texto.lstrip()
        pos = limpio.rfind(" (")
        sufijo = limpio[pos:] if pos >= 0 else ""
        return f"{self._formatear_fila_estado(nombre_visual, n_local, n_nube)}{sufijo}"

    def _actualizar_estado_copia_sin_reescanear(self, juegos_exitosos):
        """Marca como respaldados solo los juegos que acaban de completarse.

        No vuelve a ejecutar scan(): conserva toda la lista, tamaños, orden y
        resultados del escaneo actual y modifica únicamente las filas que
        realmente han terminado el backup correctamente.
        """
        if not juegos_exitosos:
            return

        exitosos = set(juegos_exitosos)
        cambios = []

        # self.juegos usa como clave exactamente el texto mostrado en el Listbox.
        # Migramos también los diccionarios auxiliares para que seleccionar de
        # nuevo la fila siga funcionando después de cambiarle el prefijo.
        for clave in list(self.juegos.keys()):
            if clave not in exitosos:
                continue
            nueva_clave = self._reformatear_fila_estado(clave, tiene_copia=True)
            if nueva_clave == clave:
                continue

            valor = self.juegos.pop(clave)
            self.juegos[nueva_clave] = valor
            for atributo in ("juegos_confianza", "juegos_evidencia", "juegos_installdir"):
                diccionario = getattr(self, atributo, None)
                if isinstance(diccionario, dict) and clave in diccionario:
                    diccionario[nueva_clave] = diccionario.pop(clave)
            cambios.append((clave, nueva_clave))

        if not cambios:
            return

        def aplicar_en_tk():
            # Sustituimos únicamente las filas afectadas; no borramos ni
            # reconstruimos el Listbox y, por tanto, no se vuelve a escanear.
            por_clave = {vieja: nueva for vieja, nueva in cambios}
            for idx in range(self.box.size()):
                actual = self.box.get(idx)
                nueva = por_clave.get(actual)
                if nueva is not None:
                    seleccionado = idx in self.box.curselection()
                    self.box.delete(idx)
                    self.box.insert(idx, nueva)
                    if seleccionado:
                        self.box.selection_set(idx)

        self.root.after(0, aplicar_en_tk)

    def _normalizar_nombre_ruta(self, texto):
        """Normaliza un nombre de carpeta para poder compararlo con el nombre del juego."""
        try:
            return _norm(os.path.basename(str(texto).rstrip("/\\")))
        except Exception:
            return str(texto).strip().lower()

    # Carpetas contenedoras de Windows que agrupan varios juegos, cada uno
    # en su propia subcarpeta (el mismo papel que ya cumple "My Games").
    # Cuando la ruta de un juego pasa por una de estas carpetas, esa carpeta
    # SIEMPRE debe quedar como primer nivel dentro de "Arlequin Backups" —igual
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
        Determina la ruta relativa del save dentro de Arlequin Backups.

        La carpeta del juego es SIEMPRE la unidad que se versiona. Por ejemplo:

            .../My Games/Borderlands 2/WillowGame/SaveData

        queda como:

            Arlequin Backups/My Games/Borderlands 2/WillowGame/SaveData

        De esta forma, cuando se hace un backup nuevo, se renombra la carpeta
        completa "Borderlands 2" y no "SaveData" o "WillowGame". Lo mismo se
        aplica a carpetas contenedoras conocidas como "Saved Games" (ver
        _indice_raiz_juego): "Saved Games/CD Projekt Red/..." queda como
        "Arlequin Backups/Saved Games/CD Projekt Red/...".
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
        vez de Arlequin Backups).

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
            -> Arlequin Backups/My Games/Borderlands 2
        """
        rel = self._grupo_backup_y_relativo(origen, nombre_juego_limpio)
        partes = [p for p in rel.replace("\\", "/").split("/") if p]
        if len(partes) >= 2:
            return os.path.join(self.dest, partes[0], partes[1]).replace("\\", "/")
        return os.path.join(self.dest, partes[0] if partes else nombre_juego_limpio).replace("\\", "/")

    def _raices_pc_unicas(self, origenes, nombre_juego_limpio):
        """Obtiene las raíces reales del juego, eliminando duplicados.

        Un juego puede tener varias rutas de guardado completamente distintas
        (por ejemplo, una en AppData y otra en X:/Juegos). En ese caso todas
        esas raíces se consideran partes del mismo backup del juego.
        """
        resultado = []
        vistas = set()
        for orig in origenes or []:
            if not orig:
                continue
            ruta = orig if os.path.isabs(orig) else os.path.join(UP, orig)
            ruta = os.path.normpath(ruta).replace("\\", "/")
            raiz = self._pc_game_root(ruta, nombre_juego_limpio)
            clave = os.path.normcase(os.path.normpath(raiz))
            if clave in vistas:
                continue
            vistas.add(clave)
            resultado.append(raiz)
        return resultado

    def _es_juego_con_varias_rutas(self, origenes, nombre_juego_limpio):
        return len(self._raices_pc_unicas(origenes, nombre_juego_limpio)) > 1

    def _backup_game_root_multiruta(self, nombre_juego_limpio):
        """Carpeta común para juegos que tienen más de una ruta de guardado."""
        return os.path.join(
            self.dest, "Juegos con varias rutas", nombre_juego_limpio
        ).replace("\\", "/")

    def _etiquetas_rutas_multiruta(self, raices_pc):
        """Asigna nombres visibles y estables a cada raíz dentro del backup.

        Normalmente se usa el nombre de la carpeta raíz (por ejemplo
        ``LocalStorage_Shared`` o ``pgs``). Si dos rutas terminan con el mismo
        nombre, se añade su carpeta padre y, si todavía hubiera colisión, un
        sufijo numérico.
        """
        usadas = set()
        resultado = {}
        for raiz in raices_pc:
            base = os.path.basename(os.path.normpath(raiz)) or "Ruta"
            base = self._normalizar_nombre_ruta(base) or "Ruta"
            candidato = base
            if candidato.lower() in usadas:
                padre = os.path.basename(os.path.dirname(os.path.normpath(raiz))) or "Origen"
                padre = self._normalizar_nombre_ruta(padre) or "Origen"
                candidato = f"{padre} - {base}"
            n = 2
            original = candidato
            while candidato.lower() in usadas:
                candidato = f"{original} ({n})"
                n += 1
            usadas.add(candidato.lower())
            resultado[raiz] = candidato
        return resultado

    def _backup_multiruta_completo(self, game_root, raices_pc):
        """Comprueba que el backup común contiene todas sus rutas esperadas."""
        if not os.path.isdir(game_root):
            return False
        meta = os.path.join(game_root, BACKUP_METADATA_NAME)
        try:
            if os.path.isfile(meta):
                with open(meta, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                if datos.get("multi_route"):
                    esperadas = [str(x.get("folder", "")) for x in (datos.get("routes") or []) if isinstance(x, dict)]
                    if esperadas:
                        return all(os.path.isdir(os.path.join(game_root, x)) for x in esperadas)
            etiquetas = self._etiquetas_rutas_multiruta(raices_pc)
            return all(os.path.isdir(os.path.join(game_root, etiqueta)) for etiqueta in etiquetas.values())
        except Exception:
            return False

    def r_path(self, orig, nombre_juego_limpio):
        so = orig if os.path.isabs(orig) else os.path.join(UP, orig).replace("\\", "/")
        rel = self._grupo_backup_y_relativo(so, nombre_juego_limpio)
        return os.path.join(self.dest, *rel.split("/")).replace("\\", "/"), so

    def check_bkp(self, folder, rutas=None):
        """Comprueba si existe el backup agrupado correspondiente al juego."""
        nombre = str(folder).lower().strip()

        if rutas:
            if isinstance(rutas, str):
                rutas = [rutas]
            try:
                origenes = list(rutas)
                nombre_limpio = self.limpiar_nombre_juego(folder)
                raices = self._raices_pc_unicas(origenes, nombre_limpio)
                if len(raices) > 1:
                    esperado = self._backup_game_root_multiruta(nombre_limpio)
                    if self._backup_multiruta_completo(esperado, raices):
                        return True
                    historico = self._buscar_backup_historico_mas_reciente(esperado)
                    if historico and self._backup_multiruta_completo(historico, raices):
                        return True
                    return False

                for ruta in origenes:
                    esperado, ruta_origen = self.r_path(ruta, folder)
                    if os.path.isdir(esperado):
                        return True
                    game_root = self._backup_game_root(ruta_origen, folder)
                    historico = self._buscar_backup_historico_mas_reciente(game_root)
                    if historico:
                        rel = os.path.relpath(esperado, game_root)
                        candidato = historico if rel == "." else os.path.join(historico, rel)
                        if os.path.isdir(candidato):
                            return True
            except Exception:
                pass

        if nombre in getattr(self, "backups_existentes", set()):
            return True
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

    def run_cmd(self, o, d, excluir_archivos=None, excluir_carpetas=None):
        """Copia o->d usando robocopy y devuelve True solo si la copia fue válida.

        excluir_archivos: nombres o comodines de archivos que no se copian
        (robocopy /XF), p. ej. ash_backup.json al restaurar, o los patrones de
        exclusión de Opciones ("*.log"...) al hacer backup.
        excluir_carpetas: igual para carpetas (robocopy /XD)."""
        excluir_archivos = [n for n in (excluir_archivos or []) if n]
        excluir_carpetas = [n for n in (excluir_carpetas or []) if n]
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
                if excluir_archivos:
                    cmd += ["/XF", *excluir_archivos]
                if excluir_carpetas:
                    cmd += ["/XD", *excluir_carpetas]
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

            # Se mide el disco en este momento, sin la caché de 5 s de
            # _folder_size_bytes: la caché se indexa por la fecha de la
            # carpeta raíz, que no cambia cuando cambian archivos más adentro,
            # y podía comparar contra un tamaño de origen ya obsoleto.
            if os.path.isdir(o):
                origen_tam = _tamano_carpeta_bytes(o, excluir_archivos, excluir_carpetas)
                destino_tam = _tamano_carpeta_bytes(d, excluir_archivos, excluir_carpetas)
            else:
                origen_tam = os.path.getsize(o)
                destino_tam = os.path.getsize(os.path.join(dir_d, file_o))
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
        raíz de "Arlequin Backups" con carpetas old, old2, old3, etc.
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
        anterior con fecha, pero sin este límite "Arlequin Backups" crecería sin
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
                    fecha_txt = self._formatear_fecha_es(instante) if instante is not None else nombre
                    etiqueta = "🗓️ Copia del " + fecha_txt
                    try:
                        with open(os.path.join(ruta, BACKUP_METADATA_NAME), "r", encoding="utf-8") as fm:
                            if json.load(fm).get("detection_evidence") == "copia previa a restaurar":
                                etiqueta = f"↩️ Antes de restaurar ({fecha_txt})"
                    except Exception:
                        pass
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
        # "Reciente" = el último BACKUP. Una copia "↩️ Antes de restaurar" puede
        # ser más nueva, pero no es un backup: se elige solo a mano.
        reciente = next((c[2] for c in candidatos if not str(c[1]).startswith("↩️")),
                        candidatos[0][2] if candidatos else None)

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
                    command=lambda: cerrar_y_liberar(top, reciente)
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
                resultado["ruta"] = reciente
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
        escaneo con muchos juegos, sobre todo si "Arlequin Backups" vive en un
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

    def _confirmar_sincronizacion_activa(self, nombre_juego, sincronizadores):
        resultado = {"continuar": False}
        evento = threading.Event()
        texto = (f"Se ha detectado sincronización activa ({', '.join(sincronizadores)}) mientras se trabaja con los datos de \"{nombre_juego}\".\n\n"
                 "El servicio puede estar leyendo o modificando archivos al mismo tiempo, lo que puede producir una copia incompleta o una restauración que vuelva a cambiarse inmediatamente.\n\n¿Quieres continuar de todas formas?")
        def preguntar():
            try:
                resultado["continuar"] = mb.askyesno("Sincronización activa", texto, parent=self.root)
            except Exception:
                resultado["continuar"] = False
            evento.set()
        self.root.after(0, preguntar)
        evento.wait()
        return resultado["continuar"]

    def _backup_local_es_igual_al_origen(self, game_root, raices_pc, excluir=None):
        """Devuelve True si la copia actual contiene exactamente los mismos saves
        (sin contar los archivos excluidos por los patrones de Opciones)."""
        if not os.path.isdir(game_root):
            return False
        try:
            if len(raices_pc) == 1:
                return (self._google_hash_contenido_carpeta(game_root, excluir)
                        == self._google_hash_contenido_carpeta(raices_pc[0], excluir))
            if not self._backup_multiruta_completo(game_root, raices_pc):
                return False
            etiquetas = self._etiquetas_rutas_multiruta(raices_pc)
            for raiz in raices_pc:
                destino = os.path.join(game_root, etiquetas[raiz])
                if (self._google_hash_contenido_carpeta(destino, excluir)
                        != self._google_hash_contenido_carpeta(raiz, excluir)):
                    return False
            return True
        except Exception as exc:
            self._log("WARNING", "No se pudo comparar el backup actual de %s: %s", os.path.basename(game_root), exc)
            return False

    # -- Registro de Windows ---------------------------------------------

    def _claves_registro_juego(self, nombre, datos_juego=None):
        """Claves de registro (formato Windows) de un juego según la BD."""
        if datos_juego is None:
            datos_juego = (self.manifest or {}).get(nombre) or {}
        claves = []
        for k in (datos_juego or {}).get("registry") or []:
            kw = _clave_registro_windows(k)
            if kw and kw not in claves:
                claves.append(kw)
        return claves

    def _carpeta_registro_juego(self, nombre):
        return os.path.join(REGISTRO_DIR, _nombre_carpeta_segura(nombre)).replace("\\", "/")

    def _es_carpeta_registro(self, ruta):
        return _ruta_bajo_de(str(ruta or ""), REGISTRO_DIR)

    def _exportar_registro_juego(self, nombre, datos_juego=None):
        """Exporta las claves del juego que existan a REGISTRO_DIR/<Juego>/*.reg.

        Devuelve la carpeta, o None si ninguna clave existe (el juego no ha
        guardado nada en el registro de este PC)."""
        claves = self._claves_registro_juego(nombre, datos_juego)
        existentes = [k for k in claves if _clave_registro_existe(k)]
        carpeta = self._carpeta_registro_juego(nombre)
        if not existentes:
            return None
        tmp = carpeta + f".__tmp_{uuid.uuid4().hex[:6]}"
        try:
            os.makedirs(tmp, exist_ok=True)
            nuevos = []
            for i, clave in enumerate(existentes, 1):
                archivo = f"{i:02d} {_nombre_carpeta_segura(clave.split(chr(92))[-1])}.reg"
                ok, salida = _ejecutar_reg("export", clave, os.path.join(tmp, archivo), "/y")
                if not ok:
                    self._log("WARNING", "No se pudo exportar %s (%s): %s", clave, nombre, salida)
                    continue
                nuevos.append(archivo)
            if not nuevos:
                return None
            os.makedirs(carpeta, exist_ok=True)
            # Se sustituyen los .reg de golpe; los que ya no correspondan se borran.
            for viejo in os.listdir(carpeta):
                if viejo.lower().endswith(".reg") and viejo not in nuevos:
                    os.remove(os.path.join(carpeta, viejo))
            for archivo in nuevos:
                os.replace(os.path.join(tmp, archivo), os.path.join(carpeta, archivo))
            return carpeta
        except Exception as exc:
            self._log("WARNING", "Error exportando el registro de %s: %s", nombre, exc)
            return carpeta if os.path.isdir(carpeta) and os.listdir(carpeta) else None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _ruta_registro_para_lista(self, nombre, datos_juego=None):
        """Ruta de registro que se muestra para un juego detectado:
          - si tiene claves en este PC, la carpeta con el export actual;
          - si no, pero existe un backup de su registro (p. ej. PC nuevo), la
            carpeta vacía, para poder RESTAURARLO;
          - si no, None."""
        if not self._claves_registro_juego(nombre, datos_juego):
            return None
        carpeta = self._exportar_registro_juego(nombre, datos_juego)
        if carpeta:
            return carpeta
        destino_backup = self._backup_game_root(self._carpeta_registro_juego(nombre), nombre)
        if self._contar_backups_en_disco(destino_backup):
            carpeta = self._carpeta_registro_juego(nombre)
            os.makedirs(carpeta, exist_ok=True)
            return carpeta
        return None

    def _importar_registro_carpeta(self, nombre, carpeta):
        """Importa los .reg restaurados en `carpeta`. Devuelve lista de errores.

        Seguridad: cada .reg solo puede tocar las claves del juego que figuran
        en la BD (y sus subclaves), y solo de HKEY_CURRENT_USER. Antes de
        importar se guarda el estado actual; si algo falla, se deja como estaba."""
        errores = []
        permitidas = [k.lower() for k in self._claves_registro_juego(nombre)]
        archivos = sorted(f for f in (os.listdir(carpeta) if os.path.isdir(carpeta) else [])
                          if f.lower().endswith(".reg"))
        if not archivos:
            return errores
        plan = []
        for archivo in archivos:
            ruta = os.path.join(carpeta, archivo)
            claves = _claves_en_archivo_reg(ruta)
            if not claves:
                errores.append(f"{archivo}: no es un archivo .reg válido")
                continue
            raiz = claves[0].lower()
            if raiz not in permitidas or any(
                    not (c.lower() == raiz or c.lower().startswith(raiz + "\\")) for c in claves):
                errores.append(f"{archivo}: contiene claves que no son de {nombre}; no se importa")
                continue
            plan.append((ruta, claves[0]))
        if errores:
            return errores

        snapshot = os.path.join(REGISTRO_DIR, f".__antes_{uuid.uuid4().hex[:8]}")
        os.makedirs(snapshot, exist_ok=True)
        try:
            copias = []
            for i, (_, clave) in enumerate(plan):
                if _clave_registro_existe(clave):
                    destino = os.path.join(snapshot, f"{i}.reg")
                    ok, salida = _ejecutar_reg("export", clave, destino, "/y")
                    if not ok:
                        return [f"no se pudo guardar el estado actual de {clave}: {salida}"]
                    copias.append((clave, destino))
            for ruta, clave in plan:
                # Se borra la clave antes de importar para que no queden valores
                # posteriores al backup mezclados con los restaurados.
                if _clave_registro_existe(clave):
                    _ejecutar_reg("delete", clave, "/f")
                ok, salida = _ejecutar_reg("import", ruta)
                if not ok:
                    errores.append(f"no se pudo importar {os.path.basename(ruta)}: {salida}")
                    break
            if errores:
                # Vuelta atrás: se deja el registro como estaba.
                for _, clave in plan:
                    if _clave_registro_existe(clave):
                        _ejecutar_reg("delete", clave, "/f")
                for clave, destino in copias:
                    _ejecutar_reg("import", destino)
            else:
                self._log("INFO", "Registro de %s restaurado (%d clave(s)).", nombre, len(plan))
            return errores
        finally:
            shutil.rmtree(snapshot, ignore_errors=True)

    def _respaldar_juego(self, nombre_limpio, origenes, evidencia, fallidas, sin_cambios=None):
        """Realiza el backup completo de un juego, agrupando sus múltiples rutas.

        Si el juego tiene una sola raíz, conserva exactamente la organización
        habitual. Si tiene varias raíces, todo queda bajo:

            Arlequin Backups/Juegos con varias rutas/<Juego>/

        y cada raíz se guarda en una subcarpeta propia (por ejemplo
        ``LocalStorage_Shared`` o ``pgs``), evitando que dos rutas distintas
        se mezclen o sobrescriban archivos entre sí.
        """
        raices = []
        vistas = set()
        for orig in origenes:
            if not orig:
                continue
            ruta_real = orig if os.path.isabs(orig) else os.path.join(UP, orig)
            ruta_real = os.path.normpath(ruta_real).replace("\\", "/")
            if self._es_carpeta_registro(ruta_real):
                # Partida en el registro: se exporta ahora mismo a .reg para
                # respaldar el estado actual, no el del último escaneo.
                if not self._exportar_registro_juego(nombre_limpio):
                    fallidas.append(f"{nombre_limpio}: sus claves del registro ya no existen en este PC")
                    return False
            sincronizadores = _sincronizadores_activos()
            if sincronizadores and _ruta_bajo_de(ruta_real, entorno_windows_base().get("winDocuments", "")):
                if not self._confirmar_sincronizacion_activa(nombre_limpio, sincronizadores):
                    fallidas.append(f"{nombre_limpio}: cancelado por sincronización activa")
                    return False
            valido, motivo = self._validar_origen_para_backup(ruta_real, nombre_limpio)
            if not valido:
                fallidas.append(f"{nombre_limpio}: origen no válido ({motivo}: {ruta_real})")
                return False
            raiz_pc = self._pc_game_root(ruta_real, nombre_limpio)
            clave = os.path.normcase(os.path.normpath(raiz_pc))
            if clave in vistas:
                continue
            vistas.add(clave)
            if self._ruta_es_demasiado_amplia(raiz_pc):
                fallidas.append(
                    f"{nombre_limpio}: {raiz_pc} es una carpeta compartida por todos los juegos "
                    "(o el perfil entero); no se respalda por seguridad."
                )
                return False
            raices.append(raiz_pc)

        if not raices:
            fallidas.append(f"{nombre_limpio}: no se encontraron rutas válidas para respaldar")
            return False

        multiruta = len(raices) > 1
        game_root = (
            self._backup_game_root_multiruta(nombre_limpio)
            if multiruta else self._backup_game_root(raices[0], nombre_limpio)
        )

        # Patrones de Opciones ("*.log", "ShaderCache"...): no se copian.
        patrones = self._patrones_exclusion()

        # Si el contenido local no ha cambiado, no creamos una copia duplicada.
        if os.path.isdir(game_root) and self._backup_local_es_igual_al_origen(game_root, raices, patrones):
            if sin_cambios is not None:
                sin_cambios.append(nombre_limpio)
            self._log("INFO", "Backup omitido para %s: la copia actual ya es válida.", nombre_limpio)
            return True

        tmp_root = game_root + f".__tmp_game_{uuid.uuid4().hex[:8]}"
        tam_origen = sum(_tamano_carpeta_bytes(r, patrones, patrones) if patrones
                         else self._folder_size_bytes(r) for r in raices)
        espacio_ok, libre, requerido = self._espacio_suficiente(game_root, tam_origen)
        if not espacio_ok:
            faltan = max(0, requerido - libre)
            fallidas.append(
                f"{nombre_limpio}: espacio insuficiente. Necesita aprox. {self._formatear_bytes(requerido)}, "
                f"disponible {self._formatear_bytes(libre)} (faltan {self._formatear_bytes(faltan)})"
            )
            return False

        antiguo_backup = None
        try:
            if os.path.exists(tmp_root):
                shutil.rmtree(tmp_root, ignore_errors=True)
            os.makedirs(tmp_root, exist_ok=True)

            if multiruta:
                etiquetas = self._etiquetas_rutas_multiruta(raices)
                for raiz_pc in raices:
                    destino_ruta = os.path.join(tmp_root, etiquetas[raiz_pc])
                    if not self.run_cmd(raiz_pc, destino_ruta, patrones, patrones):
                        raise RuntimeError(f"fallo copiando {raiz_pc}")
            else:
                # La raíz temporal representa directamente la carpeta del juego.
                if not self.run_cmd(raices[0], tmp_root, patrones, patrones):
                    raise RuntimeError(f"fallo copiando {raices[0]}")

            antiguo_backup = self.rotar_a_old(game_root)
            if antiguo_backup is False:
                raise RuntimeError("no se pudo apartar el backup anterior")

            os.makedirs(os.path.dirname(game_root), exist_ok=True)
            try:
                os.replace(tmp_root, game_root)
                if multiruta:
                    etiquetas = self._etiquetas_rutas_multiruta(raices)
                    rutas_meta = [
                        {"source": raiz, "folder": etiquetas[raiz]}
                        for raiz in raices
                    ]
                    self._escribir_metadata_backup(
                        game_root, nombre_limpio, [r["source"] for r in rutas_meta], evidencia,
                        multi_route=True, routes=rutas_meta
                    )
                else:
                    self._escribir_metadata_backup(
                        game_root, nombre_limpio, raices[0], evidencia
                    )
            except Exception:
                if antiguo_backup and os.path.exists(antiguo_backup) and not os.path.exists(game_root):
                    shutil.move(antiguo_backup, game_root)
                raise

            self._log("INFO", "Backup nuevo instalado: %s", game_root)
            self._purgar_backups_historicos_antiguos(game_root)
            return True
        except Exception as exc:
            if os.path.exists(tmp_root):
                shutil.rmtree(tmp_root, ignore_errors=True)
            self._log(
                "ERROR", "Backup transaccional fallido para %s: %s",
                nombre_limpio, exc, exc_info=True
            )
            fallidas.append(f"{nombre_limpio}: {exc}")
            return False

    def _mover_estado_previo_a_backups(self, nombre_limpio, game_root_backup_base, archivados, etiquetas=None):
        """Tras restaurar, lleva la copia "antes de restaurar" a Arlequin Backups.

        La restauración aparta los saves que había en el PC renombrándolos a
        "Carpeta [fecha]" junto a la original (rápido y atómico en el mismo
        disco). Antes se quedaban ahí para siempre, llenando My Games,
        AppData, etc. con copias que nadie limpiaba. Ahora se mueven junto a
        los backups del juego como una copia histórica más, de modo que
        aparecen en el selector de restauración y sirven para deshacer.

        Si algo falla, la copia se queda donde estaba (nunca se pierde).
        """
        if not archivados:
            return
        base = os.path.normpath(game_root_backup_base).replace("\\", "/")
        fecha = self._formatear_fecha_es()
        destino = f"{base} [{fecha}]"
        n = 2
        while os.path.exists(destino):
            destino = f"{base} [{fecha} #{n}]"
            n += 1
        tmp = destino + f".__tmp_prerestore_{uuid.uuid4().hex[:8]}"
        movidos = []
        try:
            if etiquetas is None:
                archivo_raiz, _ = archivados[0]
                os.makedirs(os.path.dirname(tmp), exist_ok=True)
                shutil.move(archivo_raiz, tmp)
                movidos.append((archivo_raiz, tmp))
            else:
                os.makedirs(tmp, exist_ok=True)
                for archivo_raiz, raiz_pc in archivados:
                    sub = os.path.join(tmp, etiquetas.get(raiz_pc) or os.path.basename(raiz_pc))
                    shutil.move(archivo_raiz, sub)
                    movidos.append((archivo_raiz, sub))
            os.replace(tmp, destino)
        except Exception as exc:
            # Devolvemos a su sitio lo que ya se hubiera movido.
            for original, movido in reversed(movidos):
                try:
                    if os.path.exists(movido) and not os.path.exists(original):
                        shutil.move(movido, original)
                except Exception:
                    pass
            shutil.rmtree(tmp, ignore_errors=True)
            self._log("WARNING", "La copia previa a restaurar %s se queda junto a los saves (%s): %s",
                      nombre_limpio, ", ".join(a for a, _ in archivados), exc)
            return
        try:
            if etiquetas is None:
                self._escribir_metadata_backup(destino, nombre_limpio, archivados[0][1],
                                               "copia previa a restaurar", aplazar_hash=False)
            else:
                self._escribir_metadata_backup(
                    destino, nombre_limpio, [r for _, r in archivados], "copia previa a restaurar",
                    multi_route=True,
                    routes=[{"source": r, "folder": etiquetas.get(r) or os.path.basename(r)} for _, r in archivados],
                    aplazar_hash=False)
        except Exception:
            pass
        self._log("INFO", "Copia previa a restaurar %s guardada en %s", nombre_limpio, destino)

    def _restaurar_juego(self, nombre_limpio, origenes, fallidas):
        """Restaura un juego, tratando sus múltiples rutas como un único backup."""
        raices = self._raices_pc_unicas(origenes, nombre_limpio)
        if not raices:
            fallidas.append(f"{nombre_limpio}: no se encontraron rutas válidas para restaurar")
            return False, False
        # Registro: se exporta el estado actual antes de restaurar, para que la
        # copia "Antes de restaurar" refleje lo que hay ahora en el registro.
        raices_registro = [r for r in raices if self._es_carpeta_registro(r)]
        if raices_registro:
            self._exportar_registro_juego(nombre_limpio)

        multiruta = len(raices) > 1
        game_root_backup_base = (
            self._backup_game_root_multiruta(nombre_limpio)
            if multiruta else self._backup_game_root(raices[0], nombre_limpio)
        )
        candidatos_backup = self._listar_todos_los_backups(game_root_backup_base)
        if not candidatos_backup:
            fallidas.append(f"{nombre_limpio}: no existe el backup ({game_root_backup_base})")
            return False, False

        if len(candidatos_backup) == 1:
            game_root_backup = candidatos_backup[0][2]
        else:
            elegido = self._elegir_backup_para_restaurar(nombre_limpio, candidatos_backup)
            if not elegido:
                self._log("INFO", "Restauración de %s cancelada por el usuario.", nombre_limpio)
                fallidas.append(f"{nombre_limpio}: restauración cancelada por el usuario")
                return False, True
            game_root_backup = elegido
            self._log(
                "INFO", "Restaurando %s desde la copia elegida por el usuario: %s",
                nombre_limpio, game_root_backup
            )

        if multiruta:
            etiquetas = self._etiquetas_rutas_multiruta(raices)
            # Si el backup tiene metadata, usamos las carpetas registradas en ella.
            meta_path = os.path.join(game_root_backup, BACKUP_METADATA_NAME)
            try:
                if os.path.isfile(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    rutas_meta = {
                        os.path.normcase(os.path.normpath(str(r.get("source", "")))): str(r.get("folder", ""))
                        for r in (meta.get("routes") or []) if isinstance(r, dict)
                    }
                    for raiz in raices:
                        registrada = rutas_meta.get(os.path.normcase(os.path.normpath(raiz)))
                        if registrada:
                            etiquetas[raiz] = registrada
            except Exception:
                pass
            if not all(os.path.isdir(os.path.join(game_root_backup, etiqueta)) for etiqueta in etiquetas.values()):
                fallidas.append(f"{nombre_limpio}: el backup de varias rutas está incompleto")
                return False, False

        if not self._confirmar_restauracion_preview(nombre_limpio, game_root_backup):
            fallidas.append(f"{nombre_limpio}: restauración cancelada por el usuario")
            return False, False

        total_tam = self._folder_size_bytes(game_root_backup)
        espacio_ok, libre, requerido = self._espacio_suficiente(raices[0], total_tam)
        if not espacio_ok:
            fallidas.append(
                f"{nombre_limpio}: espacio insuficiente para restaurar. Necesita aprox. {self._formatear_bytes(requerido)}, "
                f"disponible {self._formatear_bytes(libre)}"
            )
            return False, False

        # Primero comprobamos todos los destinos para no dejar una restauración
        # parcial si una de las rutas no es segura.
        for raiz_pc in raices:
            if self._ruta_es_demasiado_amplia(raiz_pc):
                fallidas.append(
                    f"{nombre_limpio}: {raiz_pc} es una carpeta compartida por todos los juegos "
                    "(o el perfil entero); no se restaura por seguridad."
                )
                return False, False

        temporales = []
        archivados = []
        try:
            if multiruta:
                # Se usan las 'etiquetas' ya calculadas arriba, que incluyen las
                # carpetas registradas en ash_backup.json. Antes se recalculaban
                # aquí y se perdía esa correspondencia: la comprobación de
                # "backup completo" usaba unas carpetas y la copia otras.
                for raiz_pc in raices:
                    origen_backup = os.path.join(game_root_backup, etiquetas[raiz_pc])
                    tmp_destino = raiz_pc + f".__tmp_restore_game_{uuid.uuid4().hex[:8]}"
                    if os.path.exists(tmp_destino):
                        shutil.rmtree(tmp_destino, ignore_errors=True)
                    if not self.run_cmd(origen_backup, tmp_destino, excluir_archivos=[BACKUP_METADATA_NAME]):
                        raise RuntimeError(f"el backup no supera la verificación ({origen_backup})")
                    temporales.append((tmp_destino, raiz_pc))
            else:
                raiz_pc = raices[0]
                tmp_destino = raiz_pc + f".__tmp_restore_game_{uuid.uuid4().hex[:8]}"
                if os.path.exists(tmp_destino):
                    shutil.rmtree(tmp_destino, ignore_errors=True)
                # ash_backup.json es metadata de ASH: no debe acabar dentro de
                # la carpeta de saves del juego.
                if not self.run_cmd(game_root_backup, tmp_destino, excluir_archivos=[BACKUP_METADATA_NAME]):
                    raise RuntimeError(f"el backup no supera la verificación ({game_root_backup})")
                temporales.append((tmp_destino, raiz_pc))

            for tmp_destino, raiz_pc in temporales:
                if os.path.exists(raiz_pc):
                    archivo_raiz = self._nombre_backup_historico(raiz_pc)
                    shutil.move(raiz_pc, archivo_raiz)
                    archivados.append((archivo_raiz, raiz_pc))
                os.makedirs(os.path.dirname(raiz_pc), exist_ok=True)
                try:
                    os.replace(tmp_destino, raiz_pc)
                except Exception:
                    if archivados and archivados[-1][1] == raiz_pc and os.path.exists(archivados[-1][0]) and not os.path.exists(raiz_pc):
                        shutil.move(archivados[-1][0], raiz_pc)
                    raise

            # Registro: la carpeta ya tiene los .reg del backup; ahora se aplican.
            errores_registro = []
            for raiz_pc in raices_registro:
                errores_registro += self._importar_registro_carpeta(nombre_limpio, raiz_pc)
            if errores_registro:
                fallidas.append(f"{nombre_limpio}: archivos restaurados, pero el registro no: "
                                + "; ".join(errores_registro[:3]))
                self._log("ERROR", "Restauración del registro de %s fallida: %s", nombre_limpio, errores_registro)

            self._log("INFO", "Restauración completada: %s", nombre_limpio)
            if self._cargar_opciones_generales()["copia_antes_restaurar"]:
                self._mover_estado_previo_a_backups(
                    nombre_limpio, game_root_backup_base, archivados,
                    etiquetas if multiruta else None
                )
            else:
                # Desactivado en Opciones: la restauración ya terminó bien, así
                # que lo que había antes en el PC se descarta.
                for archivo_raiz, _ in archivados:
                    shutil.rmtree(archivo_raiz, ignore_errors=True)
                    self._log("INFO", "Copia previa a restaurar descartada (opción desactivada): %s", archivo_raiz)
            return (not errores_registro), False
        except Exception as exc:
            for tmp_destino, _ in temporales:
                if os.path.exists(tmp_destino):
                    shutil.rmtree(tmp_destino, ignore_errors=True)
            self._log("ERROR", "Restauración fallida para %s: %s", nombre_limpio, exc, exc_info=True)
            fallidas.append(f"{nombre_limpio}: {exc}")
            return False, False

    def op(self, mode, lista_forzada=None, automatico=False):
        lista_seleccionados = list(lista_forzada) if lista_forzada is not None else self.get_sel_list()
        if not lista_seleccionados:
            self.root.after(0, lambda: mb.showwarning(
                "Atención",
                "Por favor, selecciona uno o varios elementos de la lista haciendo clic sobre ellos."
            ))
            return

        exitosas = 0
        juegos_exitosos = []
        juegos_sin_cambios = []
        juegos_para_nube = []
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
                if automatico:
                    fallidas.append(
                        f"{nombre_limpio}: pospuesto (el juego sigue en ejecución: {exe_en_marcha})"
                    )
                    continue
                if not self._confirmar_continuar_con_juego_activo(nombre_limpio, exe_en_marcha, accion):
                    fallidas.append(
                        f"{nombre_limpio}: cancelado (el juego seguía en ejecución: {exe_en_marcha})"
                    )
                    continue

            # -----------------------------------------------------------------
            # BACKUP
            # -----------------------------------------------------------------
            if mode == 1:
                if not self._respaldar_juego(
                    nombre_limpio, origenes,
                    self.juegos_evidencia.get(tag_seleccionado, ""),
                    fallidas, juegos_sin_cambios
                ):
                    juego_ok = False

            # -----------------------------------------------------------------
            # RESTORE
            # -----------------------------------------------------------------
            elif mode == 2:
                juego_ok, cancelada = self._restaurar_juego(nombre_limpio, origenes, fallidas)
                if cancelada:
                    restauracion_cancelada = True

            if juego_ok:
                exitosas += 1
                juegos_exitosos.append(tag_seleccionado)
                if tag_seleccionado not in juegos_sin_cambios:
                    juegos_para_nube.append(tag_seleccionado)

            if restauracion_cancelada:
                break

        def finalizar_operacion():
            # Un backup, manual o automático, solo necesita actualizar las
            # filas que han terminado correctamente; no requiere un escaneo global.
            if mode == 1:
                self._actualizar_estado_copia_sin_reescanear(juegos_exitosos)
                # La selección de un respaldo manual se limpia inmediatamente
                # al pulsar el botón (en _iniciar_respaldo_manual), para que el
                # usuario pueda seguir seleccionando otros juegos mientras el
                # respaldo trabaja en segundo plano. Por eso aquí NO se toca
                # la selección: cualquier juego seleccionado después de pulsar
                # "Respaldar Save(s)" debe permanecer seleccionado.
                # Los respaldos automáticos tampoco alteran la selección manual.
                # Si la nube está configurada para subir después de cada backup,
                # se programa sin bloquear la interfaz ni el backup local.
                self._programar_subida_nube(juegos_para_nube)

            if automatico:
                self._log(
                    "INFO",
                    "Operación automática terminada: %s correctos de %s; %s incidencia(s).",
                    exitosas, total_juegos, len(fallidas),
                )
                return
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
                if mode == 1 and juegos_sin_cambios:
                    detalle_iguales = "\n".join(f"• {x}" for x in juegos_sin_cambios[:12])
                    extra_iguales = "" if len(juegos_sin_cambios) <= 12 else f"\n… y {len(juegos_sin_cambios)-12} más."
                    mb.showinfo(
                        "Copia ya válida",
                        f"La copia de seguridad ya estaba actualizada.\n\n"
                        f"{len(juegos_sin_cambios)} juego(s) ya tenían una copia idéntica y no se creó otra.\n\n"
                        f"{detalle_iguales}{extra_iguales}" +
                        (f"\n\nSe crearon copias nuevas para {len(juegos_para_nube)} juego(s)." if juegos_para_nube else "")
                    )
                else:
                    mb.showinfo(
                        "Operación completada",
                        f"¡{accion.capitalize()} completado!\n\n"
                        f"Juegos correctos: {exitosas}/{total_juegos}"
                    )

            # La restauración sí puede cambiar el contenido local, así que
            # conserva el escaneo completo que ya tenía la versión anterior.
            if mode != 1:
                # La restauración sí puede cambiar el contenido local, así que
                # conserva el escaneo completo que ya tenía la versión anterior.
                self.ejecutar_en_hilo(self.scan)

        self._ultimo_resultado_op = {
            "exitosas": exitosas, "total": total_juegos, "fallidas": list(fallidas),
            "sin_cambios": list(juegos_sin_cambios),
        }
        self.root.after(0, finalizar_operacion)
        return juegos_exitosos

    def indexar_backups_en_disco(self):
        """Indexa backups tanto en el formato nuevo agrupado como en el antiguo.

        Formato nuevo:
            Arlequin Backups/
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

                # Compatibilidad con el formato antiguo: Arlequin Backups/Juego
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
            _escribir_texto_atomico(path, "".join(f"{item}\n" for item in sorted(list(data))))
        except Exception as exc:
            self._log("ERROR", "No se pudo guardar %s: %s", path, exc)

    # -- NUEVO: configuración general (máximo de copias históricas/juego) --

    def _cargar_ruta_backup_config(self):
        """Devuelve la ubicación de backups guardada en config.json, si existe."""
        try:
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                ruta = str(datos.get("backup_root", "")).strip()
                if ruta:
                    return os.path.normpath(ruta).replace("\\", "/")
        except Exception as exc:
            self._log("ERROR", "No se pudo leer la ruta de backup de config.json: %s", exc, exc_info=True)
        return ""

    def _guardar_ruta_backup_config(self, ruta):
        """Guarda la ubicación de backups, conservando las demás opciones."""
        try:
            _actualizar_config({"backup_root": os.path.normpath(ruta).replace("\\", "/")})
        except Exception as exc:
            self._log("ERROR", "No se pudo guardar la ruta de backup: %s", exc, exc_info=True)

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
        try:
            _actualizar_config({"max_backups_historicos": int(valor)})
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
        try:
            self.manifest_estadisticas = self._calcular_estadisticas_manifest()
        except Exception:
            self.manifest_estadisticas = {}
        try:
            stats = self.manifest_estadisticas
            texto_bd = f"BD: {stats.get('juegos_unicos', 0):,} juegos".replace(",", ".")
            self.root.after(0, lambda t=texto_bd: self.lbl_db_stats.config(text=t))
        except Exception:
            pass
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

    def _calcular_estadisticas_manifest(self):
        """Cuenta juegos únicos por plataforma. Una ficha cuenta una vez por
        plataforma aunque tenga varios IDs de esa misma plataforma; si un
        juego tiene Steam y GOG, cuenta una vez en cada una."""
        plataformas_por_juego = {}
        etiquetas = {
            "steam": "Steam", "gog": "GOG", "epic": "Epic", "uplay": "Ubisoft",
            "ubisoft": "Ubisoft", "ea": "EA app", "amazon": "Amazon Games",
            "microsoft": "Xbox / Microsoft Store", "xbox": "Xbox / Microsoft Store",
            "battlenet": "Battle.net", "battle_net": "Battle.net",
        }
        for nombre, datos in (self.manifest or {}).items():
            plataformas = set()
            ids = datos.get("ids") or {}
            if isinstance(ids, dict):
                for clave, valor in ids.items():
                    clave_n = str(clave).strip().lower()
                    if clave_n.endswith("extra"):
                        clave_n = clave_n[:-5]
                    if clave_n in etiquetas and valor not in (None, "", []):
                        plataformas.add(etiquetas[clave_n])
            for ruta in datos.get("save_locations") or []:
                _, condiciones = _parsear_entrada_save_location(ruta)
                for store in condiciones.get("store", set()):
                    st = str(store).lower()
                    if st in etiquetas:
                        plataformas.add(etiquetas[st])
            # Fichas sin ruta de save: la tienda viene en la lista 'stores'.
            stores = datos.get("stores") or []
            if isinstance(stores, str):
                stores = [stores]
            for store in stores:
                st = str(store).strip().lower()
                if st in etiquetas:
                    plataformas.add(etiquetas[st])
            plataformas_por_juego[nombre] = plataformas

        conteo = {}
        multi = 0
        referencias = 0
        for plataformas in plataformas_por_juego.values():
            referencias += len(plataformas)
            if len(plataformas) > 1:
                multi += 1
            for plataforma in plataformas:
                conteo[plataforma] = conteo.get(plataforma, 0) + 1
        sin_ruta = probables = con_registro = 0
        for datos in (self.manifest or {}).values():
            if not isinstance(datos, dict):
                continue
            if datos.get("registry"):
                con_registro += 1
                continue  # el registro es una ubicación de guardado confirmada
            if datos.get("no_save_path") or not datos.get("save_locations"):
                sin_ruta += 1
            elif datos.get("probable_save_path"):
                probables += 1
        return {
            "juegos_unicos": len(self.manifest or {}),
            "juegos_con_ruta": len(self.manifest or {}) - sin_ruta - probables,
            "juegos_ruta_probable": probables,
            "juegos_con_registro": con_registro,
            "juegos_sin_ruta": sin_ruta,
            "por_plataforma": dict(sorted(conteo.items(), key=lambda x: x[0].lower())),
            "referencias_plataforma": referencias,
            "multiplataforma": multi,
        }

    def _evidencia_deteccion(self, info, clave_manifest, rutas):
        """Devuelve evidencia técnica y un nivel de confianza, no una
        valoración del juego: AppID exacto > nombre/alias exacto > fuzzy >
        ruta encontrada por catálogo."""
        launcher = info.get("launcher")
        id_juego = str(info.get("id") or "").strip()
        store = LAUNCHER_A_STORE.get(launcher)
        if clave_manifest and store == "steam" and id_juego:
            return "ALTA", f"AppID Steam {id_juego} + ficha DB"
        if clave_manifest and store == "gog" and id_juego:
            return "ALTA", f"ID GOG {id_juego} + ficha DB"
        if clave_manifest and _norm(info.get("nombre")) in self.manifest_por_nombre:
            return "ALTA", "nombre/acrónimo exacto + ficha DB"
        if clave_manifest:
            return "MEDIA", "coincidencia de nombre aproximada + ruta DB"
        if rutas:
            return "MEDIA", "ruta de guardado encontrada en el catálogo DB"
        return "BAJA", "detección sin evidencia suficiente de ruta"

    def _validar_origen_para_backup(self, ruta, nombre_juego):
        """Última validación antes de copiar: existe, es accesible, no es una
        carpeta compartida y contiene datos razonables para un backup."""
        ruta = os.path.normpath(ruta).replace("\\", "/")
        if not os.path.exists(ruta):
            return False, "la ruta no existe"
        if not os.path.isdir(ruta):
            return False, "la ruta no es una carpeta"
        if self._ruta_es_demasiado_amplia(ruta):
            return False, "la ruta es una carpeta contenedora compartida"
        try:
            entradas = list(os.scandir(ruta))
        except OSError as exc:
            return False, f"no se puede leer la carpeta: {exc}"
        if not entradas:
            return False, "la carpeta está vacía"
        # Si la raíz no se parece al nombre del juego, no bloqueamos rutas
        # válidas de manifest (muchas usan nombres de editora); solo dejamos
        # constancia para el diagnóstico.
        return True, "OK"

    def _espacio_suficiente(self, destino, bytes_necesarios, margen=BACKUP_SPACE_MARGIN):
        """Comprueba espacio libre en el volumen donde se escribirá el tmp."""
        try:
            carpeta = destino if os.path.isdir(destino) else os.path.dirname(destino)
            os.makedirs(carpeta, exist_ok=True)
            libre = shutil.disk_usage(carpeta).free
            requerido = int(max(0, bytes_necesarios) * (1.0 + margen))
            return libre >= requerido, libre, requerido
        except Exception as exc:
            # Siempre 3 valores: los llamadores desempaquetan (ok, libre, requerido).
            # Antes se devolvía un 4º valor y el desempaquetado lanzaba
            # ValueError, abortando el lote entero de backups/restauraciones.
            self._log("WARNING", "No se pudo comprobar el espacio libre en %s: %s", destino, exc)
            return False, 0, max(0, int(bytes_necesarios))

    def _resumen_carpeta(self, ruta):
        try:
            return self._folder_size_bytes(ruta), _contar_archivos_carpeta(ruta)
        except Exception:
            return 0, 0

    def _inventario_integridad(self, root, aplazar_hash=False, excluir=None):
        """Crea un inventario de archivos. Para archivos hasta 256 MB se
        guarda SHA-256; para archivos mayores se usa tamaño+mtime para evitar
        convertir una verificación de backup enorme en otra copia completa."""
        import hashlib
        if aplazar_hash and not self._esperar_si_hash_debe_aplazarse("inventario de integridad"):
            return 0, 0, {}, {}
        total = 0
        archivos = 0
        hashes = {}
        grandes = {}
        limite_hash = 256 * 1024 * 1024
        for raiz, carpetas, nombres in os.walk(root):
            if excluir:
                # Mismos patrones que se excluyen al copiar: la huella del
                # origen debe describir exactamente lo que se respalda.
                carpetas[:] = [c for c in carpetas if not _coincide_patron(c, excluir)]
            for nombre in nombres:
                if nombre == BACKUP_METADATA_NAME or _coincide_patron(nombre, excluir):
                    continue
                ruta = os.path.join(raiz, nombre)
                try:
                    st = os.stat(ruta)
                    rel = os.path.relpath(ruta, root).replace("\\", "/")
                    total += st.st_size
                    archivos += 1
                    if st.st_size <= limite_hash:
                        h = hashlib.sha256()
                        with open(ruta, "rb") as f:
                            for bloque in iter(lambda: f.read(1024 * 1024), b""):
                                h.update(bloque)
                        hashes[rel] = h.hexdigest()
                    else:
                        grandes[rel] = {"size": st.st_size, "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))}
                except OSError:
                    continue
        return total, archivos, hashes, grandes

    def _escribir_metadata_backup(self, game_root, nombre_juego, origen, evidencia=None, multi_route=False, routes=None, aplazar_hash=True):
        try:
            tam, archivos, hashes, grandes = self._inventario_integridad(game_root, aplazar_hash=aplazar_hash)
            metadata = {
                "format": 2,
                "app": "Arlequin SaveHub",
                "game": nombre_juego,
                "detection_evidence": evidencia,
                "created_at": datetime.now().strftime("%d-%m-%Y %H-%M-%S"),
                "source": origen,
                "multi_route": bool(multi_route),
                "routes": routes or [],
                "files": archivos,
                "size_bytes": tam,
                "hash_algorithm": BACKUP_HASH_ALGORITHM,
                "file_hashes": hashes,
                "large_file_signatures": grandes,
            }
            ruta_meta = os.path.join(game_root, BACKUP_METADATA_NAME)
            with open(ruta_meta, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            return True
        except Exception as exc:
            self._log("WARNING", "No se pudo escribir metadata de backup %s: %s", game_root, exc)
            return False

    def _verificar_integridad_backup(self, game_root):
        if not game_root or not os.path.isdir(game_root):
            return False, "la carpeta no existe"
        ruta_meta = os.path.join(game_root, BACKUP_METADATA_NAME)
        try:
            if not os.path.isfile(ruta_meta):
                tam, archivos, _, _ = self._inventario_integridad(game_root)
                return tam > 0, "backup antiguo sin metadata" if tam > 0 else "backup vacío"
            with open(ruta_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            tam_real, archivos_reales, hashes_reales, grandes_reales = self._inventario_integridad(game_root)
            tam_meta = int(meta.get("size_bytes", 0) or 0)
            archivos_meta = int(meta.get("files", 0) or 0)
            if tam_real != tam_meta:
                return False, "el tamaño no coincide con la metadata"
            if archivos_reales != archivos_meta:
                return False, "el número de archivos no coincide con la metadata"
            hashes_meta = meta.get("file_hashes") or {}
            if hashes_meta != hashes_reales:
                return False, "uno o más hashes SHA-256 no coinciden"
            grandes_meta = meta.get("large_file_signatures") or {}
            if grandes_meta != grandes_reales:
                return False, "cambió un archivo grande (tamaño o fecha)"
            return True, "integridad OK"
        except Exception as exc:
            return False, f"metadata ilegible: {exc}"

    def _confirmar_restauracion_preview(self, nombre_juego, backup):
        tam, archivos = self._resumen_carpeta(backup)
        ok, detalle = self._verificar_integridad_backup(backup)
        resultado = {"continuar": False}
        evento = threading.Event()
        def preguntar():
            texto = (
                f"Juego: {nombre_juego}\n\n"
                f"Backup: {backup}\n"
                f"Archivos: {archivos:,}\n"
                f"Tamaño: {self._formatear_bytes(tam)}\n"
                f"Integridad: {'✅ ' if ok else '⚠️ '}{detalle}\n\n"
                + ("La restauración sustituirá la carpeta actual. Lo que hay ahora se guardará "
                   "como copia \"↩️ Antes de restaurar\" para poder deshacerlo."
                   if self._cargar_opciones_generales()["copia_antes_restaurar"] else
                   "⚠️ La restauración sustituirá la carpeta actual y lo que hay ahora se BORRARÁ "
                   "(la copia \"Antes de restaurar\" está desactivada en Opciones).")
                + "\n\n¿Continuar?"
            )
            try:
                resultado["continuar"] = mb.askyesno("Vista previa de restauración", texto, parent=self.root)
            except Exception:
                resultado["continuar"] = False
            evento.set()
        self.root.after(0, preguntar)
        evento.wait()
        return resultado["continuar"]

    def mostrar_estadisticas_bd(self):
        def trabajo():
            stats = self._calcular_estadisticas_manifest()
            self.manifest_estadisticas = stats
            def fmt(n):
                try:
                    return f"{int(n):,}".replace(",", ".")
                except Exception:
                    return str(n)
            tiempo = (
                f"{self.ultimo_tiempo_escaneo:.2f} segundos"
                if isinstance(self.ultimo_tiempo_escaneo, (int, float))
                else "Todavía no se ha completado un escaneo"
            )
            lineas = [
                "📊 ESTADÍSTICAS DE ARLEQUIN GAME DB",
                "",
                f"Juegos únicos en la base de datos: {fmt(stats['juegos_unicos'])}",
                f"  Con ruta de guardado conocida: {fmt(stats.get('juegos_con_ruta', 0))}"
                f" (de ellos {fmt(stats.get('juegos_con_registro', 0))} en el registro de Windows)",
                f"  Con ruta probable (Steam Cloud, sin confirmar): {fmt(stats.get('juegos_ruta_probable', 0))}",
                f"  Sin ruta de guardado conocida: {fmt(stats.get('juegos_sin_ruta', 0))}",
                f"Referencias de plataforma: {fmt(stats['referencias_plataforma'])}",
                f"Juegos multiplataforma: {fmt(stats['multiplataforma'])}",
                "",
                "JUEGOS POR PLATAFORMA",
            ]
            plataformas_ordenadas = sorted(
                stats["por_plataforma"].items(),
                key=lambda x: (-int(x[1]), x[0].lower())
            )
            for plataforma, cantidad in plataformas_ordenadas:
                lineas.append(f"  {plataforma}: {fmt(cantidad)}")
            lineas += [
                "",
                "ÚLTIMO ESCANEO",
                f"  Tiempo empleado: {tiempo}",
                "  El tiempo corresponde al último escaneo completo realizado por ASH.",
            ]
            self.root.after(0, lambda: self._mostrar_diagnostico(
                "\n".join(lineas), "Estadísticas BD"
            ))
        self.ejecutar_en_hilo(trabajo)

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
                claves_reg = self._claves_registro_juego(clave_manifest, datos_juego)
                if claves_reg:
                    lineas.append("   🗝️ Guarda partida en el registro de Windows:")
                    for clave in claves_reg:
                        estado = "✅ EXISTE" if _clave_registro_existe(clave) else "❌ no existe en este PC"
                        lineas.append(f"      -> {clave}   [{estado}]")
                if not entradas and claves_reg:
                    lineas.append("")
                    continue
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
                ubisoft_root = obtener_ubisoft_root()
                ubisoft_user_ids = obtener_ubisoft_user_ids(ubisoft_root)
                store = LAUNCHER_A_STORE.get(info["launcher"])
                installdir = (info.get("installdir") or "").replace("\\", "/")
                contexto = dict(entorno)
                contexto["base"] = installdir
                if store == "steam":
                    contexto["root"] = steam_path
                    contexto["storeUserIds"] = steam_user_ids
                elif store == "uplay":
                    contexto["root"] = ubisoft_root or ""
                    contexto["storeUserIds"] = ubisoft_user_ids or []
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

    def _mostrar_diagnostico(self, texto, titulo="Diagnóstico", ajustar_instrucciones=False, ventana_padre=None):
        ventana = tk.Toplevel(self.root)
        ventana.title(titulo)
        ventana.configure(bg="#2c3e50")
        ventana.resizable(False, False)

        # Si la ventana que abrió este diálogo es modal (por ejemplo, Opciones),
        # liberamos temporalmente su grab. De lo contrario, Windows/Tk puede
        # dejar el foco atrapado en Opciones e impedir cerrar correctamente el
        # diálogo de instrucciones. Al cerrar, restauramos el grab de su padre.
        if ventana_padre is not None:
            try:
                ventana_padre.grab_release()
            except Exception:
                pass
            try:
                ventana.transient(ventana_padre)
            except Exception:
                pass

        def cerrar_dialogo():
            try:
                ventana.grab_release()
            except Exception:
                pass
            try:
                ventana.destroy()
            except Exception:
                return
            if ventana_padre is not None:
                try:
                    ventana_padre.deiconify()
                    ventana_padre.lift()
                    ventana_padre.focus_force()
                except Exception:
                    pass
            else:
                try:
                    self.root.lift()
                except Exception:
                    pass

        ventana.protocol("WM_DELETE_WINDOW", cerrar_dialogo)

        if ajustar_instrucciones:
            # Las instrucciones se muestran completas, sin scrollbar. Usamos una
            # ventana más ancha y calculamos su altura a partir del texto envuelto.
            fuente = ("Consolas", 11)
            ancho_final = 1100
            margen_horizontal = 70
            max_px = ancho_final - margen_horizontal
            caja = tk.Text(
                ventana, bg="#1b2731", fg="#ecf0f1", font=fuente,
                wrap="word", bd=0, relief="flat", padx=14, pady=12,
                width=125, height=10,
            )
            caja.pack(fill="both", expand=True, padx=10, pady=10)
            # Las líneas de contenido llevan una sangría real de texto.
            # lmargin1/lmargin2 hace que las líneas que se parten por el
            # borde derecho continúen a la misma altura que el resto del
            # contenido, en vez de volver al margen izquierdo.
            caja.tag_configure("contenido_sangrado", lmargin1=42, lmargin2=42)
            for linea in texto.splitlines(True):
                contenido = linea[4:] if linea.startswith("    ") else linea
                inicio = caja.index("end-1c")
                caja.insert("end", contenido)
                fin = caja.index("end-1c")
                if linea.startswith("    ") and fin != inicio:
                    caja.tag_add("contenido_sangrado", inicio, fin)
            caja.config(state="disabled")
            ventana.update_idletasks()

            font_obj = tk.font.Font(font=fuente)
            lineas = 0
            for parrafo in texto.split("\n"):
                if not parrafo:
                    lineas += 1
                    continue
                ancho_linea = 0
                palabras = parrafo.split()
                for palabra in palabras:
                    ancho_palabra = font_obj.measure(palabra)
                    espacio = font_obj.measure(" ") if ancho_linea else 0
                    if ancho_linea and ancho_linea + espacio + ancho_palabra > max_px:
                        lineas += 1
                        ancho_linea = ancho_palabra
                    else:
                        ancho_linea += espacio + ancho_palabra
                lineas += 1

            # Una línea de 11 pt ocupa aproximadamente 18-19 px. Añadimos margen
            # para que el último renglón nunca quede cortado.
            alto = max(360, 34 + lineas * 19)
            try:
                pantalla_h = ventana.winfo_screenheight()
                # Margen para la barra de título y la barra de tareas de Windows.
                if alto > pantalla_h - 140:
                    # No cabe en pantalla (p. ej. 1080 px): barra para llegar al final.
                    alto = pantalla_h - 140
                    barra = ttk.Scrollbar(ventana, orient="vertical", command=caja.yview)
                    barra.pack(side="right", fill="y", pady=10, before=caja)
                    caja.configure(yscrollcommand=barra.set)
            except Exception:
                pass
            ventana.geometry(f"{ancho_final}x{alto}")
            self.centrar_ventana(ventana, ancho_final, alto)
            try:
                # No hacemos grab_set(): así la ventana principal sigue
                # pudiendo recibir su cierre aunque este diálogo esté abierto.
                ventana.focus_force()
            except Exception:
                pass
        else:
            ventana.geometry("680x520")
            self.centrar_ventana(ventana, 680, 520)
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
        evidencia_por_nombre = {}
        # Juegos 100% online detectados (nombre, launcher). Solo se rellenan si
        # la opción "Mostrar juegos 100% online" está activada; _scan_impl los
        # muestra en un bloque propio.
        self._scan_online = []
        mostrar_online = self._cargar_opciones_generales()["mostrar_online"]
        online_vistos = set()

        def rango(d):
            if d["rutas"]:
                return 3
            if d["previstas"]:
                return 2
            if d.get("sin_datos"):
                return 1
            return 0

        todos_los_detectados = detectar_todos_los_juegos() + detectar_juegos_carpetas_raiz(self.carpetas_sin_launcher)
        # Descubrimiento incremental de bibliotecas sin launcher: si un juego
        # confirmado está en E:/Juegos/CS2, se puede inspeccionar E:/Juegos
        # (solo un nivel) para encontrar hermanos como E:/Juegos/Borderlands 2.
        # Se hace antes de resolver saves para que el juego descubierto entre
        # en el mismo flujo que cualquier otro juego detectado.
        try:
            self._descubrir_raices_comunes_instalacion()
            descubrimientos = self._explorar_raices_instalacion_conocidas(todos_los_detectados)
            if descubrimientos:
                todos_los_detectados.extend(descubrimientos)
        except Exception as exc:
            self._log("WARNING", "No se pudo hacer el descubrimiento incremental de carpetas: %s", exc)
        # Guardamos una instantánea independiente de la BD de saves. Aquí se
        # conservan también los juegos online/sin save local, que más abajo se
        # omiten deliberadamente de la lógica de respaldo.
        inventario_detectados = list(todos_los_detectados)
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
            conteo_launchers[info["launcher"]] = conteo_launchers.get(info["launcher"], 0) + 1
            if info["nombre"] in self.ocultos:
                continue

            # Primero resolvemos la identidad contra la BD. Esto es importante:
            # dos detectores pueden devolver nombres diferentes para la MISMA
            # ficha (por ejemplo "Borderlands GOTY Enhanced" y
            # "Borderlands: Game of the Year Enhanced"). La clave de
            # deduplicación debe ser la ficha canónica del manifest, no el texto
            # bruto que haya devuelto el launcher.
            store = LAUNCHER_A_STORE.get(info["launcher"])
            clave_manifest = self.buscar_en_manifest(info) if self.manifest else None
            clave_identidad = _norm(clave_manifest or info["nombre"])

            # Si una detección ya se ocultó por su nombre canónico, tampoco la
            # volvemos a mostrar aunque el launcher la reporte con un alias.
            if clave_manifest and clave_manifest in self.ocultos:
                continue

            # Juegos 100% online: lista fija de ASH o ficha de la BD con
            # "online_only: true". Su progreso vive en el servidor.
            es_online = _es_online_sin_save_local(clave_norm) or bool(
                clave_manifest and (self.manifest.get(clave_manifest) or {}).get("online_only"))
            if es_online:
                if mostrar_online and clave_identidad not in online_vistos:
                    online_vistos.add(clave_identidad)
                    self._scan_online.append((clave_manifest or info["nombre"], info["launcher"]))
                continue

            existente = mejores_por_nombre.get(clave_identidad)

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
                # Partida guardada en el registro de Windows (exportada a .reg).
                ruta_registro = self._ruta_registro_para_lista(clave_manifest, datos_juego)
                if ruta_registro:
                    rutas_validas.append(ruta_registro)
                if not rutas_validas:
                    if rutas_resueltas and datos_juego.get("probable_save_path"):
                        # Ruta supuesta (p. ej. Steam Cloud userdata/<appid>/remote)
                        # que no existe en disco: no hay save conocido, no es
                        # una ruta "prevista" confirmada.
                        sin_datos_guardado = True
                    elif rutas_resueltas:
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
                # Si la BD identificó la ficha, SIEMPRE usamos su nombre
                # canónico en la interfaz. El nombre del launcher queda solo
                # como evidencia interna y nunca crea una segunda fila.
                "nombre": clave_manifest or info["nombre"],
                "launcher": info["launcher"],
                "rutas": rutas_validas, "previstas": rutas_previstas,
                "sin_datos": sin_datos_guardado,
                "installdir": (info.get("installdir") or "").replace("\\", "/"),
            }
            confianza, evidencia = self._evidencia_deteccion(info, clave_manifest, rutas_validas or rutas_previstas)
            nuevo["confianza"] = confianza
            nuevo["evidencia"] = evidencia

            if existente is None:
                mejores_por_nombre[clave_identidad] = nuevo
                evidencia_por_nombre[clave_identidad] = (confianza, evidencia)
            else:
                # Fusionamos detecciones de la misma ficha en lugar de escoger
                # solo una. Así, si Steam/Epic/una carpeta manual aportan rutas
                # distintas, todas quedan asociadas al mismo juego.
                for ruta in rutas_validas:
                    if ruta not in existente["rutas"]:
                        existente["rutas"].append(ruta)
                for ruta in rutas_previstas:
                    if ruta not in existente["previstas"]:
                        existente["previstas"].append(ruta)

                # Una ruta real invalida la condición de "prevista" para esa
                # misma ubicación, y una ruta real hace que el estado global
                # sea de encontrado.
                reales_norm = {os.path.normcase(os.path.normpath(r)) for r in existente["rutas"]}
                existente["previstas"] = [
                    r for r in existente["previstas"]
                    if os.path.normcase(os.path.normpath(r)) not in reales_norm
                ]
                if existente["rutas"]:
                    existente["sin_datos"] = False
                elif nuevo.get("sin_datos"):
                    existente["sin_datos"] = True

                # Conservamos una carpeta de instalación si la anterior estaba
                # vacía y esta detección sí la proporciona.
                if not existente.get("installdir") and nuevo.get("installdir"):
                    existente["installdir"] = nuevo["installdir"]

                if rango(nuevo) > rango(existente):
                    existente["launcher"] = nuevo["launcher"]
                    existente["confianza"] = nuevo["confianza"]
                    existente["evidencia"] = nuevo["evidencia"]
                elif rango(nuevo) == rango(existente) and confianza == "ALTA" and existente.get("confianza") != "ALTA":
                    existente["confianza"] = confianza
                    existente["evidencia"] = evidencia

                evidencia_por_nombre[clave_identidad] = (
                    existente.get("confianza", confianza),
                    existente.get("evidencia", evidencia),
                )

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

        self._scan_evidencia_por_nombre = evidencia_por_nombre
        # El inventario se escribe al final de la resolución para que, además
        # de saber qué está instalado, pueda indicar si ASH conoce su save.
        self._guardar_inventario_juegos(inventario_detectados, mejores_por_nombre)
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

    # -- DESCUBRIMIENTO INCREMENTAL DE CARPETAS DE JUEGOS ---------------

    def _cargar_rutas_juegos_conocidas(self):
        """Carga el índice incremental de carpetas de instalación conocidas.

        No es una base de datos de saves. Solo recuerda qué carpetas ya hemos
        inspeccionado y qué juegos se identificaron dentro de ellas, para que
        los siguientes escaneos no tengan que volver a recorrer las mismas
        carpetas ni volver a comparar sus nombres con toda la BD.
        """
        try:
            with open(KNOWN_GAME_PATHS_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos, dict) or datos.get("version") != 1:
                return {"version": 1, "roots": {}, "games": {}}
            return {
                "version": 1,
                "roots": datos.get("roots") if isinstance(datos.get("roots"), dict) else {},
                "games": datos.get("games") if isinstance(datos.get("games"), dict) else {},
            }
        except Exception:
            return {"version": 1, "roots": {}, "games": {}}

    def _guardar_rutas_juegos_conocidas(self, datos):
        try:
            os.makedirs(os.path.dirname(KNOWN_GAME_PATHS_FILE), exist_ok=True)
            temporal = KNOWN_GAME_PATHS_FILE + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
            os.replace(temporal, KNOWN_GAME_PATHS_FILE)
        except Exception as exc:
            self._log("WARNING", "No se pudo guardar known_game_paths.json: %s", exc)

    def _obtener_unidades_locales_windows(self):
        """Devuelve las letras de unidades locales disponibles en Windows."""
        if not _ES_WINDOWS:
            return []
        unidades = []
        try:
            import ctypes
            mascara = int(ctypes.windll.kernel32.GetLogicalDrives())
            get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
            get_drive_type.argtypes = [ctypes.c_wchar_p]
            get_drive_type.restype = ctypes.c_uint
            for i in range(26):
                if not (mascara & (1 << i)):
                    continue
                raiz = f"{chr(ord('A') + i)}:/"
                try:
                    if not os.path.isdir(raiz):
                        continue
                    tipo = int(get_drive_type(raiz))
                    if tipo not in (0, 3):
                        continue
                except Exception:
                    if not os.path.isdir(raiz):
                        continue
                unidades.append(raiz)
        except Exception:
            for i in range(26):
                raiz = f"{chr(ord('A') + i)}:/"
                if os.path.isdir(raiz):
                    unidades.append(raiz)
        return unidades

    def _descubrir_raices_comunes_instalacion(self):
        """Registra raíces habituales de juegos en las unidades locales sin recorrerlas completas."""
        datos = self._cargar_rutas_juegos_conocidas()
        roots = datos.setdefault("roots", {})
        cambios = False
        for unidad in self._obtener_unidades_locales_windows():
            for nombre in COMMON_GAME_ROOT_NAMES:
                ruta = os.path.join(unidad, nombre).replace("\\", "/")
                if not os.path.isdir(ruta):
                    continue
                clave = os.path.normcase(os.path.normpath(ruta))
                anterior = roots.get(clave)
                if not isinstance(anterior, dict) or anterior.get("path") != ruta:
                    roots[clave] = {"path": ruta, "mtime_ns": None, "last_scan": 0,
                                    "children_count": 0, "manifest_count": 0,
                                    "launchers": [], "auto_discovered": True}
                    cambios = True
            for partes in COMMON_GAME_ROOT_RELATIVE:
                ruta = unidad
                for parte in partes:
                    ruta = os.path.join(ruta, parte)
                ruta = ruta.replace("\\", "/")
                if not os.path.isdir(ruta):
                    continue
                clave = os.path.normcase(os.path.normpath(ruta))
                anterior = roots.get(clave)
                if not isinstance(anterior, dict) or anterior.get("path") != ruta:
                    roots[clave] = {"path": ruta, "mtime_ns": None, "last_scan": 0,
                                    "children_count": 0, "manifest_count": 0,
                                    "launchers": [], "auto_discovered": True}
                    cambios = True
        if cambios:
            self._guardar_rutas_juegos_conocidas(datos)
        return datos

    def _explorar_raices_instalacion_conocidas(self, juegos_detectados):
        """Busca juegos hermanos en las carpetas que ya sabemos que contienen juegos.

        Ejemplo: si Steam/Epic/etc. detecta E:/Juegos/CS2, ASH registra E:/Juegos
        como raíz candidata y, en un escaneo posterior, puede encontrar
        E:/Juegos/Borderlands 2 aunque ese segundo juego no aparezca en ningún
        launcher que ASH sepa consultar.

        IMPORTANTE PARA EL RENDIMIENTO:
          * Solo se inspecciona UN nivel de subcarpetas.
          * Nunca se hace un os.walk() recursivo.
          * Las carpetas de instalación ya conocidas se omiten.
          * Si el mtime de una raíz no ha cambiado, no se vuelve a enumerar.
          * Solo se consulta la BD para carpetas nuevas/desconocidas.
          * Primero se prueba el índice exacto O(1); el fuzzy costoso solo se
            permite para raíces pequeñas y candidatos nuevos.
        """
        datos = self._cargar_rutas_juegos_conocidas()
        roots = datos.setdefault("roots", {})
        games = datos.setdefault("games", {})
        ahora = time.time()

        # Todas las carpetas de instalación que los launchers acaban de dar son
        # conocimiento confirmado y, por tanto, no necesitan volver a cotejarse.
        rutas_confirmadas = set()
        for info in (juegos_detectados or []):
            ruta = str(info.get("installdir") or "").replace("\\", "/").strip()
            if ruta and os.path.isdir(ruta):
                rutas_confirmadas.add(os.path.normcase(os.path.normpath(ruta)))

        # Rutas que ya da un launcher: esas nunca se devuelven desde aquí para
        # no duplicar el juego (el launcher aporta además su ID real).
        rutas_launcher = set(rutas_confirmadas)

        # Una raíz puede proceder de un launcher actual o de una raíz que ya
        # descubrimos en una ejecución anterior. De esta forma sigue siendo
        # útil aunque hoy no esté instalado el juego que nos la enseñó.
        raices = {}
        for info in (juegos_detectados or []):
            ruta = str(info.get("installdir") or "").replace("\\", "/").strip()
            if not ruta or not os.path.isdir(ruta):
                continue
            try:
                raiz = os.path.dirname(os.path.normpath(ruta)).replace("\\", "/")
                if raiz and os.path.isdir(raiz):
                    raices[os.path.normcase(os.path.normpath(raiz))] = raiz
            except Exception:
                continue
        for clave, registro in list(roots.items()):
            ruta = registro.get("path") if isinstance(registro, dict) else None
            if ruta and os.path.isdir(ruta):
                raices[clave] = ruta

        cambios = False
        resultados = []

        for clave_raiz, raiz in raices.items():
            # Nunca inspeccionamos una unidad completa como raíz.
            try:
                unidad, resto = os.path.splitdrive(os.path.abspath(raiz))
                if unidad and not resto.strip("\\/"):
                    continue
            except Exception:
                continue

            try:
                stat_raiz = os.stat(raiz)
                mtime_ns = getattr(stat_raiz, "st_mtime_ns", int(stat_raiz.st_mtime * 1_000_000_000))
            except Exception:
                continue

            anterior = roots.get(clave_raiz) or {}
            if (anterior.get("mtime_ns") == mtime_ns and anterior.get("path") == raiz
                    and anterior.get("manifest_count") == self.manifest_total_juegos):
                continue

            try:
                entradas = []
                for nombre in os.listdir(raiz):
                    ruta_hija = os.path.join(raiz, nombre).replace("\\", "/")
                    if os.path.isdir(ruta_hija):
                        entradas.append((nombre, ruta_hija))
            except Exception:
                continue

            # Guardamos el estado de la raíz ANTES de hacer el cotejo. Si una
            # comparación concreta falla, no obligamos a repetir toda la
            # enumeración en cada arranque.
            roots[clave_raiz] = {
                "path": raiz,
                "mtime_ns": mtime_ns,
                "last_scan": ahora,
                "children_count": len(entradas),
                "manifest_count": self.manifest_total_juegos,
            }
            cambios = True

            # Solo los candidatos nuevos necesitan consulta. Los conocidos se
            # conservan en el índice y se saltan directamente.
            nuevos = []
            for nombre, ruta_hija in entradas:
                clave_ruta = os.path.normcase(os.path.normpath(ruta_hija))
                if clave_ruta in rutas_confirmadas:
                    continue
                conocido = games.get(clave_ruta)
                if conocido:
                    # Si la misma ruta física ahora tiene otro nombre, puede
                    # tratarse de otro juego reutilizando la carpeta. En ese
                    # caso sí la volvemos a cotejar. Las carpetas que NO
                    # coincidieron también se vuelven a cotejar si la BD ha
                    # cambiado desde la última vez (puede haber juegos nuevos).
                    nombre_guardado = _norm(str(conocido.get("folder_name") or ""))
                    mismo_nombre = nombre_guardado == _norm(nombre) or not nombre_guardado
                    bd_distinta = (not conocido.get("matched")
                                   and conocido.get("manifest_count") != self.manifest_total_juegos)
                    if mismo_nombre and not bd_distinta:
                        continue
                nuevos.append((nombre, ruta_hija, clave_ruta))

            # Evitamos hacer una avalancha de fuzzy matching en una carpeta que
            # claramente no es una biblioteca de juegos. Exact match sigue sin
            # límite porque es O(1).
            for nombre, ruta_hija, clave_ruta in nuevos:
                nombre_norm = _norm(nombre)
                if not nombre_norm:
                    continue

                encontrado = self.manifest_por_nombre.get(nombre_norm) if self.manifest else None
                if not encontrado and self.manifest and len(nuevos) <= 60:
                    # Solo hacemos la comparación aproximada para una carpeta
                    # pequeña y para candidatos realmente nuevos. El método ya
                    # tiene umbral alto (0.90) y evita ambigüedades.
                    try:
                        encontrado = self.buscar_en_manifest({
                            "nombre": nombre,
                            "launcher": "Carpeta conocida",
                            "id": None,
                        })
                    except Exception:
                        encontrado = None

                # Guardamos también los no coincidentes como revisados. Si la
                # raíz no cambia, no volveremos a tocarlos. Si aparece una
                # actualización posterior de la BD, el cambio de mtime de la
                # raíz no se produce, así que NO inventamos trabajo adicional.
                games[clave_ruta] = {
                    "path": ruta_hija,
                    "name": encontrado or nombre,
                    "folder_name": nombre,
                    "matched": bool(encontrado),
                    "last_seen": ahora,
                    "manifest_count": self.manifest_total_juegos,
                }
                cambios = True

                if encontrado:
                    resultados.append({
                        "nombre": encontrado,
                        "launcher": "Carpeta",
                        "installdir": ruta_hija,
                        "id": None,
                        "detected_by": "known_root",
                    })
                    rutas_confirmadas.add(clave_ruta)

        # Los juegos identificados en arranques ANTERIORES también deben
        # devolverse en cada escaneo. Si no, solo aparecerían la primera vez:
        # en el siguiente arranque la raíz no ha cambiado (mismo mtime), se
        # salta, y el juego desaparecería de la lista.
        ya_devueltas = {os.path.normcase(os.path.normpath(r["installdir"])) for r in resultados}
        for clave_ruta, registro in list(games.items()):
            if not isinstance(registro, dict) or not registro.get("matched"):
                continue
            if clave_ruta in rutas_launcher or clave_ruta in ya_devueltas:
                continue
            ruta_juego = str(registro.get("path") or "")
            nombre_bd = str(registro.get("name") or "")
            if not ruta_juego or not nombre_bd or not os.path.isdir(ruta_juego):
                continue
            if self.manifest and nombre_bd not in self.manifest:
                continue  # la ficha ya no existe en la BD actual
            resultados.append({
                "nombre": nombre_bd,
                "launcher": "Carpeta",
                "installdir": ruta_juego,
                "id": None,
                "detected_by": "known_root",
            })
            ya_devueltas.add(clave_ruta)

        # Limpieza ligera: no borramos raíces conocidas solo porque un juego
        # haya desaparecido; si vuelve a aparecer, la raíz puede volver a ser
        # útil. Las rutas de juegos sí se conservan como historial de conocimiento.
        if cambios:
            self._guardar_rutas_juegos_conocidas(datos)
            if resultados:
                self._log("INFO", "Descubrimiento incremental: %d juego(s) nuevo(s) por raíces conocidas.", len(resultados))

        return resultados

    # -- INVENTARIO PERSISTENTE DE JUEGOS INSTALADOS -----------------------

    def _guardar_inventario_juegos(self, juegos_detectados, mejores_por_nombre):
        """Guarda un inventario independiente de la BD de saves.

        El inventario representa lo que los launchers de Windows detectan como
        instalado, aunque ASH no conozca todavía sus rutas de guardado. Esto
        permite conservar juegos online/sin save local y juegos nuevos que
        todavía no estén en ArlequinGameDB.yaml.

        Las carpetas añadidas manualmente no se consideran una instalación
        confirmada: se guardan aparte como candidatos para no presentar una
        carpeta cualquiera como un juego instalado real.
        """
        try:
            juegos = []
            candidatos_carpetas = []
            vistos = set()
            marca_tiempo = time.time()

            for info in (juegos_detectados or []):
                if not isinstance(info, dict):
                    continue
                nombre = str(info.get("nombre") or "").strip()
                launcher = str(info.get("launcher") or "").strip()
                installdir = str(info.get("installdir") or "").replace("\\", "/").strip()
                id_juego = str(info.get("id") or "").strip()
                if not nombre or not launcher:
                    continue

                # Las carpetas raíz sin launcher son una pista útil, pero no
                # prueban que el juego siga instalado. Se registran aparte.
                if launcher == "Carpeta":
                    clave_carpeta = (_norm(nombre), installdir.lower())
                    if clave_carpeta in vistos:
                        continue
                    vistos.add(clave_carpeta)
                    candidatos_carpetas.append({
                        "name": nombre,
                        "path": installdir,
                        "detected_by": "folder",
                        "installed_confirmed": False,
                    })
                    continue

                # No excluimos aquí los juegos online/sin save local.
                # Precisamente ese es uno de los objetivos del inventario.
                clave = (launcher.lower(), id_juego.lower(), _norm(nombre), installdir.lower())
                if clave in vistos:
                    continue
                vistos.add(clave)

                clave_manifest = None
                try:
                    if self.manifest:
                        clave_manifest = self.buscar_en_manifest(info)
                except Exception:
                    clave_manifest = None

                identidad = _norm(clave_manifest or nombre)
                mejor = mejores_por_nombre.get(identidad) if identidad else None

                if mejor:
                    if mejor.get("rutas"):
                        estado_save = "save_found"
                    elif mejor.get("previstas"):
                        estado_save = "save_path_known_not_created"
                    elif mejor.get("sin_datos"):
                        estado_save = "no_local_save_known"
                    else:
                        estado_save = "installed_not_resolved"
                elif clave_manifest:
                    estado_save = "installed_not_resolved"
                else:
                    estado_save = "not_in_arlequin_db"

                juegos.append({
                    "name": clave_manifest or nombre,
                    "launcher": launcher,
                    "id": id_juego or None,
                    "install_dir": installdir or None,
                    "installed": True,
                    "detected_by": "launcher",
                    "arlequin_db_match": bool(clave_manifest),
                    "arlequin_db_name": clave_manifest or None,
                    "save_status": estado_save,
                })

            juegos.sort(key=lambda x: (str(x.get("name") or "").lower(), str(x.get("launcher") or "").lower()))
            candidatos_carpetas.sort(key=lambda x: str(x.get("name") or "").lower())

            datos = {
                "version": 1,
                "generated_at": datetime.fromtimestamp(marca_tiempo).isoformat(timespec="seconds"),
                "timestamp": marca_tiempo,
                "source": "Arlequin SaveHub",
                "description": "Inventario local de juegos detectados como instalados por los launchers de Windows.",
                "total_installed": len(juegos),
                "games": juegos,
                "folder_candidates": candidatos_carpetas,
            }

            os.makedirs(os.path.dirname(INSTALLED_GAMES_FILE), exist_ok=True)
            temporal = INSTALLED_GAMES_FILE + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
            os.replace(temporal, INSTALLED_GAMES_FILE)
            self._log("INFO", "Inventario de juegos instalado actualizado: %d juegos (%s)", len(juegos), INSTALLED_GAMES_FILE)
        except Exception as exc:
            self._log("WARNING", "No se pudo guardar installed_games.json: %s", exc)

    # -- CACHÉ DE LA ÚLTIMA DETECCIÓN --------------------------------------

    def _guardar_cache_deteccion(self, elementos, conteo_launchers, total_items):
        """Guarda el último resultado completo del escaneo para acelerar el arranque.

        La caché es solo una representación temporal de la última detección.
        Al arrancar se muestra inmediatamente y, en paralelo, se hace un escaneo
        real que sustituye la caché con el estado actual del equipo.
        """
        try:
            datos = {
                "version": 1,
                "timestamp": time.time(),
                "juegos": dict(self.juegos),
                "juegos_installdir": dict(self.juegos_installdir),
                "juegos_confianza": dict(self.juegos_confianza),
                "juegos_evidencia": dict(self.juegos_evidencia),
                "elementos": list(elementos),
                "conteo_launchers": dict(conteo_launchers),
                "total_items": int(total_items),
            }
            os.makedirs(os.path.dirname(DETECTION_CACHE_FILE), exist_ok=True)
            temporal = DETECTION_CACHE_FILE + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False)
            os.replace(temporal, DETECTION_CACHE_FILE)
        except Exception as exc:
            self._log("WARNING", "No se pudo guardar la caché de detección: %s", exc)

    def _cargar_cache_deteccion(self):
        """Carga y muestra inmediatamente la última detección conocida, si existe."""
        try:
            if not os.path.isfile(DETECTION_CACHE_FILE):
                return False
            with open(DETECTION_CACHE_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos, dict) or datos.get("version") != 1:
                return False

            juegos = datos.get("juegos")
            elementos = datos.get("elementos")
            if not isinstance(juegos, dict) or not isinstance(elementos, list):
                return False

            self.juegos = {str(k): str(v) for k, v in juegos.items()}
            self.juegos_installdir = {str(k): str(v) for k, v in (datos.get("juegos_installdir") or {}).items()}
            self.juegos_confianza = {str(k): str(v) for k, v in (datos.get("juegos_confianza") or {}).items()}
            self.juegos_evidencia = {str(k): str(v) for k, v in (datos.get("juegos_evidencia") or {}).items()}

            self.box.delete(0, tk.END)
            for item in elementos:
                self.box.insert(tk.END, str(item))

            conteo = datos.get("conteo_launchers") or {}
            self.actualizar_label_launchers(conteo)
            total = int(datos.get("total_items", len(self.juegos)))
            self.lbl_i.config(text=f"Partidas {total}", fg="white")

            marca_tiempo = datos.get("timestamp")
            texto_fecha = ""
            if marca_tiempo:
                try:
                    texto_fecha = time.strftime("%d/%m/%Y %H:%M", time.localtime(float(marca_tiempo)))
                except Exception:
                    texto_fecha = ""
            self.lbl_db_status.config(
                text=(f"Última detección cargada ({texto_fecha}). Actualizando..." if texto_fecha
                      else "Última detección cargada. Actualizando..."),
                fg="#f1c40f",
            )
            self.lbl_launchers_status.config(
                text=self.lbl_launchers_status.cget("text")
            )
            self._log("INFO", "Caché de detección cargada al iniciar: %d elementos.", total)
            return True
        except Exception as exc:
            self._log("WARNING", "No se pudo cargar la caché de detección: %s", exc)
            return False

    # -- ESCANEO (ahora vía base de datos de Arlequin-SaveHub) --------------

    def _bloquear_controles_durante_escaneo(self, bloquear=True):
        """Bloquea los controles que pueden modificar o usar la lista mientras
        el escaneo está trabajando. La caché puede seguir visible, pero no se
        permite respaldar, restaurar, ocultar, añadir/quitar manualmente ni
        ejecutar acciones sobre una lista que todavía se está actualizando."""
        estado = "disabled" if bloquear else "normal"
        for control in getattr(self, "_controles_bloqueo_escaneo", []):
            try:
                control.config(state=estado)
            except Exception:
                pass

    def scan(self):
        # Cada escaneo, incluido el del arranque, bloquea los controles desde
        # el principio y los libera únicamente cuando termina (también si hay
        # una excepción).
        self._escaneo_en_curso = True
        self.root.after(0, lambda: self._bloquear_controles_durante_escaneo(True))
        try:
            self._scan_impl()
        finally:
            self._escaneo_en_curso = False
            self.root.after(0, lambda: self._bloquear_controles_durante_escaneo(False))

    def _scan_impl(self):
        inicio_scan = time.perf_counter()
        self.root.after(0, lambda: self.btn_scan.config(state="disabled", text="⏳ ESCANEANDO..."))
        self.juegos.clear()
        self.juegos_confianza.clear()
        self.juegos_evidencia.clear()
        self._scan_inicio = time.monotonic()
        self.juegos_installdir.clear()
        self._exes_cache.clear()
        # No borramos la lista actual al comenzar el escaneo.
        # La vista anterior (incluida la caché de arranque) permanece visible
        # mientras se obtiene el resultado nuevo. Se sustituirá de una vez
        # cuando el escaneo haya terminado correctamente.
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
        self._raices_backup_en_lista = set()

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
                copias_locales = self._copias_locales_fila(nombre_manual, ruta_manual)
                tam_str = self.get_folder_size_str(ruta_manual)
                nv = f"{self._formatear_fila_estado(nombre_manual, copias_locales, self._contar_copias_nube(nombre_manual))} ({tam_str})"
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

            # Se crea en cada escaneo: el contenido de las carpetas cambia
            # entre escaneos (juegos nuevos, saves borrados...).
            indice_carpetas = _IndiceCarpetasEscaneo([c for _, c in contextos_extensos])

            mostrar_online_ext = self._cargar_opciones_generales()["mostrar_online"]
            ya_detectados_norm |= {_norm(n) for n, _ in getattr(self, "_scan_online", [])}

            def _resolver_extenso(item):
                nombre_real, datos_juego = item
                nombre_real_norm = _norm(nombre_real)
                if nombre_real_norm in ya_detectados_norm:
                    return None
                if not mostrar_online_ext and (
                        datos_juego.get("online_only") or _es_online_sin_save_local(nombre_real_norm)):
                    return None
                if any(_es_edicion_derivada_del_mismo_juego(nombre_real_norm, n)
                       for n in nombres_ya_con_launcher):
                    return None
                existentes = []
                vistos_ext = set()
                # Juegos que guardan en el registro: si sus claves existen en
                # este PC, se encuentran aunque ningún launcher los conozca
                # (clásicos sueltos, juegos Unity de itch.io...).
                if datos_juego.get("registry"):
                    claves = self._claves_registro_juego(nombre_real, datos_juego)
                    if any(_clave_registro_existe(k) for k in claves):
                        carpeta_reg = self._exportar_registro_juego(nombre_real, datos_juego)
                        if carpeta_reg:
                            existentes.append((carpeta_reg, None))
                            vistos_ext.add(carpeta_reg)
                for store_contexto, contexto_extenso in contextos_extensos:
                    try:
                        if not indice_carpetas.juego_puede_tener_save(
                                datos_juego, contexto_extenso, store_contexto):
                            continue
                    except Exception:
                        pass
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
                # Si la ruta no lleva [store=...], usamos los IDs de la ficha
                # como segunda evidencia. Si solo hay una plataforma Windows
                # inequívoca, no obligamos al usuario a quedarse en "Sin launcher".
                if launcher_inferido is None:
                    ids = datos_juego.get("ids") or {}
                    plataformas_ids = set()
                    mapa_ids = {
                        "steam": "Steam", "gog": "GOG", "epic": "Epic",
                        "uplay": "Ubisoft", "ubisoft": "Ubisoft",
                        "microsoft": "Xbox", "xbox": "Xbox",
                        "ea": "EA", "amazon": "Amazon",
                        "battlenet": "Battle.net", "battle_net": "Battle.net",
                    }
                    for clave, valor in ids.items() if isinstance(ids, dict) else []:
                        base_clave = str(clave).lower().removesuffix("extra")
                        if base_clave in mapa_ids and valor not in (None, "", []):
                            plataformas_ids.add(mapa_ids[base_clave])
                    if len(plataformas_ids) == 1:
                        launcher_inferido = {
                            "Steam": "Steam", "GOG": "GOG", "Epic": "Epic",
                            "Ubisoft": "Ubisoft", "Xbox": "Xbox", "EA": "EA",
                            "Amazon": "Amazon", "Battle.net": "Battle.net",
                        }.get(next(iter(plataformas_ids)))
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
                copias_locales = self._copias_locales_fila(nombre, rutas)
                tam_str = self.get_rutas_size_str(rutas)
                # Ya está agrupado bajo la cabecera de su tienda (arriba),
                # así que aquí no hace falta repetir de qué tienda es.
                confianza, evidencia = getattr(self, "_scan_evidencia_por_nombre", {}).get(
                    _norm(nombre), ("MEDIA", "ruta de guardado encontrada"))
                # Los indicadores van delante para que sean visibles inmediatamente.
                nv = f"{self._formatear_fila_estado(nombre, copias_locales, self._contar_copias_nube(nombre))} ({tam_str} · confianza {confianza.lower()})"
                # Si hay más de una carpeta real para este juego, se guardan
                # todas: al respaldar/restaurar se procesan las dos, aunque
                # en la lista cuenten y se vean como un único elemento.
                self.juegos[nv] = rutas[0] if len(rutas) == 1 else rutas
                # NUEVO: se recuerda la carpeta de instalación de este juego
                # (si se conoce) para poder avisar si sigue abierto. Los
                # añadidos por ruta de guardado (sin confirmar instalación)
                # simplemente no tendrán installdir conocido.
                self.juegos_installdir[nv] = installdirs_por_nombre.get(nombre, "")
                self.juegos_confianza[nv] = confianza
                self.juegos_evidencia[nv] = evidencia
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
                copias_locales = self._copias_locales_fila(nombre_real, rutas)
                tam_str = self.get_rutas_size_str(rutas)
                nv = f"{self._formatear_fila_estado(nombre_real, copias_locales, self._contar_copias_nube(nombre_real))} ({tam_str} · sin launcher · confianza media)"
                self.juegos[nv] = rutas[0] if len(rutas) == 1 else rutas
                # No se conoce la instalación de estos juegos, así
                # que no se puede comprobar si el .exe está abierto.
                self.juegos_installdir[nv] = ""
                self.juegos_confianza[nv] = "MEDIA"
                self.juegos_evidencia[nv] = "ruta de guardado encontrada en la DB"
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
        opciones_lista = self._cargar_opciones_generales()
        sin_datos_filtrado = [
            (nombre, launcher) for nombre, launcher in sin_datos
            if nombre not in self.ocultos and nombre not in juegos_encontrados_global
        ]
        if sin_datos_filtrado and not opciones_lista["mostrar_sin_datos"]:
            # Ocultos desde Opciones: siguen contando como instalados en el
            # resumen de launchers, pero no ocupan filas en la lista.
            for nombre_real, launcher in sin_datos_filtrado:
                juegos_encontrados_global.add(nombre_real)
                conteo_launchers_final[launcher] = conteo_launchers_final.get(launcher, 0) + 1
            sin_datos_filtrado = []
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
                    nv = f"{self._sangria_filas_info()}{nombre_real} (instalado · sin save conocido)"
                    self.juegos[nv] = ""  # informativo: no hay ruta de save que respaldar
                    elementos_a_insertar.append(nv)
                    total_items_detectados += 1

        # Juegos 100% online (solo si la opción está activada): informativos,
        # no hay partida local que respaldar.
        online_filtrado = [
            (nombre, launcher) for nombre, launcher in getattr(self, "_scan_online", [])
            if nombre not in self.ocultos and nombre not in juegos_encontrados_global
        ]
        if online_filtrado:
            elementos_a_insertar.append("")
            elementos_a_insertar.append("═══ 🌐 JUEGOS 100% ONLINE (el progreso se guarda en el servidor) ═══")
            por_launcher_online = {}
            for nombre_real, launcher in online_filtrado:
                por_launcher_online.setdefault(launcher, []).append(nombre_real)
            for launcher in sorted(por_launcher_online.keys()):
                icono = iconos_launcher.get(launcher, "🎮")
                nombre_visual_launcher = NOMBRE_VISUAL_LAUNCHER.get(launcher, launcher)
                elementos_a_insertar.append(f"--- {icono} {nombre_visual_launcher.upper()} (online) ---")
                for nombre_real in sorted(por_launcher_online[launcher], key=str.lower):
                    juegos_encontrados_global.add(nombre_real)
                    nv = f"{self._sangria_filas_info()}{nombre_real} (instalado · 100% online)"
                    self.juegos[nv] = ""  # informativo: sin partida local
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
            # La copia ya pertenece a un juego de la lista (aunque su carpeta
            # no se llame igual que el juego, p. ej. "FINAL FANTASY X&X-2").
            if os.path.normcase(os.path.normpath(ruta_bkp)) in self._raices_backup_en_lista:
                continue
            lista_solo_backup.append((rel_bkp, nombre_bkp, ruta_bkp))

        if lista_solo_backup:
            elementos_a_insertar.append("")
            elementos_a_insertar.append("--- 💾 SOLO EN CARPETA BACKUP (DESINSTALADOS) ---")
            self._precalentar_tamanos_en_paralelo(r_c for _, _, r_c in lista_solo_backup)
            for rel_bkp, nombre_bkp, r_c in lista_solo_backup:
                tam_str = self.get_folder_size_str(r_c)
                # Mostramos el grupo para que quede claro dónde está ordenado.
                nombre_visual = f"[Solo en Backup] {rel_bkp}"
                copias_locales = max(1, self._contar_backups_en_disco(r_c))
                nv = f"{self._formatear_fila_estado(nombre_visual, copias_locales, self._contar_copias_nube(nombre_bkp))} ({tam_str})"
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
        if previstos_filtrado and not opciones_lista["mostrar_previstos"]:
            for nombre_real in {n for n, _, _ in previstos_filtrado}:
                juegos_encontrados_global.add(nombre_real)
            for launcher in {l for _, l, _ in previstos_filtrado}:
                conteo_launchers_final[launcher] = conteo_launchers_final.get(launcher, 0) + len(
                    {n for n, l, _ in previstos_filtrado if l == launcher})
            previstos_filtrado = []
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
                        nv = f"{self._sangria_filas_info()}{nombre_real} → se creará en: {rutas[0]}"
                    else:
                        nv = f"{self._sangria_filas_info()}{nombre_real} → se creará en: {rutas[0]} (+{len(rutas) - 1} más)"
                    self.juegos[nv] = ""  # carpeta aún no existe: solo informativo, no respaldable todavía
                    elementos_a_insertar.append(nv)
                    total_items_detectados += 1

        def actualizar_interfaz_grafica():
            # El escaneo ya terminó: ahora sí sustituimos de una sola vez
            # la lista anterior por el resultado nuevo. De esta forma los
            # juegos de la caché nunca desaparecen durante el análisis y
            # tampoco se duplican al insertar el resultado final.
            self.box.delete(0, tk.END)
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

        # El escaneo ha terminado correctamente: guardamos una caché completa
        # para que el siguiente arranque pueda mostrar este mismo resultado
        # inmediatamente, antes de repetir la detección real.
        self._guardar_cache_deteccion(elementos_a_insertar, conteo_launchers_final, total_items_detectados)
        # El manifiesto local puede haber llegado de Google mientras el escaneo
        # estaba en curso; reaplicamos los indicadores sin volver a escanear.
        self._actualizar_indicadores_nube()

        duracion_scan = time.perf_counter() - inicio_scan
        self.ultimo_tiempo_escaneo = duracion_scan
        self._log(
            "INFO",
            "Escaneo completado en %.2f s: %d elementos mostrados.",
            duracion_scan, total_items_detectados,
        )
        self.root.after(0, actualizar_interfaz_grafica)

    def verificar_backups(self, silencioso=False):
        """Comprueba que las copias principales existen y tienen contenido.

        silencioso=True (verificación semanal automática): sin ventanas; solo
        un aviso si hay problemas (o siempre, según Opciones)."""
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
                ok_integridad, detalle_integridad = self._verificar_integridad_backup(ruta)
                if ok_integridad:
                    validos += 1
                else:
                    problemas.append(f"{rel_bkp}: {detalle_integridad}")
            except Exception as exc:
                problemas.append(f"{rel_bkp}: {exc}")
        self._log("INFO", "Verificación de backups: %d/%d válidos", validos, total)

        if silencioso:
            try:
                _actualizar_config({"opcion_verificacion_ultima": time.time()})
            except Exception:
                pass
            modo = self._cargar_opciones_generales()["avisos_automaticos"]
            if problemas and modo != "Nunca":
                self._notificar(
                    f"Verificación semanal: {len(problemas)} copia(s) con problemas",
                    "\n".join(f"• {x}" for x in problemas[:3])
                    + ("\n…" if len(problemas) > 3 else "")
                    + "\nPulsa 🧪 Verificar para ver el detalle.", error=True)
            elif not problemas and modo == "Siempre":
                self._notificar("Verificación semanal completada", f"Las {total} copias locales están bien.")
            return

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

    def mostrar_instrucciones(self):
        texto = (
            f"📘 INSTRUCCIONES DE USO — ARLEQUIN SAVEHUB v{APP_VERSION}\n\n"
            "1. ESCANEAR SAVES\n"
            "Pulsa '🔍 ESCANEAR SAVES' para detectar los juegos instalados (Steam, Epic, GOG, Battle.net, Ubisoft, "
            "EA, Amazon, Xbox y juegos sin launcher) y dónde guardan la partida. ASH también encuentra juegos por su "
            "carpeta de guardado o por sus claves del registro de Windows aunque ningún launcher los conozca.\n\n"
            "2. LA LISTA\n"
            "Los juegos aparecen agrupados por tienda. Delante de cada uno se indica cuántas copias tiene:\n"
            "    • [💾 3 locales]: copias en tu carpeta de backups (la actual y las anteriores con fecha).\n"
            "    • [☁ 2 en nube]: copias en tu Google Drive.\n"
            "Al final hay apartados informativos (que se pueden ocultar desde Opciones): juegos sin save conocido, "
            "juegos a la espera de su primer uso, juegos 100% online y copias que están solo en la carpeta de backups.\n\n"
            "3. RESPALDAR\n"
            "Selecciona uno o varios juegos y pulsa 'Respaldar Save(s)'. ASH comprueba la ruta y el espacio libre, "
            "copia los saves y verifica la copia antes de sustituir la anterior. Si nada ha cambiado desde el último "
            "backup, no crea una copia repetida.\n\n"
            "4. RESTAURAR\n"
            "Selecciona un juego y pulsa 'Restaurar Save(s)'. Si hay varias copias, puedes elegir la más reciente "
            "('🕐 Reciente') u otra ('📂 Elegir cuál restaurar'). Antes de restaurar se muestra una vista previa con "
            "el estado de la copia. Lo que había en el PC se guarda como '↩️ Antes de restaurar', así que siempre "
            "puedes deshacerlo restaurando esa copia.\n\n"
            "5. REGISTRO DE WINDOWS\n"
            "Algunos juegos guardan la partida en el registro. ASH la exporta a archivos .reg y la respalda y restaura "
            "como cualquier otro save, sin que tengas que hacer nada especial.\n\n"
            "6. ☁ NUBE (GOOGLE DRIVE)\n"
            "En '☁ Nube' conectas tu cuenta y puedes '☁ Subir ahora' tus copias, '↻ Sincronizar' la lista y "
            "'⬇ Descargar' copias. Al descargar, si un juego tiene varias copias, eliges cuál (doble clic para "
            "cambiarla). La copia descargada pasa a ser la actual en tus backups; después usa 'Restaurar Save(s)'.\n\n"
            "7. OTROS BOTONES\n"
            "    • '➕ Añadir Manual' / '➖ Quitar Manual': añade una carpeta de saves que ASH no detecte.\n"
            "    • '📁 Juegos sin Launcher': carpetas donde tienes juegos portables o DRM-free.\n"
            "    • 'ℹ️ Detalles': rutas, tamaño y fecha del juego seleccionado.\n"
            "    • '🧪 Verificar': comprueba la integridad (SHA-256) de la copia actual de cada juego.\n"
            "    • 'Ocultar seleccionado(s)' / 'Gestionar Ocultos': quita juegos de la lista o los recupera.\n"
            "    • 'Abrir' / 'Cambiar': abre o cambia la carpeta donde se guardan los backups.\n\n"
            "8. HERRAMIENTAS\n"
            "    • '🩺 Diagnóstico': explica por qué ASH ha detectado o no un juego y dónde busca su save.\n"
            "    • '📊 Estadísticas BD': juegos de ArlequinGameDB por plataforma, cuántos tienen ruta conocida y "
            "el tiempo del último escaneo.\n"
            "    • '🔄 Actualizar': comprueba si hay versión nueva, actualiza la base de datos y sincroniza la nube.\n\n"
            "9. OPCIONES\n"
            "En '⚙️ Opciones' tienes tres bloques: General (inicio, avisos, qué mostrar en la lista), Local "
            "(respaldos automáticos, máximo de copias, verificación semanal, archivos a excluir) y Nube (subidas "
            "automáticas, límites y protecciones). Todo se explica en el botón 'Instrucciones avanzadas' de esa ventana.\n\n"
            "Consejo: cierra el juego antes de respaldar o restaurar para evitar que vuelva a escribir sobre el save."
        )
        self._mostrar_diagnostico(texto, "Instrucciones de uso", ajustar_instrucciones=True)

    def mostrar_instrucciones_avanzadas(self, ventana_padre=None):
        """Explica con más detalle las opciones de rendimiento, nube y seguridad."""
        texto = (
            "📘 INSTRUCCIONES AVANZADAS — OPCIONES\n\n"
            "La ventana de Opciones tiene tres bloques: GENERAL (arriba), 💾 LOCAL (abajo a la izquierda) y "
            "☁ NUBE (abajo a la derecha). Los cambios se aplican al pulsar 'Guardar'.\n\n"
            "═══ GENERAL ═══\n\n"
            "INICIO\n"
            "    • Abrir con Windows / abrir minimizado: ASH arranca solo al iniciar sesión, si quieres directamente "
            "en la bandeja.\n"
            "    • Ocultar en la bandeja al minimizar: al minimizar, la ventana desaparece de la barra de tareas y ASH "
            "sigue trabajando desde la bandeja del sistema.\n"
            "    • Comprobar si hay una versión nueva al iniciar: si lo desactivas, ASH no consulta GitHub al "
            "arrancar; puedes comprobarlo cuando quieras con '🔄 Actualizar'.\n"
            "    • Avisos de tareas automáticas: Nunca, Solo errores o Siempre. Se aplica a los respaldos automáticos "
            "y a la verificación semanal. Si ASH está en la bandeja, el aviso sale como notificación de Windows; si "
            "no, como una tarjeta en la esquina inferior derecha. Que un juego siga abierto y el respaldo se aplace "
            "no cuenta como error.\n\n"
            "LISTA Y RENDIMIENTO\n"
            "    • Mostrar juegos sin save conocido / a la espera de su primer uso / 100% online: muestra u oculta "
            "esos apartados informativos al final de la lista. Aunque se oculten, siguen contando en el resumen "
            "de launchers.\n"
            "    • Aplazar SHA-256: ASH espera a que el PC lleve inactivo los minutos indicados antes de hacer los "
            "cálculos de integridad, que usan CPU y disco. Afecta a los backups locales y a la nube.\n\n"
            "═══ 💾 LOCAL ═══\n\n"
            "RESPALDOS AUTOMÁTICOS\n"
            "    • Cada X horas/días/semanas: programa respaldos automáticos para los juegos incluidos.\n"
            "    • Al cerrar el juego: intenta crear un respaldo tras detectar ABIERTO → CERRADO. Antes de copiar, ASH consulta los eventos de Windows para detectar un crash. Si hay evidencia de crash, NO crea el backup automático ni sustituye el último backup conocido como válido.\n"
            "    • Si Windows registra un crash del juego: ASH muestra un aviso, protege el último backup válido y crea además una copia de emergencia separada del save que quedó en disco. Esa copia no sustituye al backup válido ni se sube automáticamente a la nube.\n"
            "    • Si el cierre no puede clasificarse con seguridad: ASH no afirma que haya sido un crash; el comportamiento automático sigue el cierre detectado.\n"
            "    • Solo si el PC está inactivo: evita iniciar el trabajo programado mientras estás usando activamente el PC.\n"
            "    • Botones rojos 'X juego(s) excluidos': todos los juegos están incluidos por defecto; ahí eliges los "
            "que NO quieres en cada modalidad.\n"
            "    • Mientras OBS está abierto, los respaldos automáticos y la verificación semanal se aplazan y se hacen "
            "cuando lo cierres.\n\n"
            "COPIAS\n"
            "    • Máximo de copias por juego: cuántas copias anteriores (con fecha) se conservan además de la actual. "
            "'Sin límite' no borra ninguna.\n"
            "    • Guardar lo que había antes de restaurar: al restaurar, lo que había en el PC se guarda como "
            "copia \"↩️ Antes de restaurar\" para poder deshacerlo. Si lo desactivas, se borra.\n"
            "    • Comprobar la integridad cada semana: hace lo mismo que '🧪 Verificar' con el PC inactivo y avisa "
            "si alguna copia está dañada.\n\n"
            "NO COPIAR ESTOS ARCHIVOS O CARPETAS\n"
            "    • Nombres o comodines separados por ; (por ejemplo *.log; *.tmp; ShaderCache; Crashes). No se copian "
            "al respaldar, así que las copias ocupan menos, pero al restaurar esos archivos no se recuperan.\n"
            "    • Solo se admiten nombres, no rutas completas.\n\n"
            "REGISTRO DE WINDOWS\n"
            "    • Algunos juegos (clásicos y muchos juegos Unity) guardan la partida en el registro "
            "(HKEY_CURRENT_USER). ASH exporta esas claves a archivos .reg y los respalda como una ruta más: "
            "aparecen en la lista, se versionan, se suben a la nube y se restauran igual que los demás saves.\n"
            "    • Al restaurar, ASH solo importa claves que pertenezcan a ese juego según la base de datos, y si algo "
            "falla deja el registro como estaba.\n\n"
            "═══ ☁ NUBE ═══\n\n"
            "SUBIDAS AUTOMÁTICAS\n"
            "    • Subir cada X horas/días/semanas: sube automáticamente los backups de los juegos incluidos.\n"
            "    • Subir al cerrar el juego: sube el backup asociado al cierre detectado.\n"
            "    • Botones rojos de exclusión: igual que en Local, pero independientes; puedes respaldar un juego en "
            "local y no subirlo a la nube.\n\n"
            "COPIAS\n"
            "    • Máximo de copias por juego: cuántas copias se conservan en Google Drive; al subir una nueva se "
            "borran las más antiguas. 'Sin límite' no borra ninguna.\n\n"
            "RED Y COMPRESIÓN\n"
            "    • Límite de subida (KB/s): limita la velocidad de transferencia hacia la nube. 0 significa sin límite.\n"
            "    • No subir con conexiones de uso medido: evita las subidas automáticas cuando Windows marca la "
            "conexión como de uso medido (datos móviles, tarifas limitadas).\n"
            "    • Compresión ZIP: Rápido usa menos CPU; Equilibrado busca un punto intermedio; Máximo prioriza reducir el tamaño.\n\n"
            "PROTECCIÓN\n"
            "    • Bloquear subida si el tamaño cambia más de X %: compara el tamaño del save con la copia anterior. "
            "Si el cambio supera el porcentaje configurado, la subida automática se bloquea para no enviar un save "
            "que parece dañado.\n"
            "    • No subir a la nube mientras OBS esté abierto: da igual que estés grabando, transmitiendo o solo "
            "con OBS preparado; mientras esté abierto no se sube nada, para no gastar red ni disco.\n\n"
            "IMPORTANTE\n"
            "    Estas opciones están pensadas para reducir el impacto de ASH mientras juegas o transmites. Los cambios "
            "    de rendimiento pueden retrasar una subida o un cálculo de integridad, pero no eliminan las comprobaciones "
            "    cuando sean necesarias."        )
        self._mostrar_diagnostico(
            texto,
            "Instrucciones avanzadas",
            ajustar_instrucciones=True,
            ventana_padre=ventana_padre,
        )

    def _configurar_backup_primera_ejecucion(self):
        """En la primera ejecución ofrece Escritorio o una carpeta elegida."""
        global BKP
        ruta_config = self._cargar_ruta_backup_config()
        if ruta_config:
            self.dest = ruta_config
            os.makedirs(self.dest, exist_ok=True)
            return

        # Si ya existe la carpeta predeterminada, no molestamos al usuario.
        if BKP_EXISTIA_AL_ARRANCAR:
            self.dest = BKP
            self._guardar_ruta_backup_config(self.dest)
            return

        respuesta = mb.askyesno(
            "Bienvenido a Arlequin SaveHub",
            "Es la primera vez que utilizas Arlequin SaveHub.\n\n"
            "¿Quieres guardar tus copias en la ubicación predeterminada del Escritorio?\n\n"
            f"Ubicación predeterminada:\n{BKP}\n\n"
            "Pulsa 'No' si prefieres elegir otra carpeta.",
            parent=self.root,
        )
        if respuesta:
            self.dest = BKP
        else:
            elegida = fd.askdirectory(
                parent=self.root,
                title="Elige dónde guardar las copias de Arlequin SaveHub",
                initialdir=DESKTOP_PATH,
            )
            if not elegida:
                # Si cancela la selección, usamos el valor seguro por defecto
                # para que la aplicación pueda continuar.
                mb.showinfo(
                    "Ubicación de backups",
                    "No se ha elegido otra carpeta. Se utilizará la ubicación predeterminada del Escritorio.",
                    parent=self.root,
                )
                self.dest = BKP
            else:
                self.dest = os.path.normpath(elegida).replace("\\", "/")

        os.makedirs(self.dest, exist_ok=True)
        self._guardar_ruta_backup_config(self.dest)
        BKP = self.dest

    def __init__(self, root):
        self.root = root
        self._tray_icon = None
        self._tray_thread = None
        self._cerrando_desde_tray = False
        # Sincronización: solo una tarea pesada puede modificar el estado
        # interno o las copias a la vez.
        self._worker_lock = threading.Lock()
        self._escaneo_en_curso = False
        self._cloud_upload_active = False
        self._cloud_manifest_sync_lock = threading.Lock()
        self._cloud_manifest_sync_active = False
        self._cloud_manifest_sync_event = threading.Event()
        self._cloud_manifest_sync_event.set()
        self._cloud_prepared_zips = {}
        self._cloud_prepared_lock = threading.Lock()
        self._cloud_download_active = False
        self._aplicar_ruta_cache_nube()
        self.cloud_manifest = self._cargar_manifest_nube_local()
        self._controles_bloqueo_escaneo = []
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
        root.protocol("WM_DELETE_WINDOW", self._cerrar_ventana_principal)
        root.geometry("820x900")
        root.minsize(820, 680)
        root.configure(bg="#2c3e50")
        self.centrar_ventana(root, 820, 900)
        self.dest = BKP
        self._configurar_backup_primera_ejecucion()
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
        self.iniciar_con_windows, self.iniciar_minimizado, self.minimizar_en_bandeja = self._cargar_opciones_inicio()
        self._minimizando_a_bandeja = False
        self.root.bind("<Unmap>", self._detectar_minimizado, add="+")
        # NUEVO: estado del sistema de respaldos automáticos.
        self._automaticos_detenidos = threading.Event()
        self._backup_automatico_en_curso = False
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
        # NUEVO: evidencia/confianza de detección y estadísticas de la BD.
        self.juegos_confianza = {}
        self.juegos_evidencia = {}
        self.manifest_estadisticas = {}
        self._scan_inicio = 0.0
        self.ultimo_tiempo_escaneo = None
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
        tk.Button(f_botones_bd, text="📊 Estadísticas BD", command=self.mostrar_estadisticas_bd,
                  bg="#8e44ad", fg="white", activebackground="#71368a", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3).pack(side="left", padx=(4, 0))
        tk.Button(f_botones_bd, text="📖 Instrucciones", command=self.mostrar_instrucciones,
                  bg="#3498db", fg="white", activebackground="#2980b9", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3).pack(side="right", padx=(4, 0))
        tk.Button(f_botones_bd, text="🔄 Actualizar", command=self._iniciar_actualizacion_completa,
                  bg="#1abc9c", fg="white", activebackground="#16a085", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3).pack(side="right", padx=(4, 0))
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
        self.lbl_db_stats = tk.Label(f_db, text="BD: calculando...",
                                     fg="#95a5a6", bg="#2c3e50", font=("Arial", 9, "bold"))
        self.lbl_db_stats.pack(side="left", padx=(15, 0))
        self.lbl_db_status.config(justify="right")
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
        btn_sin_launcher = tk.Button(f_launchers, text="📁 Juegos sin Launcher", command=self.gestionar_carpetas_sin_launcher,
                  bg="#9b59b6", fg="white", activebackground="#8e44ad", activeforeground="white",
                  font=("Arial", 8, "bold"), bd=0,
                  cursor="hand2", padx=6, pady=3)
        btn_sin_launcher.pack(side="right")

        # Los textos de estado cambian de longitud (mensajes de la BD, lista de
        # launchers...). En vez de dejar que se monten sobre lo que tienen al
        # lado, se limita su ancho al hueco libre y, si no caben, pasan a una
        # segunda línea.
        def ajustar_textos_estado(_evento=None):
            try:
                libre_db = (f_db.winfo_width() - self.lbl_update_status.winfo_reqwidth()
                            - self.lbl_db_stats.winfo_reqwidth() - 40)
                self.lbl_db_status.config(wraplength=max(160, libre_db))
                libre_launchers = f_launchers.winfo_width() - btn_sin_launcher.winfo_reqwidth() - 20
                self.lbl_launchers_status.config(wraplength=max(200, libre_launchers))
            except tk.TclError:
                pass

        f_db.bind("<Configure>", ajustar_textos_estado, add="+")
        f_launchers.bind("<Configure>", ajustar_textos_estado, add="+")
        for etiqueta in (self.lbl_update_status, self.lbl_db_stats):
            etiqueta.bind("<Configure>", ajustar_textos_estado, add="+")
        f_r = tk.Frame(root, bg="#34495e", bd=1, relief="solid", height=34)
        f_r.pack_propagate(False)
        f_r.pack(pady=5, fill="x", padx=20)
        self.lbl_r = tk.Label(f_r, text=f"Guardando en: {self.dest}", fg="#bdc3c7", bg="#34495e",
                              font=("Arial", 9), wraplength=500, justify="center", anchor="center")
        self.lbl_r.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.62)
        tk.Button(f_r, text="☁ Nube", command=self.mostrar_nube, bg="#4285f4",
                  fg="white", font=("Arial", 8, "bold"), bd=0, cursor="hand2", padx=8, pady=2).pack(side="left", padx=5)
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
        btn_anadir_manual = tk.Button(f_s_centro, text="➕ Añadir Manual", command=self.añadir_carpeta_manual, bg="#9b59b6",
                  fg="white", font=("Arial", 9, "bold"), bd=0, padx=8, pady=4, cursor="hand2")
        btn_anadir_manual.pack(side="left", padx=2)
        btn_quitar_manual = tk.Button(f_s_centro, text="➖ Quitar Manual", command=self.quitar_carpeta_manual, bg="#e67e22",
                  fg="white", font=("Arial", 9, "bold"), bd=0, padx=8, pady=4, cursor="hand2")
        btn_quitar_manual.pack(side="left", padx=2)
        # La lista va en un marco con barras de desplazamiento que solo
        # aparecen cuando hacen falta: filas largas (p. ej. "→ se creará en:
        # C:/ruta/muy/larga") ya no quedan cortadas por la derecha.
        f_lista = tk.Frame(root, bg="#34495e")
        f_lista.pack(pady=5, padx=20, fill="both", expand=True)
        f_lista.rowconfigure(0, weight=1)
        f_lista.columnconfigure(0, weight=1)
        self.box = tk.Listbox(f_lista, font=("Arial", 11), bg="#34495e", fg="white",
                              selectbackground="#1abc9c", bd=0, highlightthickness=0,
                              activestyle="none", selectmode="multiple")
        self.box.grid(row=0, column=0, sticky="nsew")
        barra_v = ttk.Scrollbar(f_lista, orient="vertical", command=self.box.yview)
        barra_h = ttk.Scrollbar(f_lista, orient="horizontal", command=self.box.xview)
        barra_v.grid(row=0, column=1, sticky="ns")
        barra_h.grid(row=1, column=0, sticky="ew")

        def enlazar_barra(barra):
            def mover(primero, ultimo):
                if float(primero) <= 0.0 and float(ultimo) >= 1.0:
                    barra.grid_remove()
                else:
                    barra.grid()
                barra.set(primero, ultimo)
            return mover

        self.box.configure(yscrollcommand=enlazar_barra(barra_v), xscrollcommand=enlazar_barra(barra_h))
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
                             command=self._iniciar_respaldo_manual)
        btn_resp.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        btn_rest = tk.Button(f_b, text="Restaurar Save(s)", font=("Arial", 11, "bold"), bg="#e74c3c",
                             fg="white", bd=0, relief="flat", pady=8, cursor="hand2",
                             command=lambda: self.ejecutar_en_hilo(lambda: self.op(2)))
        btn_rest.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # Controles que deben permanecer bloqueados mientras se escanea.
        # Donar y Opciones quedan disponibles porque no trabajan sobre la lista.
        self._controles_bloqueo_escaneo = [
            self.btn_scan,
            btn_resp,
            btn_rest,
            btn_ocultar,
            btn_gestionar_ocultos,
            btn_sel,
            btn_desel,
            btn_anadir_manual,
            btn_quitar_manual,
        ]
        # El escaneo inicial comienza después de construir la interfaz, pero
        # los controles quedan bloqueados desde ya para que la caché visible
        # no pueda utilizarse antes de que termine la detección real.
        self._bloquear_controles_durante_escaneo(True)
        f_inf = tk.Frame(root, bg="#2c3e50")
        f_inf.pack(pady=15, fill="x", padx=20)
        tk.Button(f_inf, text="🎁 Donar", command=self.abrir_link_donar, bg="#e67e22", fg="white",
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2").pack(side="left")
        tk.Button(f_inf, text="⚙️ Opciones", command=self.mostrar_opciones, bg="#7f8c8d", fg="white",
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2").pack(side="right")
        tk.Label(f_inf, text="by aitor965", font=("Arial", 11, "bold", "italic"),
                 fg="#bdc3c7", bg="#2c3e50").pack(side="right", padx=(0, 8))
        # IMPORTANTE: la ventana ya está construida y a punto de mostrarse
        # (root.mainloop() se llama justo después, fuera de esta clase).
        # Solo AHORA, en un hilo aparte para no bloquear la interfaz, se
        # descarga/actualiza la base de datos de Arlequin-SaveHub y se escanea.
        # Arranque en dos fases: primero mostramos la última detección guardada
        # para que la ventana sea útil inmediatamente; después se hace el escaneo
        # real en segundo plano y reemplaza la caché con el estado actual.
        self._cargar_cache_deteccion()
        # Si ASH se cerró durante una subida de Google Drive, la sesión y el
        # ZIP quedan guardados y se intentan reanudar automáticamente al
        # siguiente arranque.
        self._reanudar_subida_nube_pendiente()
        self._sincronizar_manifest_nube_al_arranque()

        def arranque():
            self.indexar_backups_en_disco()
            self.actualizar_bd_y_escanear(forzar=False)
        # No hay espera artificial de 250 ms: el escaneo comienza en cuanto
        # Tkinter procesa el arranque, manteniendo la caché visible mientras
        # se realiza el trabajo en segundo plano.
        self.root.after(0, lambda: self.ejecutar_en_hilo(arranque))
        # Comprobación de actualizaciones: en su propio hilo (no comparte el
        # candado de ejecutar_en_hilo) para que no espere a que termine el
        # escaneo inicial ni lo bloquee.
        threading.Thread(target=self.comprobar_actualizaciones_al_inicio, daemon=True).start()
        # Monitor de respaldos automáticos: permanece dormido si no hay
        # ninguna opción activada y comprueba cambios cada 5 segundos.
        threading.Thread(target=self._monitorizar_respaldos_automaticos, daemon=True).start()

    def _set_estado_actualizacion(self, texto, color="#95a5a6"):
        self.root.after(0, lambda: self.lbl_update_status.config(text=texto, fg=color))

    def _iniciar_actualizacion_completa(self):
        """Comprueba/actualiza en una sola acción el programa, la BD y el
        estado de los archivos conocidos en la nube.

        La comprobación se hace en segundo plano para que la interfaz siga
        respondiendo. La BD usa su ETag/caché normal: solo descarga el YAML
        si realmente ha cambiado. La nube se sincroniza mediante
        cloud_manifest.json, de modo que podemos refrescar qué backups
        existen sin descargar los ZIP.
        """
        if getattr(self, "_actualizacion_completa_en_curso", False):
            return
        self._actualizacion_completa_en_curso = True

        def trabajador():
            resumen = []
            actualizacion_programa = None
            try:
                self._set_estado_actualizacion("🔄 Comprobando programa...", "#3498db")
                try:
                    actualizacion_programa = comprobar_actualizacion_disponible()
                    if actualizacion_programa:
                        version = actualizacion_programa.get("version", "?")
                        resumen.append(f"Programa: hay una nueva versión v{version} disponible")
                    else:
                        resumen.append(f"Programa: actualizado (v{APP_VERSION})")
                except Exception as exc:
                    resumen.append(f"Programa: no se pudo comprobar ({exc})")
                    self._log("ERROR", "Error comprobando la versión del programa: %s", exc, exc_info=True)

                self._set_estado_actualizacion("🔄 Comprobando base de datos...", "#3498db")
                try:
                    # No forzamos la descarga: descargar_manifest usa ETag y
                    # conserva la caché si GitHub no ha cambiado la BD.
                    self.actualizar_base_de_datos(forzar=False)
                    if self.manifest:
                        resumen.append(f"Base de datos: {self.manifest_total_juegos:,} juegos verificados".replace(",", "."))
                        self.scan()
                    else:
                        resumen.append("Base de datos: no disponible")
                except Exception as exc:
                    resumen.append(f"Base de datos: error ({exc})")
                    self._log("ERROR", "Error actualizando la base de datos: %s", exc, exc_info=True)

                self._set_estado_actualizacion("🔄 Comprobando archivos de la nube...", "#3498db")
                try:
                    config = self._cargar_config_nube()
                    if config.get("account") and os.path.exists(GOOGLE_TOKEN_FILE):
                        creds = self._google_obtener_credenciales(pedir_json=False)
                        if creds is None:
                            resumen.append("Nube: no se pudo autenticar")
                        else:
                            ok = self._google_sincronizar_manifest_nube(creds, mostrar_error=False)
                            if ok:
                                backups = (getattr(self, "cloud_manifest", {}) or {}).get("backups", {})
                                total_copias = sum(len(v.get("copies", [])) for v in backups.values() if isinstance(v, dict))
                                resumen.append(f"Nube: {total_copias} copias verificadas")
                                self.root.after(0, self._actualizar_indicadores_nube)
                            else:
                                resumen.append("Nube: no se pudo sincronizar el manifiesto")
                    else:
                        resumen.append("Nube: no conectada")
                except Exception as exc:
                    resumen.append(f"Nube: error ({exc})")
                    self._log("ERROR", "Error comprobando los archivos de la nube: %s", exc, exc_info=True)

                self._set_estado_actualizacion("🔄 Actualización completada", "#2ecc71")

                def terminar():
                    self._actualizacion_completa_en_curso = False
                    # Si hay una versión nueva, ofrecemos instalarla después
                    # de haber terminado las comprobaciones de BD y nube.
                    if actualizacion_programa and actualizacion_programa.get("url_descarga", "").strip():
                        version = actualizacion_programa.get("version", "?")
                        novedades = str(actualizacion_programa.get("novedades", "")).strip()
                        texto = f"Hay una nueva versión disponible: v{version}\n(tienes v{APP_VERSION})"
                        if novedades:
                            texto += f"\n\nNovedades:\n{novedades}"
                        texto += "\n\n¿Quieres actualizar ahora?"
                        if mb.askyesno("Actualización disponible", texto, parent=self.root):
                            self.ejecutar_en_hilo(lambda: self._aplicar_actualizacion(
                                actualizacion_programa.get("url_descarga", ""), version,
                                actualizacion_programa.get("sha256")))
                            return
                    # Mostrar un resumen corto de las tres comprobaciones.
                    mb.showinfo("Actualizar", "Se han comprobado el programa, la base de datos y la nube.\n\n" + "\n".join(resumen), parent=self.root)

                self.root.after(0, terminar)
            except Exception as exc:
                self._log("ERROR", "Error en la actualización completa: %s", exc, exc_info=True)
                error_text = str(exc)
                self._set_estado_actualizacion("⚠️ Error durante la actualización", "#e74c3c")
                self.root.after(0, lambda error_text=error_text: mb.showerror(
                    "Actualizar", f"No se pudo completar la comprobación.\n\n{error_text}", parent=self.root))
                self.root.after(0, lambda: setattr(self, "_actualizacion_completa_en_curso", False))

        threading.Thread(target=trabajador, name="ASHActualizacionCompleta", daemon=True).start()

    def comprobar_actualizaciones_al_inicio(self):
        """Se ejecuta en segundo plano al abrir el programa. Si hay una
        versión más nueva publicada, pregunta al usuario (en el hilo
        principal de Tkinter) si quiere actualizar."""
        if not self._cargar_opciones_generales()["comprobar_actualizaciones"]:
            # Desactivado en Opciones: se puede comprobar a mano con "🔄 Actualizar".
            self._set_estado_actualizacion(f"v{APP_VERSION}", "#95a5a6")
            return
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
                self.ejecutar_en_hilo(lambda: self._aplicar_actualizacion(
                    url_descarga, version_remota, datos.get("sha256")))
            else:
                self._set_estado_actualizacion(
                    f"🆕 Versión v{version_remota} disponible (pendiente)", "#f1c40f")

        self.root.after(0, preguntar)

    def _aplicar_actualizacion(self, url_descarga, version_remota="?", sha256_esperado=None):
        """Descarga la nueva versión y, si todo va bien, cierra la app para
        que el script de actualización termine el reemplazo y la reabra."""
        self._set_estado_actualizacion(f"⬇️ Descargando actualización v{version_remota}...", "#3498db")

        def avisar(tipo, titulo, texto):
            # Se ejecuta en un hilo de fondo: la ventana se abre en el de Tk.
            funcion = mb.showerror if tipo == "error" else mb.showinfo
            self.root.after(0, lambda: funcion(titulo, texto, parent=self.root))

        cerrar_app = descargar_y_aplicar_actualizacion(url_descarga, sha256_esperado, avisar)
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

    # La ubicación de backups puede elegirse en la primera ejecución, así
    # que no debemos crear/comprobar la carpeta predeterminada antes de que
    # el usuario haya elegido dónde quiere guardar sus copias.
    carpetas_a_probar = [APP_ARLEQUIN_SAVEHUB_DIR]
    if BKP_EXISTIA_AL_ARRANCAR:
        carpetas_a_probar.append(BKP)
    else:
        try:
            ruta_config = ""
            if os.path.exists(M_CFG):
                with open(M_CFG, "r", encoding="utf-8") as f:
                    datos_cfg = json.load(f)
                ruta_config = str(datos_cfg.get("backup_root", "")).strip()
            if ruta_config:
                carpetas_a_probar.append(os.path.normpath(ruta_config).replace("\\", "/"))
        except Exception:
            pass
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
    # "Abrir minimizado" solo se aplica cuando ASH es iniciado por Windows.
    # La entrada de inicio de Windows añade --minimized al comando.
    # Si el usuario abre ASH manualmente, se muestra normalmente.
    if "--minimized" in sys.argv:
        # El inicio minimizado va directamente a la bandeja, no a la barra de tareas.
        root.after(300, app.ocultar_en_bandeja)
    root.mainloop()
