# Arlequin

Web de Arlequin GameHub (https://arlequinsavehub.com) y datos de la comunidad.

- La web, una página por sección: `index.html` (inicio), `funciones.html`, `savehub.html`, `hud.html`,
  `comunidad.html`, `pro.html`, `novedades.html` y `soporte.html`. La cabecera y el pie son los mismos en todas:
  los escribe `comun.js` (el botón de la página actual se ilumina con `<body data-pagina="…">`). Estilos en `estilo.css`.
  `gamehub.html` es la página antigua: redirige a la nueva que toque.
- `privacy-policy.html`, `terms-of-service.html`: política de privacidad y condiciones.
- `contribuciones/`: lo que comparten los usuarios con «Ayuda a mejorar Arlequin», agregado una vez al día
  (`.github/workflows/contribuciones.yml`): base de datos propia de rutas de partidas (`arlequin_bd.json`),
  clasificación de juegos (`clasificacion.json`), estadísticas de hardware (`HARDWARE.md`) y FPS (`FPS.md`).
  El receptor de los envíos (Apps Script) está en `contribuciones/servidor/`.

Las versiones de Arlequin GameHub se publican en https://github.com/aitor965/Arlequin-GameHub-Releases.
