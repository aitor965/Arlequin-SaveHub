# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Consumo de recursos de Arlequin SaveHub (CPU, RAM, disco y red).

Se mide TODO lo que es de ASH: su propio proceso y sus procesos hijos
(la interfaz WebView2 y robocopy mientras hace copias), con las APIs de
Windows (ctypes), sin dependencias extra.

  - CPU:   tiempo de CPU del árbol de procesos / tiempo real / nº de núcleos.
  - RAM:   memoria en uso (working set) del árbol de procesos.
  - Disco: bytes leídos + escritos por segundo (contadores de E/S).
  - Red:   bytes enviados + recibidos por ASH (nube, base de datos, etc.),
           contados en los sockets de Python.
"""

import os
import ssl
import time
import socket
import threading
from collections import deque

HISTORIAL = 120          # muestras (1 por segundo -> 2 minutos)

# ---------------------------------------------------------------------------
#  Red: contador de bytes en los sockets de Python
# ---------------------------------------------------------------------------
_red = {"enviados": 0, "recibidos": 0}
_red_lock = threading.Lock()


def _sumar(clave, n):
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return
    if n > 0:
        with _red_lock:
            _red[clave] += n


def _envolver(clase, nombre, clave, desde_resultado):
    original = getattr(clase, nombre, None)
    if original is None or getattr(original, "_ash_contado", False):
        return

    def envoltura(self, *args, **kwargs):
        resultado = original(self, *args, **kwargs)
        _sumar(clave, desde_resultado(resultado, args))
        return resultado
    envoltura._ash_contado = True
    setattr(clase, nombre, envoltura)


def instalar_contador_red():
    longitud = lambda r, a: len(r) if isinstance(r, (bytes, bytearray)) else 0   # noqa: E731
    numero = lambda r, a: r if isinstance(r, int) else 0                           # noqa: E731
    enviado_todo = lambda r, a: len(a[0]) if a and hasattr(a[0], "__len__") else 0  # noqa: E731
    # HTTPS (casi todo el tráfico de ASH): se cuenta en SSLSocket. Su
    # sendall() llama a send() y su recv() a read(), así que solo se cuentan
    # send, recv y recv_into para no sumar dos veces.
    _envolver(ssl.SSLSocket, "send", "enviados", numero)
    _envolver(ssl.SSLSocket, "recv", "recibidos", longitud)
    _envolver(ssl.SSLSocket, "recv_into", "recibidos", numero)
    # HTTP sin cifrar (inicio de sesión OAuth en localhost, etc.).
    _envolver(socket.socket, "send", "enviados", numero)
    _envolver(socket.socket, "sendall", "enviados", enviado_todo)
    _envolver(socket.socket, "recv", "recibidos", longitud)
    _envolver(socket.socket, "recv_into", "recibidos", numero)


def bytes_red():
    with _red_lock:
        return _red["enviados"], _red["recibidos"]


# ---------------------------------------------------------------------------
#  CPU, RAM y disco del árbol de procesos (Windows)
# ---------------------------------------------------------------------------
try:
    import ctypes
    from ctypes import wintypes

    # PyDLL: las llamadas son instantáneas y así no sueltan el GIL (con WinDLL,
    # cada llamada tendría que esperar a recuperarlo si otro hilo está ocupado).
    _k32 = ctypes.PyDLL("kernel32", use_last_error=True)
    _psapi = ctypes.PyDLL("psapi", use_last_error=True)

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.OpenProcess.restype = wintypes.HANDLE
    _WINDOWS = True
except Exception:   # fuera de Windows
    _WINDOWS = False

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value if _WINDOWS else None


def _procesos():
    """{pid: (pid_padre, nombre)} de todos los procesos del sistema."""
    resultado = {}
    instantanea = _k32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
    if not instantanea or instantanea == INVALID_HANDLE_VALUE:
        return resultado
    try:
        entrada = PROCESSENTRY32W()
        entrada.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = _k32.Process32FirstW(instantanea, ctypes.byref(entrada))
        while ok:
            resultado[entrada.th32ProcessID] = (entrada.th32ParentProcessID, entrada.szExeFile)
            ok = _k32.Process32NextW(instantanea, ctypes.byref(entrada))
    finally:
        _k32.CloseHandle(instantanea)
    return resultado


def _arbol(pid_raiz):
    """[(pid, nombre)] de ASH y de todos sus descendientes."""
    procesos = _procesos()
    hijos = {}
    for pid, (padre, nombre) in procesos.items():
        hijos.setdefault(padre, []).append(pid)
    salida, pendientes = [], [pid_raiz]
    vistos = set()
    while pendientes:
        pid = pendientes.pop()
        if pid in vistos:
            continue
        vistos.add(pid)
        salida.append((pid, procesos.get(pid, (0, "ASH"))[1]))
        pendientes.extend(p for p in hijos.get(pid, []) if p != pid)
    return salida


def _medir_proceso(pid):
    """(cpu_100ns, ram_bytes, disco_bytes) o None si no se puede abrir."""
    manejador = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not manejador:
        return None
    try:
        creado, salido, nucleo, usuario = (wintypes.FILETIME() for _ in range(4))
        cpu = 0
        if _k32.GetProcessTimes(manejador, ctypes.byref(creado), ctypes.byref(salido),
                                ctypes.byref(nucleo), ctypes.byref(usuario)):
            cpu = ((nucleo.dwHighDateTime << 32) | nucleo.dwLowDateTime) + \
                  ((usuario.dwHighDateTime << 32) | usuario.dwLowDateTime)
        memoria = PROCESS_MEMORY_COUNTERS()
        memoria.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        ram = memoria.WorkingSetSize if _psapi.GetProcessMemoryInfo(
            manejador, ctypes.byref(memoria), memoria.cb) else 0
        io = IO_COUNTERS()
        disco = (io.ReadTransferCount + io.WriteTransferCount) if _k32.GetProcessIoCounters(
            manejador, ctypes.byref(io)) else 0
        return cpu, ram, disco
    finally:
        _k32.CloseHandle(manejador)


def ram_total():
    if not _WINDOWS:
        return 0
    estado = MEMORYSTATUSEX()
    estado.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    return estado.ullTotalPhys if _k32.GlobalMemoryStatusEx(ctypes.byref(estado)) else 0


def _grupo(nombre):
    n = (nombre or "").lower()
    if "webview" in n or "msedge" in n:
        return "interfaz"
    if "robocopy" in n or n in ("reg.exe", "cmd.exe", "conhost.exe", "powershell.exe"):
        return "copias"
    return "motor"


class Monitor:
    """Toma una muestra por segundo en segundo plano y guarda el historial."""

    def __init__(self):
        self.pid = os.getpid()
        self.nucleos = os.cpu_count() or 1
        self.ram_total = ram_total()
        self.historial = deque(maxlen=HISTORIAL)
        self._anterior = {}          # pid -> (cpu_100ns, disco_bytes)
        self._anterior_red = bytes_red()
        self._momento = time.monotonic()
        self._lock = threading.Lock()
        self._activo = False

    def iniciar(self):
        if self._activo or not _WINDOWS:
            return
        self._activo = True
        threading.Thread(target=self._bucle, name="ASHRecursos", daemon=True).start()

    def _bucle(self):
        while self._activo:
            try:
                self._muestra()
            except Exception:
                pass
            time.sleep(1.0)

    def _muestra(self):
        ahora = time.monotonic()
        segundos = max(0.2, ahora - self._momento)
        self._momento = ahora
        grupos = {g: {"cpu": 0.0, "ram": 0, "disco": 0.0, "procesos": 0} for g in ("motor", "interfaz", "copias")}
        nuevo_anterior = {}
        for pid, nombre in _arbol(self.pid):
            datos = _medir_proceso(pid)
            if datos is None:
                continue
            cpu, ram, disco = datos
            cpu_prev, disco_prev = self._anterior.get(pid, (cpu, disco))
            nuevo_anterior[pid] = (cpu, disco)
            g = grupos[_grupo(nombre)]
            g["cpu"] += max(0, cpu - cpu_prev) / 1e7 / segundos / self.nucleos * 100
            g["ram"] += ram
            g["disco"] += max(0, disco - disco_prev) / segundos
            g["procesos"] += 1
        self._anterior = nuevo_anterior
        enviados, recibidos = bytes_red()
        env_prev, rec_prev = self._anterior_red
        self._anterior_red = (enviados, recibidos)
        muestra = {
            "t": time.time(),
            "cpu": round(min(100.0, sum(g["cpu"] for g in grupos.values())), 2),
            "ram": sum(g["ram"] for g in grupos.values()),
            "disco": round(sum(g["disco"] for g in grupos.values())),
            "red_subida": round(max(0, enviados - env_prev) / segundos),
            "red_bajada": round(max(0, recibidos - rec_prev) / segundos),
            "grupos": {k: {"cpu": round(v["cpu"], 2), "ram": v["ram"], "disco": round(v["disco"]),
                           "procesos": v["procesos"]} for k, v in grupos.items()},
        }
        with self._lock:
            self.historial.append(muestra)

    def datos(self, completo=False):
        with self._lock:
            historial = list(self.historial)
        enviados, recibidos = bytes_red()
        salida = {
            "actual": historial[-1] if historial else None,
            "nucleos": self.nucleos, "ram_total": self.ram_total,
            "red_total": {"enviados": enviados, "recibidos": recibidos},
            "disponible": _WINDOWS,
        }
        if completo:
            salida["historial"] = [{k: m[k] for k in ("t", "cpu", "ram", "disco", "red_subida", "red_bajada")}
                                   for m in historial]
        return salida
