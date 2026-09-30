# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Arlequin SaveHub 2.0 (interfaz web) by aitor965 — https://github.com/aitor965/Arlequin-SaveHub

Interfaz nueva hecha con pywebview + React sobre el MISMO motor de la v1.1.9
(motor_v119.py, copia sin cambios de Arlequin_SaveHub_v1.1.9.py).

Cómo encaja:
  - El motor (clase GestorPartidasLocal) sigue funcionando igual, con su
    ventana de Tkinter OCULTA en un hilo propio. Todo lo que ya hacía
    (escaneo, backups, restauraciones, nube, automáticos...) se reutiliza
    tal cual, con los mismos archivos de datos y de configuración.
  - Los cuadros de mensaje del motor (messagebox, simpledialog, filedialog)
    se redirigen a la interfaz web.
  - La interfaz web lee el estado con un "long-poll" (esperar_eventos) y
    llama a las acciones a través de la clase Api (window.pywebview.api).
  - Las ventanas secundarias que aún no tienen versión web (p. ej. Opciones)
    se abren con su aspecto clásico de Tkinter por encima de la ventana.
"""

import os
import sys
import shutil
import json
import time
import uuid
import threading
import webbrowser
import traceback

import tkinter as tk

import webview

import motor_v119 as motor

VERSION_WEB = "2.0.0-beta.1"
TITULO = "Arlequin SaveHub"
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
CARPETA_WEB = os.path.join(_BASE, "web")
URL_DESARROLLO = os.environ.get("ASH_WEB_DEV_URL", "").strip()   # p. ej. http://localhost:5173

ENLACES_PERMITIDOS = {
    "paypal": motor.DONAR_PAYPAL_URL,
    "sponsors": motor.DONAR_GITHUB_SPONSORS_URL,
    "github": "https://github.com/aitor965/Arlequin-SaveHub",
    "web": "https://arlequinsavehub.com",
}


# ---------------------------------------------------------------------------
#  Canal de eventos Python -> web y diálogos bloqueantes
# ---------------------------------------------------------------------------
class Puente:
    def __init__(self):
        self._eventos = []
        self._cond = threading.Condition()
        self._pendientes = {}          # id -> [threading.Event, valor]
        self._lock = threading.Lock()
        self.root = None
        self.hilo_tk = None
        self.ventana = None
        self.cerrando = False

    # -- eventos -------------------------------------------------------------
    def emitir(self, tipo, **datos):
        datos["tipo"] = tipo
        with self._cond:
            if tipo in ("tabla", "estado"):
                # Avisos de "algo ha cambiado": basta con el último.
                self._eventos = [e for e in self._eventos if e.get("tipo") != tipo]
            self._eventos.append(datos)
            self._cond.notify_all()

    def esperar_eventos(self, timeout=15.0):
        with self._cond:
            if not self._eventos:
                self._cond.wait(timeout)
            eventos, self._eventos = self._eventos, []
        return eventos

    # -- diálogos ------------------------------------------------------------
    def _esperar(self, evento):
        """Espera a un evento. En el hilo de Tk se siguen procesando sus
        eventos (como hacía el bucle modal de messagebox) para que los
        root.after() de otros hilos no se queden atascados."""
        if threading.current_thread() is self.hilo_tk and self.root is not None:
            while not evento.is_set() and not self.cerrando:
                try:
                    self.root.update()
                except Exception:
                    evento.wait(0.05)
                    continue
                evento.wait(0.03)
        else:
            while not evento.is_set() and not self.cerrando:
                evento.wait(0.25)

    def preguntar(self, clase, por_defecto=None, **datos):
        if self.cerrando:
            return por_defecto
        ident = uuid.uuid4().hex
        evento = threading.Event()
        with self._lock:
            self._pendientes[ident] = [evento, por_defecto]
        self.emitir("dialogo", id=ident, clase=clase, **datos)
        self._esperar(evento)
        with self._lock:
            return self._pendientes.pop(ident, [None, por_defecto])[1]

    def responder(self, ident, valor):
        with self._lock:
            pendiente = self._pendientes.get(ident)
            if not pendiente:
                return False
            pendiente[1] = valor
            pendiente[0].set()
        return True

    def liberar_todo(self):
        self.cerrando = True
        with self._lock:
            for evento, _ in self._pendientes.values():
                evento.set()

    def en_tk(self, funcion):
        """Ejecuta `funcion` en el hilo de Tk (sin esperar)."""
        if self.root is None:
            return
        def envoltura():
            try:
                funcion()
            except Exception as exc:
                motor.logging.getLogger("ArlequinSaveManager").error(
                    "Error en acción de la interfaz: %s", exc, exc_info=True)
                self.emitir("toast", titulo="Error", texto=str(exc), error=True)
        try:
            self.root.after(0, envoltura)
        except Exception:
            pass


puente = Puente()


def _texto(valor):
    return "" if valor is None else str(valor)


class _MessageboxWeb:
    """Sustituye a tkinter.messagebox dentro del motor."""

    def _mostrar(self, clase, title=None, message=None, **_kw):
        puente.preguntar(clase, por_defecto="ok", titulo=_texto(title), mensaje=_texto(message))
        return "ok"

    def showinfo(self, title=None, message=None, **kw):
        return self._mostrar("info", title, message, **kw)

    def showwarning(self, title=None, message=None, **kw):
        return self._mostrar("aviso", title, message, **kw)

    def showerror(self, title=None, message=None, **kw):
        return self._mostrar("error", title, message, **kw)

    def askyesno(self, title=None, message=None, **_kw):
        return bool(puente.preguntar("sino", por_defecto=False, titulo=_texto(title), mensaje=_texto(message)))

    def askokcancel(self, title=None, message=None, **_kw):
        return bool(puente.preguntar("sino", por_defecto=False, titulo=_texto(title), mensaje=_texto(message),
                                     si="Aceptar", no="Cancelar"))

    def askretrycancel(self, title=None, message=None, **_kw):
        return bool(puente.preguntar("sino", por_defecto=False, titulo=_texto(title), mensaje=_texto(message),
                                     si="Reintentar", no="Cancelar"))

    def askquestion(self, title=None, message=None, **kw):
        return "yes" if self.askyesno(title, message, **kw) else "no"

    def askyesnocancel(self, title=None, message=None, **_kw):
        valor = puente.preguntar("sinocancelar", por_defecto=None, titulo=_texto(title), mensaje=_texto(message))
        return None if valor is None else bool(valor)


class _SimpledialogWeb:
    def askstring(self, title=None, prompt=None, initialvalue="", **_kw):
        valor = puente.preguntar("texto", por_defecto=None, titulo=_texto(title), mensaje=_texto(prompt),
                                 valor=_texto(initialvalue))
        return None if valor is None else str(valor)

    def askinteger(self, title=None, prompt=None, initialvalue=None, minvalue=None, maxvalue=None, **_kw):
        valor = puente.preguntar("numero", por_defecto=None, titulo=_texto(title), mensaje=_texto(prompt),
                                 valor=initialvalue, minimo=minvalue, maximo=maxvalue)
        try:
            return None if valor is None else int(valor)
        except (TypeError, ValueError):
            return None


def _elegir_carpeta(title=None, initialdir=None, **_kw):
    """Selector de carpeta nativo de Windows (el de pywebview)."""
    if puente.ventana is None:
        return ""
    resultado = {"ruta": ""}
    listo = threading.Event()

    def abrir():
        try:
            carpeta = initialdir if initialdir and os.path.isdir(str(initialdir)) else ""
            r = puente.ventana.create_file_dialog(webview.FileDialog.FOLDER, directory=carpeta)
            if r:
                resultado["ruta"] = str(r[0] if isinstance(r, (list, tuple)) else r).replace("\\", "/")
        except Exception as exc:
            motor.logging.getLogger("ArlequinSaveManager").warning("Selector de carpeta: %s", exc)
        finally:
            listo.set()

    threading.Thread(target=abrir, daemon=True).start()
    puente._esperar(listo)
    return resultado["ruta"]


class _FiledialogWeb:
    askdirectory = staticmethod(_elegir_carpeta)


motor.mb = _MessageboxWeb()
motor.sd = _SimpledialogWeb()
motor.fd = _FiledialogWeb()
# Color de cada nube en la interfaz: el de su marca y distinto entre ellas
# (Google Drive verde, OneDrive azul cielo, Dropbox azul intenso).
motor.ProveedorGoogleDrive.color = "#1fa463"
motor.ProveedorOneDrive.color = "#28a8ea"
motor.ProveedorDropbox.color = "#0061fe"


def espacio_disco(ruta):
    """Espacio del disco donde está `ruta` (sube hasta una carpeta que exista)."""
    ruta = os.path.abspath(str(ruta or "."))
    while ruta and not os.path.exists(ruta):
        padre = os.path.dirname(ruta)
        if padre == ruta:
            break
        ruta = padre
    try:
        uso = shutil.disk_usage(ruta)
    except OSError:
        return None
    unidad = os.path.splitdrive(ruta)[0] or ruta
    return {"unidad": unidad, "total": uso.total, "libre": uso.free, "usado": uso.used}


# El programa se actualiza con otra vía mientras la 2.0 esté en beta: la
# comprobación de la 1.1.x ofrecería instalar el .exe clásico encima.
motor.comprobar_actualizacion_disponible = lambda *a, **k: None


# Las ventanas clásicas que siguen existiendo (Opciones...) se abren por
# encima de la ventana web. Con la raíz de Tk oculta, "transient" las
# ocultaría también, así que se ignora.
_toplevel_init_original = tk.Toplevel.__init__


def _toplevel_init(self, *args, **kwargs):
    _toplevel_init_original(self, *args, **kwargs)
    try:
        def al_frente():
            try:
                self.attributes("-topmost", True)
                self.lift()
                self.focus_force()
                self.after(400, lambda: self.winfo_exists() and self.attributes("-topmost", False))
            except Exception:
                pass
        self.after(60, al_frente)
    except Exception:
        pass


tk.Toplevel.__init__ = _toplevel_init
tk.Toplevel.transient = lambda self, *a, **k: None
tk.Wm.transient = lambda self, *a, **k: None


# ---------------------------------------------------------------------------
#  Motor con los cambios mínimos para la interfaz web
# ---------------------------------------------------------------------------
class GestorWeb(motor.GestorPartidasLocal):

    def __init__(self, root):
        self._textos_ui = {}
        self._rev_tabla = 0
        self._tarea_actual = ""
        super().__init__(root)
        # La geometría que el motor aplica a su ventana (oculta) no importa.
        for clave, widget in (("update_status", self.lbl_update_status), ("db_stats", self.lbl_db_stats),
                              ("db_status", self.lbl_db_status), ("partidas", self.lbl_i),
                              ("launchers", self.lbl_launchers_status), ("ruta", self.lbl_r),
                              ("scan", self.btn_scan), ("nube", self.btn_nube)):
            self._espiar_widget(clave, widget)
        programar_original = self.box._programar

        def programar():
            self._rev_tabla += 1
            puente.emitir("tabla", rev=self._rev_tabla)
            programar_original()
        self.box._programar = programar
        invalidar_original = self.box.invalidar

        def invalidar():
            invalidar_original()
            self._rev_tabla += 1
            puente.emitir("tabla", rev=self._rev_tabla)
        self.box.invalidar = invalidar

    def _espiar_widget(self, clave, widget):
        try:
            self._textos_ui[clave] = {"texto": str(widget.cget("text")), "color": str(widget.cget("fg"))}
        except Exception:
            self._textos_ui[clave] = {"texto": "", "color": ""}
        original = widget.configure

        def configure(cnf=None, **kw):
            cambio = False
            if isinstance(cnf, dict):
                kw = {**cnf, **kw}
                cnf = None
            if "text" in kw:
                self._textos_ui[clave]["texto"] = str(kw["text"])
                cambio = True
            if "fg" in kw:
                self._textos_ui[clave]["color"] = str(kw["fg"])
                cambio = True
            if cambio:
                puente.emitir("estado")
            return original(cnf, **kw) if cnf is not None else original(**kw)
        widget.configure = configure
        widget.config = configure

    # -- ventana ---------------------------------------------------------------
    def centrar_ventana(self, ventana, ancho, alto):
        if ventana is self.root:
            return
        super().centrar_ventana(ventana, ancho, alto)

    def _restaurar_geometria_ventana(self):
        pass

    def _guardar_geometria_ventana(self):
        guardar_geometria_web()

    def _detectar_minimizado(self, _event=None):
        pass

    def ocultar_en_bandeja(self):
        if self._iniciar_bandeja() and puente.ventana is not None:
            puente.ventana.hide()

    def _mostrar_desde_bandeja(self, icono=None, item=None):
        if puente.ventana is not None:
            try:
                puente.ventana.show()
                puente.ventana.restore()
            except Exception:
                pass

    def _salir_desde_bandeja(self, icono=None, item=None):
        self._mostrar_desde_bandeja()
        threading.Thread(target=intentar_cerrar, daemon=True).start()

    def _cerrar_ventana_principal(self):
        threading.Thread(target=intentar_cerrar, daemon=True).start()

    # -- avisos y ventanas con versión web ---------------------------------------
    def _notificar(self, titulo, texto, error=False):
        icono = getattr(self, "_tray_icon", None)
        visible = not getattr(puente, "_ventana_oculta", False)
        if icono is not None and not visible:
            try:
                icono.notify(texto, titulo)
                return
            except Exception:
                pass
        puente.emitir("toast", titulo=_texto(titulo), texto=_texto(texto), error=bool(error))

    def _mostrar_diagnostico(self, texto, titulo="Diagnóstico", ajustar_instrucciones=False, ventana_padre=None):
        puente.emitir("texto", titulo=_texto(titulo), texto=_texto(texto))

    def mostrar_instrucciones_avanzadas(self, ventana_padre=None):
        # Se llama desde la ventana clásica de Opciones: esa sí se queda clásica.
        super().mostrar_instrucciones_avanzadas(ventana_padre)

    def abrir_link_donar(self):
        puente.emitir("abrir", panel="donar")

    def mostrar_nube(self):
        puente.emitir("abrir", panel="nube")
        puente.emitir("estado")

    def mostrar_submenu_ocultos(self):
        puente.emitir("abrir", panel="ocultos")

    def gestionar_carpetas_sin_launcher(self):
        puente.emitir("abrir", panel="sinlauncher")

    def mostrar_detalles_seleccionado(self, fila=None):
        seleccion = [fila] if fila else self.get_sel_list()
        if len(seleccion) == 1:
            puente.emitir("abrir", panel="detalles", id=seleccion[0])

    def _elegir_backup_para_restaurar(self, nombre_juego, candidatos):
        reciente = next((c[2] for c in candidatos if not str(c[1]).startswith("↩️")),
                        candidatos[0][2] if candidatos else None)
        opciones = [{"ts": c[0] or 0, "etiqueta": _texto(c[1]), "ruta": _texto(c[2])} for c in candidatos]
        ruta = puente.preguntar("elegir_backup", por_defecto=None, titulo="Varios backups encontrados",
                                juego=_texto(nombre_juego), opciones=opciones, reciente=_texto(reciente))
        if ruta and any(o["ruta"] == ruta for o in opciones):
            return ruta
        return None

    # Estas acciones del motor lanzaban un escaneo en el hilo de la interfaz;
    # aquí se lanza en segundo plano para no congelar nada.
    def hide(self):
        lista = self.get_sel_list()
        if lista and motor.mb.askyesno(
                "Ocultar", f"¿Quieres ocultar {'el juego seleccionado' if len(lista) == 1 else f'los {len(lista)} juegos seleccionados'} de la lista?\n\n"
                           "Podrás volver a mostrarlo desde Más → Gestionar ocultos."):
            for fila in lista:
                self.ocultos.add(self.limpiar_nombre_juego(fila))
            self.save_data(motor.M_O, self.ocultos)
            self.deseleccionar_todo_el_listado()
            self.ejecutar_web("Actualizando la lista", self.scan)

    def añadir_carpeta_manual(self):
        ruta = motor.fd.askdirectory(title="Selecciona la carpeta donde están las partidas guardadas")
        if not ruta:
            return
        nombre = motor.sd.askstring("Nombre del juego", "¿Qué nombre quieres darle a este juego en la lista?",
                                    initialvalue=os.path.basename(ruta.rstrip("/\\")))
        if not nombre or not nombre.strip():
            return
        nombre = nombre.strip()
        self.manuales[nombre] = ruta.replace("\\", "/")
        self.save_data(motor.M_M, [f"{k}|||{v}" for k, v in self.manuales.items()])
        self._notificar("Carpeta añadida", f"'{nombre}' se ha añadido a la lista.")
        self.ejecutar_web("Actualizando la lista", self.scan)

    def quitar_carpeta_manual(self):
        lista = self.get_sel_list()
        quitar = [n for n in (self.limpiar_nombre_juego(f) for f in lista) if n in self.manuales]
        if not quitar:
            motor.mb.showwarning("Quitar carpeta manual",
                                 "Ninguno de los juegos seleccionados es una carpeta añadida a mano.")
            return
        if motor.mb.askyesno("Quitar carpeta manual",
                             f"¿Quitar {len(quitar)} carpeta(s) manual(es) de la lista?\n\n"
                             "Esto NO borra tus partidas guardadas del disco."):
            for nombre in quitar:
                self.manuales.pop(nombre, None)
            self.save_data(motor.M_M, [f"{k}|||{v}" for k, v in self.manuales.items()])
            self.deseleccionar_todo_el_listado()
            self.ejecutar_web("Actualizando la lista", self.scan)

    def cambiar_carpeta(self):
        r = motor.fd.askdirectory(initialdir=self.dest, title="Elige la carpeta de backups")
        if r:
            self.dest = os.path.normpath(r).replace("\\", "/")
            self._guardar_ruta_backup_config(self.dest)
            self.lbl_r.config(text=f"Guardando en: {self.dest}")
            self.ejecutar_web("Actualizando la lista", self.scan)

    def comprobar_actualizaciones_al_inicio(self):
        # Ver motor.comprobar_actualizacion_disponible más arriba.
        self._set_estado_actualizacion(f"✓ ASH {VERSION_WEB}", "#2ecc71")

    # -- tareas con nombre para el indicador de actividad -----------------------
    def ejecutar_web(self, etiqueta, funcion):
        def envoltura():
            self._tarea_actual = etiqueta
            puente.emitir("estado")
            try:
                funcion()
            finally:
                self._tarea_actual = ""
                puente.emitir("estado")
        envoltura.__name__ = getattr(funcion, "__name__", "tarea")
        self.ejecutar_en_hilo(envoltura)


# ---------------------------------------------------------------------------
#  API expuesta a JavaScript (window.pywebview.api)
# ---------------------------------------------------------------------------
class Api:
    def __init__(self):
        self._g = None
        self._listo = threading.Event()
        self._filas_descarga = []
        self._progreso_descarga = None
        self._cache_nube = (0.0, None)

    # -- utilidades internas ---------------------------------------------------
    def _gestor(self):
        self._listo.wait(60)
        return self._g

    def _validos(self, ids):
        g = self._gestor()
        lineas = set(g.box._lineas)
        return [i for i in (ids or []) if i in lineas]

    def _seleccionar(self, ids):
        g = self._gestor()
        g.box._sel = set(self._validos(ids))

    def _bloqueado_por_escaneo(self):
        g = self._gestor()
        if getattr(g, "_escaneo_en_curso", False):
            puente.emitir("toast", titulo="Escaneando", texto="Espera a que termine el escaneo.", error=False)
            return True
        return False

    # -- arranque y eventos ------------------------------------------------------
    def iniciar(self):
        g = self._gestor()
        return {"version": VERSION_WEB, "version_motor": motor.APP_VERSION, "listo": g is not None,
                "filtros": list(motor.TablaJuegos.FILTROS)}

    def esperar_eventos(self, timeout=15):
        try:
            timeout = max(0.1, min(30.0, float(timeout)))
        except (TypeError, ValueError):
            timeout = 15.0
        return puente.esperar_eventos(timeout)

    def responder(self, ident, valor=None):
        return puente.responder(ident, valor)

    # -- estado ------------------------------------------------------------------
    def _nube_resumen(self, forzar=False):
        momento, datos = self._cache_nube
        if datos is not None and not forzar and time.monotonic() - momento < 2.0:
            return datos
        g = self._gestor()
        try:
            cfg = g._cargar_config_nube()
            conectada = g._nube_conectada()
            clase = g._nube_clase()
            datos = {
                "conectada": conectada, "clave": clase.clave if conectada else "",
                "nombre": clase.nombre if conectada else "", "color": clase.color if conectada else "",
                "cuenta": cfg.get("account", "") if conectada else "",
                "ultima_subida": cfg.get("last_upload", "") if conectada else "",
                "espacio": cfg.get("storage_text", "") if conectada else "",
                "auto": bool(cfg.get("auto")),
                "subiendo": bool(getattr(g, "_cloud_upload_active", False)),
                "descargando": bool(getattr(g, "_cloud_download_active", False)),
                "proveedores": [{"clave": c.clave, "nombre": c.nombre, "color": c.color,
                                 "configurado": bool(c.configurado())} for c in motor.NUBE_PROVEEDORES.values()],
            }
        except Exception as exc:
            datos = {"conectada": False, "error": str(exc), "proveedores": []}
        self._cache_nube = (time.monotonic(), datos)
        return datos

    def estado(self):
        g = self._gestor()
        ocupado = g._worker_lock.locked()
        return {
            "textos": {k: dict(v) for k, v in g._textos_ui.items()},
            "escaneando": bool(getattr(g, "_escaneo_en_curso", False)),
            "ocupado": ocupado,
            "tarea": g._tarea_actual or ("Trabajando…" if ocupado else ""),
            "rev": g._rev_tabla,
            "ruta_backups": g.dest,
            "disco": espacio_disco(g.dest),
            "nube": self._nube_resumen(),
            "bd_total": int(getattr(g, "manifest_total_juegos", 0) or 0),
            "ultimo_escaneo_s": g.ultimo_tiempo_escaneo,
            "version": VERSION_WEB,
            "version_motor": motor.APP_VERSION,
            "ocultos": len(g.ocultos or ()),
            "manuales": len(g.manuales or {}),
        }

    def tabla(self):
        g = self._gestor()
        box = g.box
        lineas = list(box._lineas)
        manuales = set((g.manuales or {}).keys())
        raiz, seccion, grupo, tienda = [], None, None, ""
        vistos = set()
        for texto in lineas:
            s = texto.strip()
            if not s:
                seccion = grupo = None
                tienda = ""
                continue
            if s.startswith("═"):
                seccion = {"tipo": "seccion", "texto": box._limpiar_cabecera(s), "clave": s, "hijos": []}
                raiz.append(seccion)
                grupo = None
                tienda = box._tienda_de_cabecera(s) if "SIN LAUNCHER" in s.upper() else ""
            elif s.startswith("---"):
                grupo = {"tipo": "grupo", "texto": box._limpiar_cabecera(s), "clave": s, "hijos": []}
                (seccion["hijos"] if seccion else raiz).append(grupo)
                tienda = box._tienda_de_cabecera(s)
            else:
                if texto in vistos:
                    continue
                vistos.add(texto)
                info = dict(box._info(texto))
                if not info.get("tienda"):
                    info["tienda"] = tienda
                nombre = info.get("nombre", "")
                nodo = {
                    "tipo": "juego", "id": texto, "nombre": nombre, "tienda": info.get("tienda", ""),
                    "local": int(info.get("local") or 0), "nube": int(info.get("nube") or 0),
                    "tamano": info.get("tamano", ""), "tamano_bytes": float(info.get("tamano_bytes") or 0),
                    "ultimo": info.get("ultimo", ""), "ultimo_ts": float(info.get("ultimo_ts") or 0),
                    "detalle": info.get("detalle", ""), "respaldable": bool(info.get("respaldable")),
                    "manual": nombre in manuales,
                }
                destino = grupo or seccion
                (destino["hijos"] if destino else raiz).append(nodo)
        return {"rev": g._rev_tabla, "arbol": raiz, "cerrados": sorted(box._cerrados),
                "seleccion": [t for t in box._sel if t in vistos]}

    def plegar(self, clave, cerrado):
        g = self._gestor()
        if cerrado:
            g.box._cerrados.add(clave)
        else:
            g.box._cerrados.discard(clave)
        g._guardar_grupos_cerrados(sorted(g.box._cerrados))
        return True

    # -- acciones principales ------------------------------------------------------
    def escanear(self):
        g = self._gestor()
        if getattr(g, "_escaneo_en_curso", False):
            return False
        g.ejecutar_web("Escaneando juegos", g.scan)
        return True

    def actualizar_todo(self):
        g = self._gestor()
        puente.en_tk(g._iniciar_actualizacion_completa)
        return True

    def respaldar(self, ids):
        if self._bloqueado_por_escaneo():
            return False
        g = self._gestor()
        lista = self._validos(ids)
        if not lista:
            motor.mb.showwarning("Respaldar", "Marca uno o varios juegos de la lista.")
            return False
        n = len(lista)
        g.ejecutar_web(f"Respaldando {n} juego{'s' if n != 1 else ''}",
                       lambda: g.op(1, lista_forzada=lista))
        return True

    def restaurar(self, ids):
        if self._bloqueado_por_escaneo():
            return False
        g = self._gestor()
        lista = self._validos(ids)
        if not lista:
            motor.mb.showwarning("Restaurar", "Marca uno o varios juegos de la lista.")
            return False
        n = len(lista)
        g.ejecutar_web(f"Restaurando {n} juego{'s' if n != 1 else ''}",
                       lambda: g.op(2, lista_forzada=lista))
        return True

    def ocultar(self, ids):
        if self._bloqueado_por_escaneo():
            return False
        g = self._gestor()

        def hacer():
            self._seleccionar(ids)
            g.hide()
        puente.en_tk(hacer)
        return True

    def anadir_carpeta(self):
        if self._bloqueado_por_escaneo():
            return False
        puente.en_tk(self._gestor().añadir_carpeta_manual)
        return True

    def quitar_manual(self, ids):
        if self._bloqueado_por_escaneo():
            return False
        g = self._gestor()

        def hacer():
            self._seleccionar(ids)
            g.quitar_carpeta_manual()
        puente.en_tk(hacer)
        return True

    def subir_a_nube(self, ids):
        if self._bloqueado_por_escaneo():
            return False
        g = self._gestor()
        lista = self._validos(ids)
        if not lista:
            return False
        if not g._nube_conectada():
            puente.emitir("abrir", panel="nube")
            return False
        g.ejecutar_web(f"Subiendo a {g._nube_nombre()}",
                       lambda: g._nube_subir_backups(juegos=lista, mostrar_resultado=True))
        return True

    def verificar_copia(self, ident):
        g = self._gestor()
        if ident not in g.box._lineas:
            return False
        g._verificar_copia_de(ident)
        return True

    def verificar_todas(self):
        g = self._gestor()
        g.ejecutar_web("Verificando copias", g.verificar_backups)
        return True

    def diagnostico(self, nombre=None):
        g = self._gestor()
        if nombre:
            g.ejecutar_web("Diagnóstico", lambda: g._diagnostico_juego_hilo(str(nombre)))
        else:
            puente.en_tk(g.diagnostico_juego)
        return True

    def estadisticas_bd(self):
        puente.en_tk(self._gestor().mostrar_estadisticas_bd)
        return True

    def instrucciones(self):
        puente.en_tk(self._gestor().mostrar_instrucciones)
        return True

    def opciones(self):
        puente.emitir("abrir", panel="opciones")
        return True

    def abrir_carpeta_backups(self):
        puente.en_tk(self._gestor().abrir_carpeta_backups)
        return True

    def cambiar_carpeta_backups(self):
        puente.en_tk(self._gestor().cambiar_carpeta)
        return True

    def abrir_carpeta_save(self, ident):
        g = self._gestor()
        rutas = [r for r in g._rutas_save_de(ident) if os.path.isdir(r)]
        if rutas:
            g._abrir_en_explorador(rutas[0])
            return True
        return False

    def abrir_carpeta_backup(self, ident):
        g = self._gestor()
        carpeta = g._carpeta_backup_de(ident)
        if carpeta and os.path.isdir(carpeta):
            g._abrir_en_explorador(carpeta)
            return True
        return False

    def abrir_ruta(self, ruta):
        """Abre en el Explorador una carpeta que la interfaz ha recibido del motor."""
        ruta = str(ruta or "")
        if ruta and os.path.isdir(ruta):
            self._gestor()._abrir_en_explorador(ruta)
            return True
        return False

    def abrir_enlace(self, clave):
        url = ENLACES_PERMITIDOS.get(str(clave))
        if url:
            webbrowser.open(url)
            return True
        return False

    def abrir_log(self):
        if os.path.exists(motor.LOG_FILE):
            os.startfile(os.path.normpath(motor.LOG_FILE))
            return True
        return False

    # -- detalles de un juego ----------------------------------------------------
    def detalles(self, ident, nombre=None):
        g = self._gestor()
        if ident not in g.box._lineas and nombre:
            # El texto de la fila cambia con sus copias: se busca por nombre.
            ident = next((t for t in list(g.box._lineas) if g.box._es_juego(t)
                          and g.limpiar_nombre_juego(t) == nombre), ident)
        if ident not in g.box._lineas:
            return None
        info = dict(g.box._info(ident))
        nombre = info.get("nombre") or g.limpiar_nombre_juego(ident)
        rutas = []
        for ruta in g._rutas_save_de(ident):
            try:
                modificado = g._formatear_fecha_es(os.path.getmtime(ruta))
            except Exception:
                modificado = ""
            rutas.append({"ruta": ruta, "existe": os.path.exists(ruta), "tamano": g.get_folder_size_str(ruta)
                          if os.path.exists(ruta) else "", "modificado": modificado})
        carpeta = g._carpeta_backup_de(ident)
        copias = []
        if carpeta:
            try:
                for ts, etiqueta, ruta in g._listar_todos_los_backups(carpeta):
                    copias.append({"ts": ts or 0, "etiqueta": etiqueta, "ruta": ruta})
            except Exception:
                pass
        nube = []
        try:
            entrada = ((g.cloud_manifest or {}).get("backups") or {}).get(g._clave_nube_juego(nombre))
            if isinstance(entrada, dict):
                for copia in g._nube_copias_ordenadas(entrada):
                    fecha, _ = g._fecha_drive_a_local(copia.get("createdTime"))
                    nube.append({"fecha": fecha or str(copia.get("uploaded_at", "")),
                                 "tamano": g._formatear_bytes(copia.get("size", 0))})
        except Exception:
            pass
        return {
            "id": ident, "nombre": nombre, "tienda": info.get("tienda", ""), "detalle": info.get("detalle", ""),
            "tamano": info.get("tamano", ""), "local": int(info.get("local") or 0),
            "nube": int(info.get("nube") or 0), "ultimo": info.get("ultimo", ""),
            "respaldable": bool(info.get("respaldable")), "rutas": rutas,
            "carpeta_backup": carpeta if carpeta and os.path.isdir(carpeta) else "",
            "copias": copias, "copias_nube": nube,
            "evidencia": _texto((g.juegos_evidencia or {}).get(ident, "")),
            "confianza": _texto((g.juegos_confianza or {}).get(ident, "")),
            "instalacion": _texto((g.juegos_installdir or {}).get(ident, "")),
            "manual": nombre in (g.manuales or {}),
            "escaneando": bool(getattr(g, "_escaneo_en_curso", False)),
        }

    # -- ocultos y carpetas sin launcher -------------------------------------------
    def ocultos_listar(self):
        return sorted(self._gestor().ocultos or (), key=str.casefold)

    def ocultos_mostrar(self, nombres):
        g = self._gestor()
        quitar = [n for n in (nombres or []) if n in g.ocultos]
        if not quitar:
            return False
        for n in quitar:
            g.ocultos.discard(n)
        g.save_data(motor.M_O, g.ocultos)
        g.ejecutar_web("Actualizando la lista", g.scan)
        return True

    def sinlauncher_listar(self):
        return list(self._gestor().carpetas_sin_launcher or [])

    def sinlauncher_anadir(self):
        g = self._gestor()
        r = motor.fd.askdirectory(title="Selecciona la carpeta raíz de tus juegos sin launcher")
        if r:
            r = r.replace("\\", "/")
            if r not in g.carpetas_sin_launcher:
                g.carpetas_sin_launcher.append(r)
                g.save_data(motor.M_C, g.carpetas_sin_launcher)
        return list(g.carpetas_sin_launcher)

    def sinlauncher_quitar(self, rutas):
        g = self._gestor()
        for r in rutas or []:
            if r in g.carpetas_sin_launcher:
                g.carpetas_sin_launcher.remove(r)
        g.save_data(motor.M_C, g.carpetas_sin_launcher)
        return list(g.carpetas_sin_launcher)

    def reescanear(self):
        return self.escanear()

    # -- nube --------------------------------------------------------------------
    def nube_estado(self):
        return self._nube_resumen(forzar=True)

    def nube_conectar(self, clave):
        g = self._gestor()
        if clave not in motor.NUBE_PROVEEDORES:
            return False
        g.conectar_nube(clave)
        return True

    def nube_desconectar(self):
        g = self._gestor()
        if not motor.mb.askyesno("Desconectar la nube",
                                 f"¿Desconectar {g._nube_nombre()}?\n\nLas copias ya subidas siguen en tu cuenta."):
            return False
        puente.en_tk(g.desconectar_nube)
        return True

    def nube_espacio(self):
        g = self._gestor()
        try:
            creds = g._nube_obtener_credenciales(pedir_json=False)
            if creds is None:
                return ""
            texto = g._nube_obtener_espacio_drive(creds)
            g._guardar_config_nube(cloud_storage_text=texto)
            return texto
        except Exception as exc:
            g._log("WARNING", "No se pudo consultar el espacio de la nube: %s", exc)
            return g._cargar_config_nube().get("storage_text", "")

    def nube_sincronizar(self, forzar=True):
        g = self._gestor()
        creds = g._nube_obtener_credenciales(pedir_json=False)
        if creds is None:
            return {"ok": False, "texto": f"No hay una conexión válida con {g._nube_nombre()}"}
        if forzar:
            g._cloud_manifest_sync_monotonic = 0.0
        try:
            if forzar:
                g._nube_sincronizar_manifest_nube(creds, mostrar_error=False, forzar=True)
            else:
                g._nube_sincronizar_manifest_nube_si_necesario(creds, mostrar_error=False, max_age=600.0)
            puente.en_tk(g._actualizar_indicadores_nube)
            return {"ok": True, "texto": f"Sincronizado con {g._nube_nombre()}"}
        except Exception as exc:
            g._log("WARNING", "No se pudo sincronizar la nube: %s", exc, exc_info=True)
            return {"ok": False, "texto": "No se pudo actualizar ahora; se usa el último estado conocido"}

    def nube_preparar(self):
        g = self._gestor()
        threading.Thread(target=g._nube_preparar_zips_nube, name="ASHCloudZipPreparer", daemon=True).start()
        return True

    def nube_cerrar_panel(self):
        g = self._gestor()
        if not getattr(g, "_cloud_upload_active", False):
            threading.Thread(target=g._nube_descartar_zips_preparados, daemon=True).start()
        return True

    def nube_subir_todo(self):
        g = self._gestor()
        if not g._nube_conectada():
            return False
        g.ejecutar_web(f"Subiendo a {g._nube_nombre()}",
                       lambda: g._nube_subir_backups(juegos=None, mostrar_resultado=True))
        return True

    def nube_lista_descarga(self):
        g = self._gestor()
        try:
            creds = g._nube_obtener_credenciales(pedir_json=False)
            if creds is None:
                raise RuntimeError(f"No hay una conexión válida con {g._nube_nombre()}.")
            filas = g._nube_listar_backups_para_descarga(creds)
        except Exception as exc:
            g._log("WARNING", "No se pudo cargar la lista de la nube: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc), "filas": []}
        self._filas_descarga = filas
        salida = []
        for idx, fila in enumerate(filas):
            copias = []
            for copia in g._nube_copias_ordenadas(fila["entrada"]):
                fecha, _ = g._fecha_drive_a_local(copia.get("createdTime"))
                copias.append({"id": str(copia.get("id", "")), "fecha": fecha or str(copia.get("uploaded_at", "")),
                               "tamano": g._formatear_bytes(copia.get("size", 0)),
                               "size": int(copia.get("size", 0) or 0)})
            salida.append({"idx": idx, "juego": fila["game"], "fecha": fila["fecha"], "size": fila["size"],
                           "tamano": g._formatear_bytes(fila["size"]), "estado": fila["estado"],
                           "copias": copias})
        return {"ok": True, "filas": salida}

    def _fila_efectiva(self, idx, copia_id=None):
        g = self._gestor()
        fila = self._filas_descarga[idx]
        if not copia_id or copia_id == str(fila["copy"].get("id", "")):
            return fila
        copia = next((c for c in g._nube_copias_ordenadas(fila["entrada"]) if str(c.get("id", "")) == copia_id), None)
        if copia is None:
            return fila
        if fila["estado"] == "no_local":
            estado = "no_local"
        else:
            huella = str(copia.get("backup_fingerprint") or "")
            estado = "igual" if huella and huella == g._huella_backup_local_rapida(fila["destino"]) else "distinta"
        fecha, _ = g._fecha_drive_a_local(copia.get("createdTime"))
        return dict(fila, copy=copia, size=int(copia.get("size", 0) or 0), estado=estado,
                    fecha=fecha or str(copia.get("uploaded_at", "") or ""), antigua=True)

    def nube_descargar(self, elegidas):
        g = self._gestor()
        if getattr(g, "_cloud_upload_active", False):
            motor.mb.showwarning("Nube", f"Hay una subida a {g._nube_nombre()} en curso. Espera a que termine.")
            return False
        if getattr(g, "_cloud_download_active", False):
            motor.mb.showinfo("Nube", "Ya hay una descarga en curso.")
            return False
        filas = []
        for e in elegidas or []:
            try:
                idx = int(e.get("idx"))
            except Exception:
                continue
            if 0 <= idx < len(self._filas_descarga):
                filas.append(self._fila_efectiva(idx, e.get("copia")))
        if not filas:
            return False
        distintas = [f["game"] for f in filas if f["estado"] == "distinta"]
        if distintas:
            lista = "\n".join("• " + n for n in distintas[:10])
            if len(distintas) > 10:
                lista += f"\n… y {len(distintas) - 10} más"
            if not motor.mb.askyesno(
                    "Confirmar descarga",
                    "Estos juegos ya tienen una copia local distinta:\n\n" + lista +
                    "\n\nTu copia local no se borra: se guardará como copia histórica con fecha "
                    "y la de la nube pasará a ser la copia actual.\n\n¿Continuar?"):
                return False
        cancelar = threading.Event()

        def actualizar(juego, paso, fraccion):
            puente.emitir("descarga", activo=True, juego=_texto(juego),
                          paso=("Cancelando…" if cancelar.is_set() else _texto(paso)),
                          fraccion=None if fraccion is None else max(0.0, min(1.0, float(fraccion))))

        def cerrar():
            puente.emitir("descarga", activo=False)

        self._progreso_descarga = {"cancelar": cancelar, "actualizar": actualizar, "cerrar": cerrar}
        puente.emitir("descarga", activo=True, juego="Preparando…", paso="", fraccion=None)
        g.ejecutar_web(f"Descargando de {g._nube_nombre()}",
                       lambda: g._nube_descargar_backups(filas, self._progreso_descarga))
        return True

    def nube_cancelar_descarga(self):
        if self._progreso_descarga:
            self._progreso_descarga["cancelar"].set()
            puente.emitir("descarga", activo=True, juego="", paso="Cancelando… (se termina el paso actual)",
                          fraccion=None)
        return True

    # -- opciones ------------------------------------------------------------------
    # Mismos datos y misma forma de guardarlos que la ventana clásica
    # (GestorPartidasLocal.mostrar_opciones -> guardar).
    def opciones_cargar(self):
        g = self._gestor()
        iniciar_windows, iniciar_minimizado, minimizar_en_bandeja = g._cargar_opciones_inicio()
        intervalo, _dias, al_cierre, _juegos, _ = g._cargar_opciones_respaldos_automaticos()
        auto_periodicos, auto_cierre = g._cargar_juegos_automaticos_por_modo()
        intervalo_valor, intervalo_unidad, _ = g._cargar_intervalo_respaldo_automatico()
        nube = g._cargar_config_nube()
        generales = g._cargar_opciones_generales()
        disponibles = list(dict.fromkeys(j for j, r in g.juegos.items() if r))

        def incluidos_nube(clave_excluidos, clave_incluidos):
            if not nube.get("exclusiones_configuradas", False):
                return list(disponibles)
            if clave_excluidos in nube:
                excl = {str(x) for x in (nube.get(clave_excluidos) or []) if str(x).strip()}
                return [j for j in disponibles if j not in excl]
            antiguos = nube.get(clave_incluidos)
            if isinstance(antiguos, list) and antiguos:
                antiguos = {str(x) for x in antiguos if str(x).strip()}
                return [j for j in disponibles if j in antiguos]
            return list(disponibles)

        def excluidos(incluidos):
            dentro = set(incluidos)
            return [j for j in disponibles if j not in dentro]

        unidad_nube = str(nube.get("periodic_unit", "días") or "días")
        compresion = str(nube.get("compresion", "Rápido") or "Rápido")
        return {
            "iniciar_windows": bool(iniciar_windows), "iniciar_minimizado": bool(iniciar_minimizado),
            "minimizar_en_bandeja": bool(minimizar_en_bandeja),
            "comprobar_actualizaciones": generales["comprobar_actualizaciones"],
            "avisos_automaticos": generales["avisos_automaticos"],
            "mostrar_sin_datos": generales["mostrar_sin_datos"], "mostrar_previstos": generales["mostrar_previstos"],
            "mostrar_online": generales["mostrar_online"],
            "hash_solo_idle": bool(nube.get("hash_solo_idle", False)),
            "hash_idle_min": int(nube.get("hash_idle_seconds", 300) or 300) // 60,
            "local_periodico": bool(intervalo), "local_valor": int(intervalo_valor or 1),
            "local_unidad": intervalo_unidad if intervalo_unidad in ("horas", "días", "semanas") else "días",
            "local_solo_idle": bool(g._cargar_solo_idle_automatico()),
            "local_cierre": bool(al_cierre),
            "max_backups": int(g.max_backups_historicos or 0),
            "copia_antes_restaurar": generales["copia_antes_restaurar"],
            "verificacion_semanal": generales["verificacion_semanal"],
            "patrones_exclusion": generales["patrones_exclusion"],
            "nube_periodica": bool(nube.get("auto", False)),
            "nube_valor": int(nube.get("periodic_value", nube.get("dias_periodicos", 7)) or 7),
            "nube_unidad": unidad_nube if unidad_nube in ("horas", "días", "semanas") else "días",
            "nube_cierre": bool(nube.get("al_cierre", False)),
            "max_copias_nube": int(nube.get("max_copias", 5)),
            "limite_subida": int(nube.get("upload_limit_kbps", 0) or 0),
            "no_red_medida": bool(nube.get("no_subir_red_medida", False)),
            "compresion": compresion if compresion in ("Rápido", "Equilibrado", "Máximo") else "Rápido",
            "anti_corrupcion": bool(nube.get("anti_corrupcion", False)),
            "anti_corrupcion_pct": int(nube.get("anti_corrupcion_pct", 30) or 30),
            "obs_pause": bool(nube.get("obs_pause_streaming", False)),
            "juegos": [{"id": j, "nombre": g.limpiar_nombre_juego(j)} for j in
                       sorted(disponibles, key=lambda x: g.limpiar_nombre_juego(x).lower())],
            "excluidos": {
                "local_periodico": excluidos(auto_periodicos), "local_cierre": excluidos(auto_cierre),
                "nube_periodico": excluidos(incluidos_nube("juegos_periodicos_excluidos", "juegos_periodicos")),
                "nube_cierre": excluidos(incluidos_nube("juegos_cierre_excluidos", "juegos_cierre")),
            },
            "avisos_opciones": list(g.OPCIONES_AVISOS),
            "nube_conectada": g._nube_conectada(),
        }

    def opciones_guardar(self, o):
        g = self._gestor()
        o = dict(o or {})

        def entero(clave, minimo, defecto):
            try:
                return max(minimo, int(o.get(clave, defecto)))
            except (TypeError, ValueError):
                return defecto

        unidades = ("horas", "días", "semanas")
        disponibles = list(dict.fromkeys(j for j, r in g.juegos.items() if r))

        def orden(x):
            return g.limpiar_nombre_juego(x).lower()

        excl = o.get("excluidos") or {}

        def incluidos(modo):
            fuera = set(excl.get(modo) or [])
            return sorted([j for j in disponibles if j not in fuera], key=orden)

        juegos_periodicos = incluidos("local_periodico")
        juegos_cierre = incluidos("local_cierre")
        nube_periodicos = incluidos("nube_periodico")
        nube_cierre = incluidos("nube_cierre")
        excluidos_periodicos = sorted([j for j in disponibles if j not in set(juegos_periodicos)], key=orden)
        excluidos_cierre = sorted([j for j in disponibles if j not in set(juegos_cierre)], key=orden)
        nuevos_juegos = list(dict.fromkeys(juegos_periodicos + juegos_cierre))

        iniciar_windows = bool(o.get("iniciar_windows"))
        iniciar_minimizado = bool(o.get("iniciar_minimizado")) and iniciar_windows
        bandeja = bool(o.get("minimizar_en_bandeja"))
        if not g._guardar_opciones_inicio(iniciar_windows, iniciar_minimizado, bandeja):
            return {"ok": False, "error": "No se pudieron guardar las opciones de inicio."}
        if not g._actualizar_inicio_windows(iniciar_windows, iniciar_minimizado):
            return {"ok": False, "error": "No se pudo actualizar el inicio automático de Windows."}
        g.minimizar_en_bandeja = bandeja

        _, _, _, _, ultimos = g._cargar_opciones_respaldos_automaticos()
        ultimos = {k: v for k, v in ultimos.items() if k in nuevos_juegos}
        if o.get("local_periodico"):
            ahora = time.time()
            for juego in nuevos_juegos:
                ultimos.setdefault(juego, ahora)

        max_backups = entero("max_backups", 0, 0)
        g.max_backups_historicos = max_backups
        g._guardar_max_backups(max_backups)

        valor_nube = entero("nube_valor", 1, 7)
        unidad_nube = o.get("nube_unidad") if o.get("nube_unidad") in unidades else "días"
        compresion = o.get("compresion") if o.get("compresion") in ("Rápido", "Equilibrado", "Máximo") else "Rápido"
        g._guardar_config_nube(
            cloud_exclusion_configured=True,
            cloud_auto_upload=bool(o.get("nube_periodica")),
            cloud_upload_when="Cada X días",
            cloud_upload_periodic_days=(valor_nube if unidad_nube == "días" else
                                        max(1, int(round(valor_nube * {"horas": 1 / 24, "semanas": 7}[unidad_nube])))),
            cloud_upload_periodic_value=valor_nube,
            cloud_upload_periodic_unit=unidad_nube,
            cloud_upload_on_close=bool(o.get("nube_cierre")),
            cloud_max_copias=entero("max_copias_nube", 0, 5),
            cloud_upload_limit_kbps=entero("limite_subida", 0, 0),
            cloud_no_upload_metered=bool(o.get("no_red_medida")),
            cloud_compression=compresion,
            hash_solo_idle=bool(o.get("hash_solo_idle")),
            hash_idle_seconds=max(30, entero("hash_idle_min", 1, 5) * 60),
            cloud_anti_corruption=bool(o.get("anti_corrupcion")),
            cloud_anti_corruption_pct=entero("anti_corrupcion_pct", 1, 30),
            obs_pause_streaming=bool(o.get("obs_pause")),
            cloud_periodic_games=list(dict.fromkeys(nube_periodicos)),
            cloud_close_games=list(dict.fromkeys(nube_cierre)),
            cloud_periodic_games_excluded=sorted([j for j in disponibles if j not in set(nube_periodicos)], key=orden),
            cloud_close_games_excluded=sorted([j for j in disponibles if j not in set(nube_cierre)], key=orden),
        )

        valor_local = entero("local_valor", 1, 1)
        unidad_local = o.get("local_unidad") if o.get("local_unidad") in unidades else "días"
        segundos = valor_local * {"horas": 3600, "días": 86400, "semanas": 604800}[unidad_local]
        if not g._guardar_opciones_respaldos_automaticos(
                bool(o.get("local_periodico")), max(1, int(round(segundos / 86400))), bool(o.get("local_cierre")),
                nuevos_juegos, ultimos, solo_idle=bool(o.get("local_solo_idle")),
                juegos_periodicos=juegos_periodicos, juegos_cierre=juegos_cierre,
                juegos_periodicos_excluidos=excluidos_periodicos, juegos_cierre_excluidos=excluidos_cierre,
                intervalo_valor=valor_local, intervalo_unidad=unidad_local):
            return {"ok": False, "error": "No se pudieron guardar los respaldos automáticos."}

        anteriores = g._cargar_opciones_generales()
        avisos = o.get("avisos_automaticos")
        generales = {
            "comprobar_actualizaciones": bool(o.get("comprobar_actualizaciones")),
            "mostrar_sin_datos": bool(o.get("mostrar_sin_datos")),
            "mostrar_previstos": bool(o.get("mostrar_previstos")),
            "mostrar_online": bool(o.get("mostrar_online")),
            "avisos_automaticos": avisos if avisos in g.OPCIONES_AVISOS else "Solo errores",
            "verificacion_semanal": bool(o.get("verificacion_semanal")),
            "copia_antes_restaurar": bool(o.get("copia_antes_restaurar")),
            "patrones_exclusion": str(o.get("patrones_exclusion") or "").strip(),
        }
        try:
            motor._actualizar_config({f"opcion_{k}": v for k, v in generales.items()})
        except Exception as exc:
            g._log("ERROR", "No se pudieron guardar las opciones generales: %s", exc)
        self._cache_nube = (0.0, None)
        cambia_lista = any(generales[k] != anteriores[k] for k in ("mostrar_sin_datos", "mostrar_previstos", "mostrar_online"))
        if cambia_lista and not getattr(g, "_escaneo_en_curso", False):
            g.ejecutar_web("Actualizando la lista", g.scan)
        puente.emitir("estado")
        return {"ok": True}

    def instrucciones_avanzadas(self):
        puente.en_tk(self._gestor().mostrar_instrucciones_avanzadas)
        return True

    def opciones_clasicas(self):
        puente.en_tk(self._gestor().mostrar_opciones)
        return True

    # -- ventana -------------------------------------------------------------------
    def ventana_minimizar(self):
        if puente.ventana:
            puente.ventana.minimize()

    def ventana_maximizar(self):
        if puente.ventana:
            if getattr(puente, "_maximizada", False):
                puente.ventana.restore()
            else:
                puente.ventana.maximize()

    def ventana_cerrar(self):
        threading.Thread(target=intentar_cerrar, daemon=True).start()

    def ventana_bandeja(self):
        g = self._gestor()
        puente.en_tk(g.ocultar_en_bandeja)


api = Api()


# ---------------------------------------------------------------------------
#  Cierre, geometría y arranque
# ---------------------------------------------------------------------------
_cierre_confirmado = threading.Event()
_cierre_en_curso = threading.Lock()


def intentar_cerrar():
    """Mismas comprobaciones que el cierre de la 1.1.9 (respaldos al cerrar,
    subidas/descargas en curso) y, si se confirma, cierra todo."""
    if not _cierre_en_curso.acquire(blocking=False):
        return
    try:
        g = api._g
        if g is not None:
            if not g._confirmar_cierre_si_respaldos_al_cierre():
                return
            if not g._confirmar_cierre_si_subida_nube():
                return
            guardar_geometria_web()
            try:
                if g._tray_icon is not None:
                    g._tray_icon.stop()
            except Exception:
                pass
            try:
                g._automaticos_detenidos.set()
            except Exception:
                pass
        _cierre_confirmado.set()
        puente.liberar_todo()
        if puente.root is not None:
            try:
                puente.root.after(0, puente.root.quit)
            except Exception:
                pass
        if puente.ventana is not None:
            puente.ventana.destroy()
    finally:
        _cierre_en_curso.release()


def _al_cerrar_ventana():
    if _cierre_confirmado.is_set():
        return True
    threading.Thread(target=intentar_cerrar, daemon=True).start()
    return False


_geometria = {"x": None, "y": None, "w": 1360, "h": 860}
_CLAVE_GEOMETRIA = "ash2_ventana2"
TAMANO_MINIMO = (1024, 680)
PROPORCION_INICIAL = 0.85   # de la zona útil de la pantalla (sin la barra de tareas)


def guardar_geometria_web():
    try:
        motor._actualizar_config({_CLAVE_GEOMETRIA: {
            "x": _geometria["x"], "y": _geometria["y"], "w": _geometria["w"], "h": _geometria["h"],
            "maximizada": bool(getattr(puente, "_maximizada", False))}})
    except Exception:
        pass


def _area_trabajo(punto=None):
    """Zona útil (sin barra de tareas) de la pantalla que contiene `punto`
    (en píxeles lógicos) o, si no se indica, la del ratón. Devuelve
    (x, y, ancho, alto) en píxeles LÓGICOS, que es lo que usa pywebview."""
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        anterior = None
        try:
            # Coordenadas reales aunque Windows escale la pantalla (125 %, 150 %...).
            anterior = u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass
        try:
            if punto is None:
                pt = wintypes.POINT()
                u32.GetCursorPos(ctypes.byref(pt))
            else:
                pt = wintypes.POINT(int(punto[0]), int(punto[1]))
            monitor = u32.MonitorFromPoint(pt, 2)   # MONITOR_DEFAULTTONEAREST

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            u32.GetMonitorInfoW(monitor, ctypes.byref(info))
            escala = 1.0
            try:
                dpi_x, dpi_y = wintypes.UINT(), wintypes.UINT()
                if ctypes.windll.shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                    escala = max(1.0, dpi_x.value / 96.0)
            except Exception:
                pass
            r = info.rcWork
            return (int(r.left / escala), int(r.top / escala),
                    int((r.right - r.left) / escala), int((r.bottom - r.top) / escala))
        finally:
            if anterior:
                try:
                    u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(anterior))
                except Exception:
                    pass
    except Exception:
        return None


def _geometria_inicial():
    """Tamaño a la medida de la pantalla donde se abre: el 85 % de su zona
    útil, centrado (sin llegar a maximizar). Si el usuario ya ajustó la
    ventana y sigue cabiendo en su pantalla, se respeta."""
    guardada = {}
    try:
        with open(motor.M_CFG, "r", encoding="utf-8") as f:
            guardada = json.load(f).get(_CLAVE_GEOMETRIA) or {}
    except Exception:
        pass
    try:
        gw, gh = int(guardada.get("w") or 0), int(guardada.get("h") or 0)
        gx, gy = guardada.get("x"), guardada.get("y")
        if gw and gh and isinstance(gx, (int, float)) and isinstance(gy, (int, float)):
            area = _area_trabajo((gx + gw / 2, gy + gh / 2))
            if area:
                ax, ay, aw, ah = area
                cx, cy = gx + gw / 2, gy + gh / 2
                if gw <= aw + 16 and gh <= ah + 16 and ax <= cx <= ax + aw and ay <= cy <= ay + ah:
                    _geometria.update(x=int(gx), y=int(gy), w=gw, h=gh)
                    return bool(guardada.get("maximizada")), area
    except Exception:
        pass
    area = _area_trabajo()
    if area:
        ax, ay, aw, ah = area
        w = min(aw, max(min(TAMANO_MINIMO[0], aw), int(aw * PROPORCION_INICIAL)))
        h = min(ah, max(min(TAMANO_MINIMO[1], ah), int(ah * PROPORCION_INICIAL)))
        _geometria.update(w=w, h=h, x=ax + (aw - w) // 2, y=ay + (ah - h) // 2)
    return bool(guardada.get("maximizada")), area


def _hilo_tk():
    puente.hilo_tk = threading.current_thread()
    root = tk.Tk()
    root.withdraw()
    puente.root = root
    try:
        if not motor.verificar_permisos_criticos(root):
            _cierre_confirmado.set()
            if puente.ventana is not None:
                puente.ventana.destroy()
            return
        api._g = GestorWeb(root)
        api._listo.set()
        puente.emitir("listo")
        puente.emitir("estado")
        if "--minimized" in sys.argv:
            root.after(300, api._g.ocultar_en_bandeja)
        root.mainloop()
    except Exception as exc:
        traceback.print_exc()
        puente.emitir("dialogo", id="fatal", clase="error", titulo="Error al iniciar",
                      mensaje=f"No se pudo iniciar el motor de Arlequin SaveHub:\n\n{exc}")
        api._listo.set()
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def _al_iniciar_ventana(ventana):
    threading.Thread(target=_hilo_tk, name="ASHMotorTk", daemon=True).start()


def _barra_titulo_oscura(ventana):
    """Barra de título oscura en Windows 10 (1809+) y 11, a juego con la interfaz."""
    if not motor._ES_WINDOWS:
        return
    try:
        import ctypes
        formulario = ventana.native
        hwnd = int(str(formulario.Handle.ToInt64()))
        valor = ctypes.c_int(1)
        for atributo in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (antes y después de 20H1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(valor),
                                                          ctypes.sizeof(valor)) == 0:
                break
        color = ctypes.c_int(0x000F0807)   # COLORREF 0x00BBGGRR -> #07080f (Windows 11)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
    except Exception:
        pass


def _servidor_pruebas(puerto):
    """Solo para desarrollo (--pruebas PUERTO): el motor real sin ventana y la
    API por HTTP en 127.0.0.1, para manejar la interfaz desde un navegador
    (frontend con ?rpc=PUERTO)."""
    import http.server

    class Manejador(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _cabeceras(self, codigo=200):
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_OPTIONS(self):
            self._cabeceras(204)

        def do_POST(self):
            try:
                datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                nombre = str(datos.get("nombre", ""))
                if nombre.startswith("_") or not callable(getattr(api, nombre, None)):
                    raise AttributeError(nombre)
                resultado = getattr(api, nombre)(*(datos.get("args") or []))
                cuerpo = json.dumps({"ok": True, "r": resultado}, default=str).encode("utf-8")
                self._cabeceras()
            except Exception as exc:
                traceback.print_exc()
                cuerpo = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self._cabeceras(500)
            self.wfile.write(cuerpo)

    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", int(puerto)), Manejador)
    print(f"ASH pruebas: API en http://127.0.0.1:{puerto}", flush=True)
    threading.Thread(target=_hilo_tk, name="ASHMotorTk", daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    if "--pruebas" in sys.argv:
        _servidor_pruebas(sys.argv[sys.argv.index("--pruebas") + 1])
        return
    motor._fijar_identidad_taskbar_windows()
    maximizada, area = _geometria_inicial()
    minimo = TAMANO_MINIMO
    if area:
        # En pantallas pequeñas el mínimo no puede ser mayor que la pantalla.
        minimo = (min(TAMANO_MINIMO[0], area[2]), min(TAMANO_MINIMO[1], area[3]))
    if URL_DESARROLLO:
        url = URL_DESARROLLO
    else:
        url = os.path.join(CARPETA_WEB, "index.html")
    ventana = webview.create_window(
        TITULO, url, js_api=api,
        width=_geometria["w"], height=_geometria["h"], x=_geometria["x"], y=_geometria["y"],
        min_size=minimo, background_color="#07080f", text_select=False,
        hidden="--minimized" in sys.argv, maximized=maximizada,
    )
    puente.ventana = ventana
    puente._maximizada = maximizada
    puente._ventana_oculta = "--minimized" in sys.argv

    def al_mover(x, y):
        if not getattr(puente, "_maximizada", False):
            _geometria.update(x=x, y=y)

    def al_redimensionar(w, h):
        if not getattr(puente, "_maximizada", False):
            _geometria.update(w=w, h=h)

    def al_maximizar():
        puente._maximizada = True

    def al_restaurar():
        puente._maximizada = False
        puente._ventana_oculta = False

    def al_minimizar():
        g = api._g
        if g is not None and getattr(g, "minimizar_en_bandeja", False):
            puente.en_tk(g.ocultar_en_bandeja)

    def al_mostrar():
        puente._ventana_oculta = False
        _barra_titulo_oscura(ventana)

    def al_ocultar():
        puente._ventana_oculta = True

    ventana.events.closing += _al_cerrar_ventana
    ventana.events.moved += al_mover
    ventana.events.resized += al_redimensionar
    ventana.events.maximized += al_maximizar
    ventana.events.restored += al_restaurar
    ventana.events.minimized += al_minimizar
    ventana.events.shown += al_mostrar
    try:
        ventana.events.hidden += al_ocultar
    except Exception:
        pass

    icono = os.path.join(_BASE, "icono.ico")
    webview.start(_al_iniciar_ventana, (ventana,), http_server=not URL_DESARROLLO,
                  icon=icono if os.path.exists(icono) else None,
                  private_mode=False,
                  storage_path=os.path.join(motor.APP_ARLEQUIN_SAVEHUB_DIR, "WebView"))
    puente.liberar_todo()


if __name__ == "__main__":
    main()
