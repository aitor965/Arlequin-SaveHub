# -*- coding: utf-8 -*-
"""
Prueba del inglés con el motor real: arranca `ash_web.py --pruebas` con un
APPDATA/perfil temporales configurados en inglés, comprueba textos del motor,
de la tabla y de un aviso, y deja el motor encendido para capturar la
interfaz (el llamador lo apaga).

Uso: python herramientas/prueba_idioma.py <carpeta_temporal> <puerto>
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def main(carpeta, puerto):
    carpeta = Path(carpeta)
    roaming = carpeta / "Roaming"
    perfil = carpeta / "perfil"
    (roaming / "Arlequin SaveHub").mkdir(parents=True, exist_ok=True)
    (perfil / "Desktop" / "Arlequin Backups").mkdir(parents=True, exist_ok=True)
    (roaming / "Arlequin SaveHub" / "config.json").write_text(json.dumps({
        "ash2_idioma": "en", "ash2_bienvenida": True,
        "backup_root": str(perfil / "Desktop" / "Arlequin Backups").replace("\\", "/"),
    }), encoding="utf-8")

    # 1) Traducciones del motor sin arrancar nada
    sys.path.insert(0, str(BASE))
    import traduccion
    traduccion.establecer("en")
    from traduccion import _t
    comprobaciones = {
        "Operación completada": "Operation completed",
        "Partidas {0}": "Saves {0}",
        "backup": "backup",
    }
    for es, en in comprobaciones.items():
        assert _t(es) == en, (es, _t(es))
    import ash_web
    traduccion.establecer("en")   # importar ash_web aplica el idioma de la config real
    assert _t(ash_web.INSTRUCCIONES_2).startswith("📘 HOW TO USE"), "instrucciones 2.0 sin traducir"
    print("traducciones del motor: OK")

    # 2) Motor real en inglés
    entorno = dict(os.environ, APPDATA=str(roaming), USERPROFILE=str(perfil), PYTHONIOENCODING="utf-8")
    proceso = subprocess.Popen([sys.executable, "-u", str(BASE / "ash_web.py"), "--pruebas", str(puerto)],
                               cwd=str(BASE), env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    (carpeta / "pid.txt").write_text(str(proceso.pid))

    def rpc(nombre, *args):
        peticion = urllib.request.Request(f"http://127.0.0.1:{puerto}/", data=json.dumps(
            {"nombre": nombre, "args": list(args)}).encode(), headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(peticion, timeout=60))["r"]

    for _ in range(40):
        try:
            rpc("iniciar")
            break
        except Exception:
            time.sleep(0.5)
    print("iniciar:", rpc("iniciar")["idioma"])
    for _ in range(240):   # esperar a que termine el primer escaneo (descarga la BD si hace falta)
        estado = rpc("estado")
        if estado.get("ultimo_escaneo_s") and not estado["escaneando"]:
            break
        time.sleep(1)
    textos = {k: v["texto"] for k, v in estado["textos"].items()}
    print("textos de estado:", json.dumps(textos, ensure_ascii=False))
    assert estado["idioma"] == "en"
    assert textos["partidas"].startswith("Saves"), textos["partidas"]

    # El aviso bloquea la llamada hasta que se responde (como en la app, donde
    # la interfaz lo recibe por esperar_eventos): se lanza en otro hilo.
    import threading
    hilo = threading.Thread(target=lambda: rpc("respaldar", []), daemon=True)
    hilo.start()
    avisos = []
    for _ in range(10):
        avisos += [e for e in rpc("esperar_eventos", 2) if e.get("tipo") == "dialogo"]
        if avisos:
            break
    print("aviso:", [(a["titulo"], a["mensaje"]) for a in avisos])
    assert avisos and avisos[0]["titulo"] == "Back up", avisos
    rpc("responder", avisos[0]["id"], "ok")
    hilo.join(10)

    opciones = rpc("opciones_cargar")
    assert opciones["idioma"] == "en"
    print("vista previa:", rpc("contribuir_vista_previa").splitlines()[0])
    print("== prueba de idioma OK ==")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
