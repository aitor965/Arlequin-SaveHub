# -*- coding: utf-8 -*-
"""
Genera motor.py a partir de motor_v119.py envolviendo en _t(...) los textos
que ve el usuario, para poder traducirlos (traduccion.py).

  - "texto"          -> _t("texto")
  - f"texto {x:.1f}" -> _t("texto {0:.1f}").format(x)

Solo se tocan textos en contextos que llegan a la pantalla (cuadros de
mensaje, avisos, textos de estado, listas y variables de mensajes). Los logs,
las claves internas y las cabeceras de la tabla no se tocan.

Además escribe idiomas/_catalogo.json con todas las frases (clave -> "").

Uso: python herramientas/envolver_textos.py motor_v119.py motor.py
"""

import ast
import re
import sys
import json
from pathlib import Path

LLAMADAS_MB = {"showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askretrycancel",
               "askquestion", "askyesnocancel"}
METODOS_TEXTO = {"_notificar", "_mostrar_diagnostico", "_set_estado_actualizacion"}
LISTAS = {"fallidas", "errores", "problemas", "partes", "resumen", "lineas", "notas"}
VARIABLES = {"texto", "texto_resultado", "texto_final", "detalle", "extra", "detalle_iguales", "extra_iguales",
             "lista_txt", "texto_bd", "riesgo", "verbo", "mensaje", "aviso_admin", "resumen", "etiqueta",
             "mod", "texto_espacio", "texto_fecha"}
FUNCIONES_RETORNO = {"_verificar_integridad_backup", "_nube_descargar_un_backup", "_nube_obtener_espacio_drive",
                     "_fecha_relativa"}
LETRAS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}")


def es_texto(nodo):
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return bool(LETRAS.search(nodo.value)) and not nodo.value.lstrip().startswith(("═", "---"))
    if isinstance(nodo, ast.JoinedStr):
        constantes = "".join(v.value for v in nodo.values if isinstance(v, ast.Constant))
        return bool(LETRAS.search(constantes)) and not constantes.lstrip().startswith(("═", "---"))
    return False


def recoger(nodo, salida, solo_con_espacios=False):
    """Textos a envolver dentro de una expresión, bajando solo por formas
    'de texto' (concatenaciones, if/else, listas, tuplas, join)."""
    if nodo is None:
        return
    if isinstance(nodo, (ast.Constant, ast.JoinedStr)):
        if es_texto(nodo):
            if solo_con_espacios and isinstance(nodo, ast.Constant) and " " not in nodo.value.strip():
                return
            salida.append(nodo)
        return
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, (ast.Add, ast.Mod)):
        recoger(nodo.left, salida, solo_con_espacios)
        if isinstance(nodo.op, ast.Add):
            recoger(nodo.right, salida, solo_con_espacios)
    elif isinstance(nodo, ast.IfExp):
        recoger(nodo.body, salida, solo_con_espacios)
        recoger(nodo.orelse, salida, solo_con_espacios)
    elif isinstance(nodo, (ast.List, ast.Tuple)):
        for e in nodo.elts:
            recoger(e, salida, solo_con_espacios)
    elif isinstance(nodo, ast.Starred):
        recoger(nodo.value, salida, solo_con_espacios)
    elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "join":
        for a in nodo.args:
            recoger(a, salida, solo_con_espacios)
    elif isinstance(nodo, (ast.ListComp, ast.GeneratorExp)):
        recoger(nodo.elt, salida, solo_con_espacios)
    elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "strftime":
        # momento.strftime("hoy %H:%M")
        for a in nodo.args:
            recoger(a, salida, solo_con_espacios)


class Buscador(ast.NodeVisitor):
    def __init__(self):
        self.textos = []
        self.funcion = []

    def visit_FunctionDef(self, nodo):
        self.funcion.append(nodo.name)
        self.generic_visit(nodo)
        self.funcion.pop()

    def visit_Call(self, nodo):
        f = nodo.func
        if isinstance(f, ast.Attribute):
            if f.attr in LLAMADAS_MB and isinstance(f.value, ast.Name) and f.value.id == "mb":
                for a in nodo.args:
                    recoger(a, self.textos)
                for k in nodo.keywords:
                    if k.arg in ("title", "message"):
                        recoger(k.value, self.textos)
            elif f.attr == "askstring" and isinstance(f.value, ast.Name) and f.value.id == "sd":
                for a in nodo.args[:2]:
                    recoger(a, self.textos)
            elif f.attr in METODOS_TEXTO:
                for a in nodo.args[:2]:
                    recoger(a, self.textos)
                for k in nodo.keywords:
                    if k.arg in ("titulo", "texto"):
                        recoger(k.value, self.textos)
            elif f.attr in ("config", "configure"):
                for k in nodo.keywords:
                    if k.arg == "text":
                        recoger(k.value, self.textos)
            elif f.attr in ("append", "extend", "insert") and isinstance(f.value, ast.Name) and f.value.id in LISTAS:
                for a in nodo.args:
                    recoger(a, self.textos)
        self.generic_visit(nodo)

    def visit_Assign(self, nodo):
        for objetivo in nodo.targets:
            if isinstance(objetivo, ast.Name) and (objetivo.id in VARIABLES or objetivo.id in LISTAS):
                recoger(nodo.value, self.textos)
        self.generic_visit(nodo)

    def visit_AugAssign(self, nodo):
        if isinstance(nodo.target, ast.Name) and (nodo.target.id in VARIABLES or nodo.target.id in LISTAS):
            recoger(nodo.value, self.textos)
        self.generic_visit(nodo)

    def visit_Return(self, nodo):
        if self.funcion and self.funcion[-1] in FUNCIONES_RETORNO:
            recoger(nodo.value, self.textos, solo_con_espacios=True)
        self.generic_visit(nodo)


