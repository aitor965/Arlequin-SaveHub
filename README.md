# 🎮 Arlequin SaveHub

**Arlequin SaveHub (ASH)** es una herramienta para **Windows** que permite localizar, respaldar y restaurar las partidas guardadas localmente de juegos de PC.

ASH utiliza una base de datos de juegos y ubicaciones de guardado para identificar dónde se encuentran los saves, evitando depender únicamente de búsquedas genéricas de carpetas.

---

## 🚀 ¿Qué hace?

Arlequin SaveHub permite:

* 🔎 Detectar juegos instalados mediante launchers compatibles.
* 💾 Localizar sus partidas guardadas.
* 📦 Crear copias de seguridad.
* ♻️ Restaurar partidas desde un backup.
* 🗂️ Organizar los backups por ubicación de origen.
* 🕐 Mantener versiones anteriores de las copias.
* 🔐 Comprobar la integridad mediante SHA-256.
* ⚠️ Avisar si un juego parece estar ejecutándose.
* ☁️ Detectar determinados servicios de sincronización.
* 🩺 Diagnosticar problemas de detección.
* 📊 Consultar estadísticas de la base de datos.
* 🔄 Comprobar y descargar actualizaciones.

---

# 🛠️ Cómo utilizarlo

### 1. Ejecutar ASH

Inicia Arlequin SaveHub y deja que cargue la base de datos.

ASH comprueba si existe una versión actualizada de `ArlequinGameDB.yaml` y utiliza una caché local para evitar procesar innecesariamente el archivo completo.

### 2. Escanear los juegos

ASH analiza los juegos detectados en los launchers y los relaciona con la base de datos.

Cuando existe un ID de Steam o GOG, este se utiliza como referencia principal. Si no existe un identificador válido, puede utilizarse el nombre del juego como alternativa.

### 3. Crear un backup

Los saves encontrados se copian a la ubicación de backups configurada.

La estructura mantiene la agrupación de la ubicación original:

```text
Backup Saves/
└── My Games/
    └── Borderlands 2/
        ├── ...
        └── ash_backup.json
```

Si ya existe una copia, la anterior puede conservarse como historial utilizando una fecha y hora:

```text
Borderlands 2 26-09-2026 05-34-20/
```

La copia más reciente mantiene el nombre normal del juego.

### 4. Restaurar

Antes de restaurar, ASH puede mostrar información sobre:

* Juego.
* Backup seleccionado.
* Número de archivos.
* Tamaño.
* Estado de integridad.

La carpeta actual puede archivarse antes de instalar la copia seleccionada.

---

# 🔐 Integridad y seguridad

La **v1.1.3** incorpora comprobaciones adicionales para proteger las operaciones de backup y restauración.

Los backups pueden incluir:

```text
ash_backup.json
```

Esta metadata permite comprobar:

* Tamaño total.
* Número de archivos.
* Hashes SHA-256.
* Integridad de determinados archivos.

También se realizan comprobaciones relacionadas con:

* Juegos que parecen estar ejecutándose.
* Espacio disponible.
* Servicios de sincronización como OneDrive, Dropbox, Google Drive e iCloud Drive.

---

# 🗃️ ArlequinGameDB

La base de datos utilizada por ASH es:

```text
ArlequinGameDB.yaml
```

La versión analizada actualmente contiene:

| Dato                          |   Cantidad |
| ----------------------------- | ---------: |
| Juegos                        | **12.223** |
| Ubicaciones de guardado       | **14.328** |
| Juegos con acrónimos          |  **6.407** |
| Juegos con varias ubicaciones |  **1.620** |

Un juego puede tener varias ubicaciones de guardado, por lo que el número de juegos y el número de ubicaciones no coinciden.

Cada entrada puede contener:

```yaml
- name: Nombre del juego
  ids:
    steam: 123456
    gog: 1234567890
  save_locations:
    - <winDocuments>/NombreDelJuego [os=windows]
  acronyms: NombreDelJuego
```

La base de datos admite identificadores de diferentes plataformas, ubicaciones múltiples y condiciones específicas de sistema operativo o tienda.

Ejemplos:

```text
[os=windows]
[os=windows, store=steam]
[os=windows, store=microsoft]
```

Está orientada principalmente a juegos de Windows.

---

# 📁 Ubicaciones de guardado

La base de datos puede utilizar rutas como:

```text
<winDocuments>
<winAppData>
<winLocalAppData>
<winLocalAppData>Low
<winProgramData>
<base>
<root>
```

También admite patrones de archivos y diferentes ubicaciones para un mismo juego.

Esto permite cubrir tanto juegos modernos como juegos antiguos o instalaciones que utilizan estructuras de guardado poco habituales.

---

# 🆚 v1.1.2 vs v1.1.3

La versión actual es **v1.1.3** y supone una ampliación importante respecto a la **v1.1.2**.

Entre los principales cambios:

### 💾 Backups

La v1.1.3 mejora la configuración de la ubicación de backups y la gestión de copias históricas.

### 🔐 Integridad

Añade metadata, SHA-256, comprobación de tamaño y número de archivos, además de verificación antes de restaurar.

### ⚠️ Seguridad

Añade comprobaciones sobre juegos en ejecución, espacio disponible y determinados servicios de sincronización.

### 🩺 Diagnóstico

Incorpora herramientas para analizar por qué un juego puede no haberse detectado correctamente.

### 📊 Estadísticas

Permite consultar información sobre la base de datos y el último escaneo.

### 🔄 Actualizador

El sistema de actualización de la v1.1.3 es más robusto y puede conservar la versión anterior y realizar un rollback si la nueva versión no consigue iniciarse correctamente.

---

# 🔄 Actualización de la base de datos

ASH utiliza:

```text
ArlequinGameDB_parsed.json
ArlequinGameDB.etag
```

como caché.

Mediante ETag/`If-None-Match`, ASH puede comprobar si la base de datos de GitHub ha cambiado sin tener que descargarla completamente cada vez.

---

# 🛠️ Juegos no detectados

No todos los juegos pueden detectarse automáticamente.

Puede ocurrir cuando:

* El juego no está incluido en la base de datos.
* Utiliza una ubicación de guardado desconocida.
* Cambia su ubicación entre versiones.
* Utiliza un sistema de guardado poco habitual.
* No proporciona un identificador compatible.

ASH también permite trabajar con carpetas configuradas manualmente para juegos que no pueden identificarse automáticamente.

---

# 📥 Instalación

Descarga la versión disponible desde la sección **Releases** del repositorio y ejecuta:

```text
Arlequin_SaveHub.exe
```

El proyecto también puede ejecutarse desde el código fuente.

La aplicación principal está diseñada para mantenerse en **un único archivo `.py`**.

---

# 🤝 Contribuciones

Las contribuciones son bienvenidas, especialmente para ampliar `ArlequinGameDB.yaml` con:

* Nuevos juegos.
* Nuevas ubicaciones de guardado.
* IDs de Steam/GOG.
* IDs adicionales.
* Correcciones de rutas.
* Condiciones de plataforma o tienda.

---

# 📚 Créditos

La base de datos contiene información de atribución y referencias a las fuentes utilizadas para recopilar los datos, incluyendo información relacionada con **PCGamingWiki**, **Steam API** y **Ludusavi**.

Consulta los archivos de licencia y atribución del repositorio para conocer las condiciones aplicables.

---

## 🎯 Objetivo

Arlequin SaveHub nace con un objetivo sencillo:

> **Proteger tus partidas guardadas y facilitar su recuperación cuando las necesites.**

**Arlequin SaveHub (ASH)** — *Keep your saves safe.*
