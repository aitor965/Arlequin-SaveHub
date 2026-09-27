# 🃏 Arlequin SaveHub

Gestor de partidas guardadas y copias de seguridad para juegos de PC en Windows.

Arlequin SaveHub detecta juegos, localiza sus partidas guardadas y permite crear y restaurar backups.

---

## 🚀 Versión 1.1.0

La versión 1.1.0 introduce una revisión importante del sistema de detección y gestión de partidas respecto a la versión 1.0.3.

### 🗄️ Nueva base de datos: ArlequinGameDB

Nueva base de datos propia orientada a Windows y a partidas guardadas locales.

Incluye nombres, IDs de Steam/GOG, rutas de guardado, acrónimos y alias.

La base de datos se actualiza automáticamente desde GitHub.

### 🎮 Detección mejorada

Se amplía la detección de juegos procedentes de Steam, Epic Games, GOG, Battle.net, Ubisoft, EA app / Origin, Amazon Games, Xbox / Microsoft Store y juegos añadidos manualmente.

La identificación utiliza IDs cuando están disponibles y recurre al nombre, acrónimos y alias cuando es necesario.

### 🔎 Búsqueda extensa

La nueva Búsqueda Extensa permite recorrer ArlequinGameDB para localizar partidas aunque el juego no haya sido detectado directamente por un launcher.

Resulta especialmente útil para juegos portátiles, instalaciones manuales, itch.io, Game Jolt y juegos sin launcher.

### 🛡️ Mayor seguridad

Se mejoran las comprobaciones de rutas para evitar tratar carpetas generales como `Documents`, `AppData`, `Saved Games` o `Packages` como si fueran carpetas específicas de un juego.

### 🧩 Mejor resolución de rutas

Mejor tratamiento de variables, comodines y diferentes estructuras de carpetas utilizadas por los juegos.

### 💾 Mejoras en backups

Los backups conservan la estructura de la carpeta de origen y las versiones anteriores se mantienen como históricos.

Las copias se realizan mediante una ubicación temporal para reducir el riesgo de backups incompletos.

### 🕓 Históricos configurables

Ahora se puede establecer cuántas copias históricas conservar por juego o seleccionar **Sin límite**.

La configuración se mantiene entre ejecuciones.

### ♻️ Restauración mejorada

La restauración conserva los datos existentes antes de reemplazarlos y permite trabajar con copias históricas disponibles.

### ⚡ Rendimiento

Se incorpora caché de la base de datos, índices de búsqueda y comprobación mediante **ETag / If-None-Match** para evitar descargar y procesar nuevamente datos que no han cambiado.

### 🔄 Actualizaciones

La aplicación puede comprobar automáticamente nuevas versiones y utilizar las Releases de GitHub para actualizarse.

---

## 🆚 1.0.3 → 1.1.0

**1.0.3:** detección y gestión de partidas con un sistema más limitado de identificación y búsqueda.

**1.1.0:** nueva base de datos, más launchers, identificación mediante IDs y alias, búsqueda extensa, backups históricos configurables, restauración mejorada, mayor seguridad y optimización mediante caché.

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
