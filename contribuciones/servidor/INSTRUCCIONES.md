# Poner en marcha "Ayuda a mejorar Arlequin" (unos 10 minutos)

## Actualizar a Control Hub (formato 2)

1. Abre el Apps Script, borra `Código.gs` y pega el nuevo [`Codigo.gs`](Codigo.gs). Guarda.
2. **Configuración del proyecto → Propiedades del script → Añadir propiedad**:
   `CLAVE_CONTROL` = la clave que da Arlequin Control Hub (Importar → Crear clave).
3. **Implementar → Gestionar implementaciones → ✏️ (editar) → Versión: Nueva versión → Implementar**.
   Así la URL `/exec` no cambia. Google pedirá permiso para usar **Drive** (es para guardar los
   envíos en `Arlequin/imports/` de tu Drive): *Configuración avanzada → Ir a…*.
4. En Control Hub: **Importar → Importar de Drive**.

Lo de abajo es la puesta en marcha original (formato 1, hojas de cálculo).

Todo es gratis y se hace con la cuenta de Google del proyecto
(arlequinsavehub@gmail.com). No hace falta ningún servidor.

## 1. Hoja de cálculo y script

1. Abre https://sheets.new con la cuenta del proyecto y llama a la hoja
   **ASH - Rutas aprendidas**.
2. Menú **Extensiones → Apps Script**.
3. Borra lo que haya en `Código.gs` y pega el contenido de
   [`Codigo.gs`](Codigo.gs). Guarda (💾).
4. **Configuración del proyecto** (rueda dentada) → **Propiedades del
   script** → **Añadir propiedad**: nombre `CLAVE`, valor una contraseña
   larga inventada (por ejemplo 40 letras y números al azar). Guárdala.

## 2. Publicarlo como aplicación web

1. Botón **Implementar → Nueva implementación**.
2. Tipo: **Aplicación web**.
   - *Ejecutar como:* **Yo**
   - *Quién tiene acceso:* **Cualquier usuario**
3. **Implementar** y autoriza los permisos (Google avisará de que la
   aplicación no está verificada: *Configuración avanzada → Ir a…*; es tu
   propio script).
4. Copia la **URL de la aplicación web** (termina en `/exec`).

## 3. Conectarlo con GitHub

1. En el repositorio: **Settings → Secrets and variables → Actions → New
   repository secret**:
   - `CONTRIB_URL` = la URL `/exec`
   - `CONTRIB_CLAVE` = la misma CLAVE del paso 1.4
2. Pon la URL en [`../servidor.json`](../servidor.json) (campo `"url"`) y
   súbelo. Desde ese momento, los GameHub con la opción activada empiezan a
   enviar (no hace falta publicar otra versión).

## 4. Comprobar

- **Actions → Cotejar rutas aprendidas → Run workflow**. Cuando haya
  envíos, aparecerá `contribuciones/INFORME.md` con:
  - rutas confirmadas por 2 o más equipos (candidatas a entrar en la BD),
  - rutas propuestas por un solo equipo,
  - juegos instalados sin ruta, ordenados por cuántos equipos los tienen.
- Los datos crudos (con los identificadores aleatorios de instalación) solo
  están en tu hoja de cálculo; al repositorio solo llegan recuentos.

## Qué se guarda

Cada fila es una ruta o un juego sin ruta: fecha, identificador aleatorio de
la instalación, versión de ASH, juego, tienda e ID de tienda, plantilla de
ruta con comodines (`<winDocuments>/…`, nunca rutas con nombres de usuario)
y su origen (`manual` o `candidata`). El script rechaza cualquier ruta que no
empiece por un comodín y limita a 6 envíos por hora por instalación.
