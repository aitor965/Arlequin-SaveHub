# 🃏 Arlequin SaveHub

Gestor de partidas guardadas y copias de seguridad para juegos de PC en Windows.

Arlequin SaveHub detecta juegos, localiza sus partidas guardadas y permite crear y restaurar backups.

---

## 🚀 Versión 1.1.3

La versión 1.1.3 añade controles de seguridad para los backups, información más detallada sobre la detección, nuevas herramientas de diagnóstico y mejoras de uso de la aplicación.

### 🛡️ Integridad y seguridad de los backups

Los backups nuevos incluyen un archivo `ash_backup.json` con información de la copia, origen, tamaño, número de archivos y evidencias de detección.

Para los archivos que lo permiten se almacenan hashes **SHA-256**, y los archivos grandes utilizan una firma basada en tamaño y fecha de modificación. ASH puede comprobar posteriormente la integridad de una copia antes de restaurarla.

También se realiza una validación final de la ruta de origen antes de copiar y una comprobación del espacio libre disponible, utilizando un margen de seguridad del 10%.

### ♻️ Restauración con vista previa

Antes de restaurar una copia se muestra una vista previa con:

- juego y ruta del backup;
- número de archivos;
- tamaño de la copia;
- estado de integridad;
- información sobre la sustitución de los datos actuales.

La restauración mantiene el sistema de archivado de la carpeta existente antes de instalar la copia seleccionada.

### 🎯 Evidencia y confianza de detección

ASH muestra ahora información de **confianza** y evidencia técnica de la detección.

La evidencia puede distinguir entre:

- AppID de Steam o ID de GOG + ficha de la base de datos;
- nombre, acrónimo o alias exacto + ficha de la base de datos;
- coincidencia aproximada;
- ruta de guardado encontrada en ArlequinGameDB.

Esto permite investigar mejor por qué un juego ha sido detectado y evita presentar una detección como segura cuando la evidencia no lo es.

### 📊 Estadísticas de ArlequinGameDB

Se añade **Estadísticas BD**, donde se muestran:

- juegos únicos de la base de datos;
- referencias de plataforma;
- juegos multiplataforma;
- juegos por plataforma, ordenados por cantidad;
- tiempo empleado por el último escaneo completo.

Un juego presente en varias plataformas cuenta una vez dentro de cada plataforma correspondiente.

### 📖 Instrucciones de uso

Se incorpora una ventana independiente de **Instrucciones de uso** con información sobre escaneo, backups, restauración, copias históricas, estadísticas, diagnóstico, actualización de la base de datos y ubicación de backups.

### 📁 Elección de la ubicación de backups

En la primera ejecución, ASH permite elegir entre:

- la carpeta `Backup Saves` del Escritorio;
- otra carpeta seleccionada por el usuario.

La elección se guarda en la configuración para futuras ejecuciones.

La aplicación ya no crea automáticamente la carpeta predeterminada antes de que el usuario pueda elegir la ubicación.

### ☁️ Detección de sincronización activa

Antes de trabajar con los datos se puede detectar actividad de servicios de sincronización como **OneDrive, Dropbox y Google Drive**.

Si hay sincronización activa mientras ASH trabaja con los archivos, se muestra un aviso para evitar que el servicio modifique simultáneamente la copia o restauración.

### 🔎 Diagnóstico y escaneo

El motor conserva las optimizaciones de versiones anteriores y añade más información durante el escaneo, incluyendo el tiempo empleado y la evidencia utilizada para identificar los juegos.

Se mantienen las protecciones contra rutas compartidas y detecciones demasiado amplias.

### 🌐 Botón Donar

El botón Donar mantiene la gestión del navegador según su estado:

- navegador visible: YouTube y después GitHub;
- navegador minimizado: solo YouTube y vuelve a minimizarse;
- navegador cerrado: solo YouTube y se minimiza al abrirse.

El enlace de GitHub utilizado es el repositorio oficial de Arlequin SaveHub.

---

## 🗄️ ArlequinGameDB

La base de datos utilizada con esta versión contiene **12.223 juegos** y está orientada a Windows y a partidas guardadas locales.

