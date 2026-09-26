# 🃏 Arlequin SaveHub

Gestor automático de partidas guardadas y copias de seguridad para juegos de PC en Windows.

Arlequin SaveHub detecta los juegos instalados en tu sistema, identifica dónde guardan sus partidas y te permite crear y restaurar copias de seguridad de forma segura.

A diferencia de otros gestores, no busca a ciegas en carpetas genéricas (`Documents`, `AppData`, `Saved Games`...). En su lugar, utiliza una base de datos propia de identificadores y ubicaciones (`id_y_ubicacion_saves.yaml`) para determinar qué juego está instalado y dónde debería encontrarse su save.

> Detectar → Identificar → Resolver → Respaldar → Restaurar

---

## Novedades en v1.0.3

* Añadido soporte para **EA app / Origin**.
* Añadido soporte para **Amazon Games / Prime Gaming**.
* Añadido soporte para **Xbox / Microsoft Store (UWP)**.
* Nueva **Búsqueda Extensa en BD**, capaz de buscar partidas conocidas aunque el juego no haya sido detectado directamente por un launcher.
* Mejorada la resolución de rutas con variables y comodines.
* Añadidas comprobaciones para evitar utilizar carpetas demasiado generales como ubicación de partidas.
* Mejorada la detección y clasificación de juegos encontrados durante las búsquedas.
* Ampliado el diagnóstico para mostrar con mayor detalle las rutas encontradas y descartadas.
* Mejoradas las comprobaciones realizadas durante las operaciones de backup y restauración.

---

## Características

* Detección automática de juegos en **Steam, Epic Games Store, GOG, Battle.net, Ubisoft Connect, EA app / Origin, Amazon Games y Xbox / Microsoft Store**, además de instalaciones sin launcher.
* Identificación mediante IDs de plataforma, con respaldo por nombre cuando no existe un ID disponible.
* Resolución de rutas de guardado mediante plantillas (`<home>`, `<winAppData>`, `<winLocalAppData>`, `<winDocuments>`, `<storeUserId>`...) y condiciones por sistema operativo o tienda.
* **Búsqueda Extensa en BD** para localizar partidas aunque el juego no haya sido detectado previamente por un launcher.
* Soporte para juegos instalados manualmente y juegos portables mediante **Juegos sin Launcher**.
* Posibilidad de añadir directamente una ubicación mediante **Añadir Carpeta Manual**.
* Backup y restauración de la carpeta raíz correspondiente al juego.
* Backups históricos con fecha y hora.
* Selector manual de qué copia restaurar cuando existen varias disponibles.
* Verificación de backups.
* Juegos ocultos.
* Diagnóstico detallado de la detección de juegos y sus rutas.
* Comprobación de rutas para evitar trabajar accidentalmente sobre carpetas demasiado generales.
* Actualización automática de la base de datos.
* Comprobación de nuevas versiones de la aplicación.

---

## Cómo funciona

1. **Detección:** se consulta la información disponible en Windows y en las plataformas compatibles para saber qué juegos están instalados y dónde se encuentran.
2. **Identificación:** cada juego se cruza con `id_y_ubicacion_saves.yaml` mediante su ID o, cuando no existe, mediante su nombre.
3. **Resolución:** las plantillas de ruta definidas en el YAML se transforman en carpetas reales del equipo.
4. **Comprobación:** las rutas encontradas se verifican para evitar aceptar ubicaciones demasiado generales o compartidas.
5. **Backup:** se copia la carpeta raíz correspondiente al juego a la ubicación de backups, respetando la estructura original.
6. **Restauración:** se recupera la copia seleccionada utilizando carpetas temporales y comprobaciones antes de modificar los archivos existentes.

Las operaciones de backup y restauración utilizan comprobaciones adicionales para reducir el riesgo de dejar una partida a medias o trabajar sobre una ubicación incorrecta.

---

## Búsqueda Extensa en BD

