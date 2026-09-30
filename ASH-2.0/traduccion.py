# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Idiomas de Arlequin SaveHub.

El texto original (en español) es la clave: el código escribe
_t("Texto en español") y, si el idioma activo es otro, se busca su
traducción en idiomas/<idioma>.json. Si falta una frase, se muestra en
español (nunca se rompe nada).

Idioma: el que elija el usuario en Opciones o, en "auto", el de Windows
(español, catalán, gallego y euskera -> español; cualquier otro -> inglés).
"""

import os
import sys
import json

IDIOMAS = ("es", "en")
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_CARPETA = os.path.join(_BASE, "idiomas")

_actual = "es"
_tablas = {}


def idioma_sistema():
    """Idioma de la interfaz de Windows ("es" o "en")."""
    try:
        import ctypes
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primario = langid & 0x3FF
        # 0x0A español, 0x03 catalán, 0x56 gallego, 0x2D euskera
        return "es" if primario in (0x0A, 0x03, 0x56, 0x2D) else "en"
    except Exception:
        idioma = (os.environ.get("LANG") or "").lower()
        return "es" if idioma.startswith(("es", "ca", "gl", "eu")) else "en"


def _tabla(idioma):
    if idioma not in _tablas:
        try:
            with open(os.path.join(_CARPETA, f"{idioma}.json"), "r", encoding="utf-8") as f:
                datos = json.load(f)
            _tablas[idioma] = {k: v for k, v in datos.items() if isinstance(v, str) and v}
        except Exception:
            _tablas[idioma] = {}
    return _tablas[idioma]


def establecer(preferencia):
    """preferencia: "auto", "es" o "en". Devuelve el idioma resultante."""
    global _actual
    idioma = idioma_sistema() if preferencia in (None, "", "auto") else preferencia
    _actual = idioma if idioma in IDIOMAS else "en"
    return _actual


def actual():
    return _actual


def miles(numero):
    """50240 -> "50.240" en español, "50,240" en inglés."""
    try:
        texto = f"{int(numero):,}"
    except (TypeError, ValueError):
        return str(numero)
    return texto.replace(",", ".") if _actual == "es" else texto


def _t(texto):
    """Traducción de `texto` al idioma activo (o el propio texto)."""
    if _actual == "es" or not isinstance(texto, str):
        return texto
    return _tabla(_actual).get(texto, texto)