def main(origen, destino):
    fuente = Path(origen).read_text(encoding="utf-8")
    datos = fuente.encode("utf-8")
    lineas = fuente.splitlines(keepends=True)
    inicio_linea = [0]
    for l in lineas:
        inicio_linea.append(inicio_linea[-1] + len(l.encode("utf-8")))

    def desplazamiento(linea, columna):
        return inicio_linea[linea - 1] + columna   # col_offset ya es en bytes UTF-8

    arbol = ast.parse(fuente)
    buscador = Buscador()
    buscador.visit(arbol)

    # Sin duplicados ni nodos dentro de otros ya elegidos.
    elegidos = {}
    for n in buscador.textos:
        elegidos[(n.lineno, n.col_offset, n.end_lineno, n.end_col_offset)] = n
    rangos = sorted(elegidos.items(), key=lambda kv: (desplazamiento(kv[0][0], kv[0][1]),
                                                      -desplazamiento(kv[0][2], kv[0][3])))
    finales, fin_actual = [], -1
    for clave, n in rangos:
        ini = desplazamiento(n.lineno, n.col_offset)
        fin = desplazamiento(n.end_lineno, n.end_col_offset)
        if ini < fin_actual:
            continue   # dentro de otro texto ya elegido
        finales.append((ini, fin, n))
        fin_actual = fin

    catalogo = {}
    omitidos = []

    def segmento(nodo):
        return datos[desplazamiento(nodo.lineno, nodo.col_offset):desplazamiento(nodo.end_lineno, nodo.end_col_offset)].decode("utf-8")

    def convertir(nodo):
        if isinstance(nodo, ast.Constant):
            catalogo.setdefault(nodo.value, "")
            return f"_t({nodo.value!r})"
        plantilla, argumentos = [], []
        for v in nodo.values:
            if isinstance(v, ast.Constant):
                plantilla.append(v.value.replace("{", "{{").replace("}", "}}"))
            else:
                if v.format_spec is not None and any(not isinstance(x, ast.Constant) for x in v.format_spec.values):
                    return None
                conversion = {-1: "", 115: "!s", 114: "!r", 97: "!a"}[v.conversion]
                spec = ""
                if v.format_spec is not None:
                    spec = ":" + "".join(x.value for x in v.format_spec.values)
                plantilla.append("{" + str(len(argumentos)) + conversion + spec + "}")
                argumentos.append(segmento(v.value))
        texto = "".join(plantilla)
        catalogo.setdefault(texto, "")
        if not argumentos:
            return f"_t({texto!r})"
        return f"_t({texto!r}).format(" + ", ".join(f"({a})" for a in argumentos) + ")"

    resultado = bytearray(datos)
    cambios = 0
    for ini, fin, n in sorted(finales, key=lambda x: -x[0]):
        nuevo = convertir(n)
        if nuevo is None:
            omitidos.append((n.lineno, segmento(n)[:80]))
            continue
        resultado[ini:fin] = nuevo.encode("utf-8")
        cambios += 1

    salida = resultado.decode("utf-8")
    # Importación de _t justo después del docstring/cabecera de imports.
    marca = "import os\n"
    assert marca in salida
    salida = salida.replace(marca, "import os\nfrom traduccion import _t\n", 1)
    ast.parse(salida)   # que siga siendo Python válido
    Path(destino).write_text(salida, encoding="utf-8")
    carpeta = Path(destino).parent / "idiomas"
    carpeta.mkdir(exist_ok=True)
    (carpeta / "_catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{cambios} textos envueltos, {len(catalogo)} frases distintas, {len(omitidos)} omitidos")
    for o in omitidos:
        print("  omitido:", o)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