La comprobación del YAML entregado para esta versión muestra:

- **12.223 entradas**;
- **0 identificadores Lutris**;
- **0 identificadores Flatpak**;
- nombres de juegos sin duplicados.

El YAML entregado coincide exactamente con `ArlequinGameDB_merged_v14.yaml`; no se han detectado cambios de contenido respecto a esa versión de la base de datos.

### 🎮 Plataformas e identificadores

La base de datos conserva los identificadores útiles para Windows, principalmente Steam y GOG, junto con rutas y acrónimos/alias.

Lutris y Flatpak no forman parte de la base orientada a Windows de ASH.

### 🧩 Rutas y acrónimos

Las rutas utilizan plantillas como `<winDocuments>`, `<winAppData>` y `<winLocalAppData>` y pueden incluir condiciones como `[os=windows]` o `[store=steam]`.

Los acrónimos y alias ayudan a identificar juegos cuando el nombre informado por un launcher o el nombre de una carpeta no coincide exactamente con el título de la ficha.

Las rutas pueden variar según versión, edición, plataforma, desarrollador o configuración del usuario.

### 🔄 Actualización de la base de datos

ASH comprueba la base de datos de GitHub y utiliza caché e **ETag / If-None-Match** para evitar descargar y procesar de nuevo un YAML que no ha cambiado.

---

## 🆚 Evolución de versiones

### 1.0.3 → 1.1.0

**1.0.3:** detección y gestión de partidas con un sistema más limitado de identificación y búsqueda.

**1.1.0:** nueva base de datos ArlequinGameDB, más launchers, identificación mediante IDs y alias, búsqueda extensa, backups históricos configurables, restauración mejorada, mayor seguridad, resolución avanzada de rutas y optimización mediante caché.

### 1.1.0 → 1.1.1

**1.1.1:** optimización del motor de escaneo, detectores de launchers ejecutados en paralelo, reutilización del contexto de Windows durante el escaneo, índices de nombres/acrónimos, mejor resolución de la carpeta raíz mediante nombre o acrónimo, identificación de Steam mediante AppID y protección adicional contra falsos positivos y backups accidentales de carpetas completas de instalación.

### 1.1.1 → 1.1.2

**1.1.2:** corrección de un error del escaneo relacionado con una variable de entorno no definida en determinadas rutas de ejecución. Se mantuvieron las mejoras de rendimiento, detección mediante AppID de Steam, protección contra falsos positivos y detección de la carpeta raíz mediante nombre/acrónimo.

### 1.1.2 → 1.1.3

**1.1.3:** controles de integridad de backups mediante `ash_backup.json` y SHA-256, validación de rutas de origen y espacio libre antes de copiar, vista previa e integridad antes de restaurar, evidencia y nivel de confianza de detección, nuevas Estadísticas BD con tiempo del último escaneo, ventana de Instrucciones de uso, elección de la ubicación de backups en la primera ejecución, aviso ante sincronización activa de servicios como OneDrive, Dropbox y Google Drive, y mejoras de diagnóstico y gestión del botón Donar.

---

## 📥 Descargar

La última versión compilada para Windows está disponible en **[Releases](https://github.com/loco965/Arlequin-SaveHub/releases)**.

Descarga `Arlequin_SaveHub.exe` y ejecútalo.

---

## 🗃️ Base de datos

**ArlequinGameDB** está orientada a juegos de Windows con partidas guardadas locales.

La información puede ampliarse o corregirse independientemente del ejecutable.

---

## 🤝 Contribuir

Puedes contribuir añadiendo juegos, corrigiendo rutas, incorporando IDs, mejorando acrónimos y alias o informando de errores.

---

## 📜 Créditos

Arlequin SaveHub utiliza información adaptada y ampliada a partir de fuentes como **PCGamingWiki**, **Ludusavi** y **Ludusavi Manifest**.

La base de datos de Arlequin SaveHub es una adaptación independiente orientada a Windows.

Consulta `LICENSE` para la información de licencia.

---

## 🃏 Arlequin SaveHub

**Desarrollado por loco965**

[GitHub](https://github.com/loco965/Arlequin-SaveHub)
