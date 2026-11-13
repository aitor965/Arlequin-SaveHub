# Poner en marcha "Ayuda a mejorar Arlequin" (unos 10 minutos)

## Juegos de Steam de la familia (STEAM_KEY)

GameHub pregunta a Steam qué juegos tiene la cuenta, para no mezclar los de la Familia de Steam.
1. Con la cuenta de Steam del proyecto, entra en https://steamcommunity.com/dev/apikey , pon como dominio
   `arlequinsavehub.com` y copia la clave.
2. En el Apps Script: pega el `Codigo.gs` nuevo, **Configuración del proyecto → Propiedades del script →
   Añadir propiedad**: `STEAM_KEY` = esa clave.
3. **Implementar → Gestionar implementaciones → ✏️ → Nueva versión → Implementar**. Google pedirá permiso
   para "conectarse a un servicio externo" (es para llamar a Steam).

## Actualizar a Control Hub (formato 2)

1. Abre el Apps Script, borra `Código.gs` y pega el nuevo [`Codigo.gs`](Codigo.gs). Guarda.
2. **Configuración del proyecto → Propiedades del script → Añadir propiedad**:
   `CLAVE_CONTROL` = la clave que da Arlequin Control Hub (Importar → Crear clave). Debe tener 32 o más caracteres al azar (si es más corta, las respuestas de Control Hub llevan un `aviso`). Control Hub la manda en el cuerpo de un POST; la forma antigua (`?control=` en la dirección) sigue admitida hasta que Control Hub la deje.
3. **Implementar → Gestionar implementaciones → ✏️ (editar) → Versión: Nueva versión → Implementar**.
   Así la URL `/exec` no cambia. Google pedirá permiso para usar **Drive** (es para guardar los
   envíos en `Arlequin/imports/` de tu Drive): *Configuración avanzada → Ir a…*.
4. En Control Hub: **Importar → Importar de Drive**.

Lo de abajo es la puesta en marcha original (formato 1, hojas de cálculo).

Todo es gratis y se hace con la cuenta de Google del proyecto
(arlequinsavehub@gmail.com). No hace falta ningún servidor.

## 1. Hoja de cálculo y script

1. Abre https://sheets.new con la cuenta del proyecto y llama a la hoja
   **Arlequin - Envíos**.
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

- **Actions → Datos de la comunidad → Run workflow**. Cuando haya envíos, el workflow actualiza los datos de la
  comunidad de `contribuciones/` (hardware, FPS y rutas confirmadas por 2 o más equipos).
- Los datos crudos (con los identificadores aleatorios de instalación) solo están en tu Drive; al repositorio solo
  llegan recuentos.

## Qué se guarda

Formato 2 (GameHub actual): cada envío es un archivo JSON (máximo 256 KB) en `Arlequin/imports/pendientes/` de tu
Drive; Control Hub los recoge y los pasa a `procesados/`. Formato 1 (versiones antiguas): cada fila de la hoja es una
ruta o un juego sin ruta (fecha, identificador aleatorio de la instalación, versión de GameHub, juego, tienda e ID de
tienda, plantilla de ruta con comodines `<winDocuments>/…`, nunca rutas con nombres de usuario, y su origen). El script
rechaza cualquier ruta que no empiece por un comodín.

## Límites (contra abusos)

- 10 envíos por hora por instalación, 400 por hora entre todas y 3 MB por hora entre todas (hora de reloj en UTC).
  Se cuentan con un cerrojo, para que envíos a la vez no se salten el tope.
- `steam_propios`: 10 consultas por hora por SteamID y 300 por hora entre todos.
- Lo que está en `Arlequin/imports/procesados/` no se borra solo: de vez en cuando, mira cuánto ocupa tu Drive.