La **Búsqueda Extensa en BD** permite recorrer la base de datos de Arlequin SaveHub y comprobar directamente las ubicaciones de partidas conocidas en el equipo.

A diferencia de la detección normal, no necesita que el juego haya sido identificado previamente mediante Steam, Epic, GOG, Battle.net, Ubisoft, EA, Amazon o Xbox.

Puede encontrar partidas de:

* Juegos instalados manualmente.
* Juegos portables.
* Juegos que ya no aparecen registrados en su launcher.
* Juegos procedentes de otra instalación o equipo.
* Juegos cuya partida continúa en el ordenador aunque el juego ya no esté instalado.

La búsqueda utiliza las ubicaciones conocidas de la base de datos y comprueba las carpetas reales existentes en Windows.

Cuando una ruta contiene variables o comodines, el programa intenta resolver primero la carpeta específica correspondiente al juego.

Si únicamente se encuentra una carpeta demasiado general, como `Documents`, `AppData`, `Saved Games` o `Packages`, la ruta no se utiliza como ubicación válida del juego.

> La Búsqueda Extensa depende de que la ubicación de guardado del juego esté incluida en la base de datos. Los juegos cuyo save depende exclusivamente de una carpeta de instalación que no puede determinarse pueden requerir el uso de **Juegos sin Launcher** o una ubicación manual.

---

## Base de datos de juegos

El archivo `id_y_ubicacion_saves.yaml` contiene, para cada juego, sus identificadores de plataforma y sus `save_locations` con las rutas y condiciones necesarias para localizar sus partidas.

La base de datos permite ampliar la compatibilidad de la aplicación sin tener que modificar el código principal.

Si un juego no se detecta correctamente o su ubicación de guardado es incorrecta, normalmente la solución consiste en añadir o corregir su entrada en este YAML.

Ejemplo:

```yaml
- name: 'Nombre del juego'
  ids:
    steam: 123456
    gog: 987654
  save_locations:
    - <ruta-steam> [os=windows, store=steam]
    - <ruta-gog> [os=windows, store=gog]
```

La base de datos se actualiza desde el repositorio de GitHub para incorporar nuevas ubicaciones y correcciones.

---

## Instalación

**Usuario final:** descarga el `.exe` desde los [Releases](https://github.com/loco965/Arlequin-SaveHub/releases) del proyecto.

**Desde código fuente:**

```bash
git clone https://github.com/loco965/Arlequin-SaveHub.git
cd Arlequin-SaveHub
```

Requiere **Python 3.10+** y `pyyaml`.

El ejecutable publicado en Releases no requiere instalar Python.

---

## Requisitos

* Windows.
* Permisos de escritura en las carpetas donde se encuentren las partidas.
* Permisos necesarios para acceder a determinadas ubicaciones protegidas de Windows.

---

## Diagnóstico

Si un juego no aparece o no se encuentra su partida correctamente, la herramienta **Diagnóstico de Juego** permite comprobar cómo está siendo detectado.

El diagnóstico puede mostrar:

* Si el juego ha sido detectado.
* El launcher asociado.
* La carpeta de instalación.
* Las rutas de guardado definidas en la base de datos.
* Las rutas que existen realmente en el equipo.
* Las rutas que no se han encontrado.
* Las rutas descartadas por seguridad.

Esta información resulta especialmente útil para detectar problemas de compatibilidad o preparar una corrección en la base de datos.

---

## Contribuir

La forma más útil de contribuir es ampliar `id_y_ubicacion_saves.yaml` con juegos que falten o corregir rutas de guardado existentes.

Si encuentras un problema de detección, se recomienda utilizar primero **Diagnóstico de Juego** para comprobar qué información ha encontrado la aplicación.

Las correcciones y nuevas entradas pueden enviarse mediante un **Pull Request**.

---

## Licencia

Consulta el archivo de licencia incluido en el repositorio.

---

## Créditos

Proyecto creado y desarrollado por **nox.bat (@_noxbat en X)** con ayuda de IA.
