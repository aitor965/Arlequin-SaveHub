# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
"Ayuda a mejorar Arlequin" (opcional).

Se ofrece en la bienvenida de la primera vez (casilla marcada, se puede
desmarcar) y se cambia en Opciones. Mientras está activado, después de cada
escaneo ASH envía, de
forma anónima, lo que ha aprendido y que la base de datos ArlequinGameDB
todavía no sabe:

  - rutas: carpetas de partidas que el usuario ha añadido a mano y rutas que
    ASH ha encontrado por su cuenta (carpetas con el nombre del juego en las
    ubicaciones típicas de Windows) para juegos sin ruta conocida.
  - sin_ruta: juegos instalados que no están en la base de datos o que están
    pero sin ruta de guardado (nombre, tienda e ID de tienda).

Nunca se envían rutas con el nombre de usuario ni carpetas del equipo: cada
ruta se convierte a los comodines de la base de datos (<winDocuments>,
<winAppData>, <home>...) y, si no se puede, se descarta. No se envía el
contenido de ninguna partida.

El servidor al que se envía se lee de contribuciones/servidor.json en el
repositorio de GitHub, así se puede cambiar sin publicar otra versión.
"""

import os
import re
import json
import time
import uuid
import hashlib
import urllib.request
from urllib.parse import urlparse

URL_CONFIG_SERVIDOR = ("https://raw.githubusercontent.com/aitor965/Arlequin-SaveHub/"
                       "refs/heads/main/contribuciones/servidor.json")
# Solo se envía a servidores de estos dominios (aunque servidor.json diga otra cosa).
DOMINIOS_PERMITIDOS = ("script.google.com", "workers.dev", "arlequinsavehub.com")
CLAVE_ACTIVADO = "ash2_contribuir"
CLAVE_ID = "ash2_contribuir_id"
INTERVALO_MINIMO = 20 * 3600          # como mucho un envío al día (aprox.)
MAX_ELEMENTOS = 300

# Carpetas típicas donde los juegos guardan partida (comodín, ruta relativa).
RAICES_BUSQUEDA = (
    ("<winDocuments>", ""), ("<winDocuments>", "My Games"), ("<home>", "Saved Games"),
    ("<winAppData>", ""), ("<winLocalAppData>", ""), ("<home>", "AppData/LocalLow"),
)
# Carpetas que nunca son la partida de un juego concreto.
NOMBRES_GENERICOS = {
    "microsoft", "windows", "temp", "cache", "logs", "packages", "programs", "google", "mozilla",
    "nvidia", "amd", "intel", "steam", "epic games", "epicgameslauncher", "gog com", "ubisoft", "ea games",
    "electronic arts", "origin", "battle net", "blizzard entertainment", "rockstar games", "my games",
    "saved games", "unity", "unreal engine", "crashdumps", "discord", "obs studio", "spotify",
}
# Programas que los launchers listan pero no son juegos (además de los del motor).
NO_JUEGOS = ("steamworks", "redistributable", "battleye", "easyanticheat", "steamvr", "wallpaper engine",
             "soundtrack", "dedicated server", "sdk", "benchmark")


def _norm(texto):
    texto = (texto or "").lower()
    for ch in "'’´`":
        texto = texto.replace(ch, "")
    texto = re.sub(r"[^\w]+", " ", texto, flags=re.UNICODE)
    return " ".join(texto.split())


def _barra(ruta):
    return str(ruta or "").replace("\\", "/").rstrip("/")


class Anonimizador:
    """Convierte rutas reales del equipo en plantillas con comodines."""

    def __init__(self, entorno, steam_root="", steam_ids=()):
        e = {k: _barra(v) for k, v in (entorno or {}).items() if isinstance(v, str)}
        home = e.get("home", "")
        self.usuario = (entorno or {}).get("osUserName", "") or os.path.basename(home)
        # Del más concreto al más general: primero las carpetas que están
        # dentro de <home> (Documentos, AppData...) y al final <home>.
        pares = [
            ("<winLocalAppData>", e.get("winLocalAppData", "")),
            ("<winAppData>", e.get("winAppData", "")),
            ("<winDocuments>", e.get("winDocuments", "")),
            ("<winPublic>", e.get("winPublic", "")),
            ("<winProgramData>", e.get("winProgramData", "")),
            ("<winDir>", e.get("winDir", "")),
            ("<root>", _barra(steam_root)),
            ("<home>", home),
        ]
        self.pares = [(c, v) for c, v in pares if v]
        self.pares.sort(key=lambda p: -len(p[1]))
        self.steam_ids = {str(i) for i in (steam_ids or ()) if str(i).strip()}

    def plantilla(self, ruta, base=""):
        """Plantilla con comodines, o "" si la ruta no se puede anonimizar."""
        ruta = _barra(ruta)
        if not ruta:
            return ""
        base = _barra(base)
        candidatos = ([("<base>", base)] if base else []) + self.pares
        candidatos.sort(key=lambda p: -len(p[1]))
        resultado = ""
        for comodin, valor in candidatos:
            if ruta.lower() == valor.lower() or ruta.lower().startswith(valor.lower() + "/"):
                resultado = comodin + ruta[len(valor):]
                break
        if not resultado:
            return ""   # otra unidad o carpeta propia del usuario: no se envía
        partes = resultado.split("/")
        for i, parte in enumerate(partes[1:], 1):
            if parte in self.steam_ids or re.fullmatch(r"\d{8,20}", parte):
                partes[i] = "<storeUserId>"
            elif self.usuario and parte.lower() == self.usuario.lower():
                partes[i] = "<osUserName>"
        resultado = "/".join(partes)
        # Última comprobación: que no quede el nombre de usuario en ningún sitio.
        if self.usuario and len(self.usuario) >= 3 and self.usuario.lower() in resultado.lower():
            return ""
        return resultado


def _carpeta_con_datos(ruta):
    """True si la carpeta tiene algún archivo (en ella o un nivel por debajo)."""
    try:
        with os.scandir(ruta) as it:
            for entrada in it:
                if entrada.is_file():
                    return True
                if entrada.is_dir():
                    try:
                        with os.scandir(entrada.path) as it2:
                            if any(x.is_file() for x in it2):
                                return True
                    except OSError:
                        continue
    except OSError:
        return False
    return False


def buscar_carpetas_candidatas(nombre_juego, entorno):
    """Carpetas con el nombre del juego en las ubicaciones típicas de
    partidas (y un nivel más abajo, para <Editora>/<Juego>)."""
    objetivo = _norm(nombre_juego)
    if len(objetivo) < 4:
        return []
    valores = {"<winDocuments>": entorno.get("winDocuments", ""), "<home>": entorno.get("home", ""),
               "<winAppData>": entorno.get("winAppData", ""), "<winLocalAppData>": entorno.get("winLocalAppData", "")}
    encontradas = []

    def coincide(nombre):
        n = _norm(nombre)
        if len(n) < 4 or n in NOMBRES_GENERICOS:
            return False
        return n == objetivo or (len(n) >= 6 and (n in objetivo or objetivo in n))

    for comodin, relativa in RAICES_BUSQUEDA:
        raiz = _barra(valores.get(comodin, ""))
        if not raiz:
            continue
        raiz = f"{raiz}/{relativa}" if relativa else raiz
        try:
            primer_nivel = [e for e in os.scandir(raiz) if e.is_dir()]
        except OSError:
            continue
        for e1 in primer_nivel:
            if coincide(e1.name):
                encontradas.append(_barra(e1.path))
                continue
            if _norm(e1.name) in NOMBRES_GENERICOS and _norm(e1.name) not in ("my games",):
                continue
            try:
                for e2 in os.scandir(e1.path):
                    if e2.is_dir() and coincide(e2.name):
                        encontradas.append(_barra(e2.path))
            except OSError:
                continue
    return [r for r in dict.fromkeys(encontradas) if _carpeta_con_datos(r)][:5]


def recopilar(gestor, motor):
    """Datos a enviar (ya anonimizados). No envía nada: solo los prepara."""
    entorno = motor.entorno_windows_base()
    steam_root = getattr(gestor, "_scan_steam_path", "") or ""
    try:
        steam_ids = motor.obtener_steam_user_ids(steam_root) if steam_root else []
    except Exception:
        steam_ids = []
    anon = Anonimizador(entorno, steam_root, steam_ids)
    rutas, sin_ruta = [], []

    # 1) Carpetas añadidas a mano por el usuario.
    for nombre, ruta in (getattr(gestor, "manuales", {}) or {}).items():
        plantilla = anon.plantilla(ruta)
        if plantilla:
            rutas.append({"juego": nombre, "launcher": "", "id_tienda": "", "plantilla": plantilla, "origen": "manual"})

    # 2) Juegos instalados que la base de datos no sabe dónde guardan.
    try:
        with open(motor.INSTALLED_GAMES_FILE, "r", encoding="utf-8") as f:
            inventario = json.load(f)
    except Exception:
        inventario = {}
    ocultos = {_norm(x) for x in (getattr(gestor, "ocultos", None) or ())}
    for juego in inventario.get("games", []) or []:
        estado = juego.get("save_status")
        if estado not in ("not_in_arlequin_db", "installed_not_resolved"):
            continue
        nombre = str(juego.get("name") or "").strip()
        if not nombre:
            continue
        n = _norm(nombre)
        if n in ocultos or any(x in n for x in NO_JUEGOS):
            continue
        try:
            if motor._es_exclusion_sistema(motor._norm(nombre)):
                continue
        except Exception:
            pass
        launcher = str(juego.get("launcher") or "")
        id_tienda = str(juego.get("id") or "")
        sin_ruta.append({"juego": nombre, "launcher": launcher, "id_tienda": id_tienda,
                         "en_bd": bool(juego.get("arlequin_db_match")), "estado": estado})
        base = juego.get("install_dir") or ""
        candidatas = []
        try:
            candidatas += motor.intuir_rutas_por_editoras_conocidas(nombre, entorno)
        except Exception:
            pass
        candidatas += buscar_carpetas_candidatas(nombre, entorno)
        for ruta in dict.fromkeys(candidatas):
            plantilla = anon.plantilla(ruta, base)
            if plantilla and plantilla.startswith("<") and plantilla.count("/") >= 1:
                rutas.append({"juego": nombre, "launcher": launcher, "id_tienda": id_tienda,
                              "plantilla": plantilla, "origen": "candidata"})

    return {"rutas": rutas[:MAX_ELEMENTOS], "sin_ruta": sin_ruta[:MAX_ELEMENTOS]}


# ---------------------------------------------------------------------------
#  Envío
# ---------------------------------------------------------------------------
def _huella(elemento):
    return hashlib.sha256(json.dumps(elemento, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


class Contribuidor:
    def __init__(self, motor, version_app, log=None):
        self.motor = motor
        self.version_app = version_app
        self.log = log or (lambda *a, **k: None)
        self.archivo_enviados = os.path.join(motor.APP_ARLEQUIN_SAVEHUB_DIR, "contribuciones_enviadas.json")
        self._servidor = (0.0, "")

    # -- configuración -------------------------------------------------------
    def _config(self):
        try:
            with open(self.motor.M_CFG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def activado(self):
        return bool(self._config().get(CLAVE_ACTIVADO, False))

    def activar(self, valor):
        cambios = {CLAVE_ACTIVADO: bool(valor)}
        if valor and not self._config().get(CLAVE_ID):
            # Identificador aleatorio de esta instalación: solo sirve para
            # contar cuántos equipos distintos confirman una misma ruta.
            cambios[CLAVE_ID] = uuid.uuid4().hex
        self.motor._actualizar_config(cambios)

    def _enviados(self):
        try:
            with open(self.archivo_enviados, "r", encoding="utf-8") as f:
                datos = json.load(f)
            return datos if isinstance(datos, dict) else {}
        except Exception:
            return {}

    def estado(self):
        enviados = self._enviados()
        return {"activado": self.activado(), "ultimo_envio": enviados.get("ultimo_envio", ""),
                "total_enviados": len(enviados.get("huellas", []))}

    def url_servidor(self):
        momento, url = self._servidor
        if url and time.time() - momento < 3600:
            return url
        try:
            with urllib.request.urlopen(URL_CONFIG_SERVIDOR, timeout=10) as r:
                datos = json.loads(r.read().decode("utf-8"))
            url = str(datos.get("url") or "").strip()
            host = (urlparse(url).hostname or "").lower()
            if not (url.startswith("https://") and any(host == d or host.endswith("." + d) for d in DOMINIOS_PERMITIDOS)):
                url = ""
        except Exception:
            url = ""
        self._servidor = (time.time(), url)
        return url

    # -- envío -----------------------------------------------------------------
    def pendientes(self, gestor):
        """Lo recopilado que todavía no se ha enviado nunca."""
        datos = recopilar(gestor, self.motor)
        ya = set(self._enviados().get("huellas", []))
        return {clave: [e for e in lista if _huella(e) not in ya] for clave, lista in datos.items()}

    def vista_previa(self, gestor):
        return {"todo": recopilar(gestor, self.motor), "pendiente": self.pendientes(gestor)}

    def enviar_si_toca(self, gestor, forzar=False):
        """Envía lo nuevo (si está activado). Devuelve un texto con el resultado."""
        if not self.activado():
            return "desactivado"
        enviados = self._enviados()
        if not forzar and time.time() - float(enviados.get("ultimo_intento", 0) or 0) < INTERVALO_MINIMO:
            return "espera"
        pendiente = self.pendientes(gestor)
        if not pendiente["rutas"] and not pendiente["sin_ruta"]:
            enviados["ultimo_intento"] = time.time()
            self._guardar_enviados(enviados)
            return "nada nuevo"
        url = self.url_servidor()
        if not url:
            return "servidor no disponible"
        cuerpo = {
            "version": 1, "app": self.version_app,
            "instalacion": self._config().get(CLAVE_ID) or "",
            "rutas": pendiente["rutas"], "sin_ruta": pendiente["sin_ruta"],
        }
        peticion = urllib.request.Request(url, data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"),
                                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(peticion, timeout=20) as r:
                respuesta = json.loads(r.read().decode("utf-8") or "{}")
            if not respuesta.get("ok"):
                raise RuntimeError(respuesta.get("error") or "respuesta no válida")
        except Exception as exc:
            self.log("WARNING", "No se pudieron enviar las rutas aprendidas: %s", exc)
            enviados["ultimo_intento"] = time.time()
            self._guardar_enviados(enviados)
            return "error"
        huellas = list(dict.fromkeys(list(enviados.get("huellas", [])) +
                                     [_huella(e) for e in pendiente["rutas"] + pendiente["sin_ruta"]]))
        enviados.update(huellas=huellas[-5000:], ultimo_intento=time.time(),
                        ultimo_envio=time.strftime("%d/%m/%Y %H:%M"))
        self._guardar_enviados(enviados)
        self.log("INFO", "Rutas aprendidas enviadas: %d rutas, %d juegos sin ruta.",
                 len(pendiente["rutas"]), len(pendiente["sin_ruta"]))
        return "enviado"

    def _guardar_enviados(self, datos):
        try:
            os.makedirs(os.path.dirname(self.archivo_enviados), exist_ok=True)
            temporal = self.archivo_enviados + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=1)
            os.replace(temporal, self.archivo_enviados)
        except Exception:
            pass
