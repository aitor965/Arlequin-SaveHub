# Arlequin SaveHub 2.0 (beta) — interfaz nueva

Versión 2.0 de ASH con una interfaz completamente nueva, oscura y con los
colores de Arlequin, hecha con **pywebview + React**. Por dentro usa el
**mismo motor que la 1.1.9**, así que escaneo, backups, restauraciones,
nube y respaldos automáticos funcionan igual, con los mismos datos y la
misma configuración.

> ⚠️ Es una **beta**. La versión estable sigue siendo la 1.1.9.

## Novedades

- Ventana principal nueva: tarjetas de resumen (partidas, protegidas, nube y
  espacio libre en el disco de los backups), tabla por tiendas con filtros,
  orden por columnas y clic derecho.
- Nube, Opciones, Detalles, Ocultos, Juegos sin launcher y Apoyar rehechos
  con el estilo nuevo. Todos los avisos del programa también.
- Cada nube con su color: Google Drive verde, OneDrive azul cielo y Dropbox
  azul intenso.
- La ventana se adapta a la pantalla donde se abre (85 % de la zona útil) y
  recuerda su tamaño y posición.
- Barra de título oscura en Windows 10 y 11.

## Cómo está hecho

| Archivo | Qué es |
|---|---|
| `motor_v119.py` | Copia **sin cambios** de `Arlequin_SaveHub_v1_1_9.py` (el motor). |
| `ash_web.py` | Arranca el motor con su ventana de Tkinter oculta, redirige sus cuadros de diálogo a la web y expone la API a JavaScript. |
| `frontend/` | Interfaz en React + Vite + Tailwind. `npm run build` la compila en `web/`. |

## Compilar

```bash
cd frontend
npm ci
npm run build
cd ..
pip install pywebview pyinstaller pyyaml google-auth google-auth-oauthlib pystray pillow
python -m PyInstaller --noconfirm --onefile --windowed --name Arlequin_SaveHub_2.0_beta --icon icono.ico --add-data "web;web" --add-data "icono.ico;." --hidden-import pystray._win32 --collect-submodules webview ash_web.py
```

GitHub Actions lo compila solo al subir una etiqueta `v2.*`
(workflow "Compilar Arlequin SaveHub 2.0") y lo publica como *pre-release*.

## Desarrollo

- `npm run dev` (en `frontend/`) abre la interfaz en el navegador con datos
  de ejemplo.
- `python ash_web.py --pruebas 47700` arranca el motor real sin ventana y
  `http://localhost:5173/?rpc=47700` lo maneja desde el navegador.
