# Licencia de ArlequinGameDB (`ArlequinGameDB.yaml`)

ArlequinGameDB es la base de datos de ubicaciones de guardado que usa
Arlequin SaveHub. Es una obra derivada que combina datos de varias fuentes,
adaptados, corregidos y ampliados por aitor965
(arlequinsavehub@gmail.com).

## Licencia de la base de datos

Como incluye datos procedentes de PCGamingWiki, publicados bajo
**Creative Commons Reconocimiento-NoComercial-CompartirIgual 3.0**
(CC BY-NC-SA 3.0), ArlequinGameDB se distribuye bajo la **misma licencia**:

**CC BY-NC-SA 3.0** — https://creativecommons.org/licenses/by-nc-sa/3.0/deed.es

Esto significa que puedes copiarla, redistribuirla y adaptarla siempre que:

- **Reconocimiento:** cites ArlequinGameDB / Arlequin SaveHub y las fuentes
  originales indicadas abajo, e indiques si has hecho cambios.
- **NoComercial:** no la uses con fines comerciales.
- **CompartirIgual:** si la modificas, distribuyas tu versión con esta misma
  licencia.

Esta licencia se refiere solo a la base de datos. El código del programa
Arlequin SaveHub tiene su propia licencia (ver `LICENSE`).

## Fuentes y atribuciones

### PCGamingWiki
Rutas de guardado, rutas de configuración y claves de registro.
https://www.pcgamingwiki.com — contenido bajo CC BY-NC-SA 3.0.

### Ludusavi Manifest
ArlequinGameDB se ha construido a partir de Ludusavi Manifest
(https://github.com/mtkennerly/ludusavi-manifest), que se distribuye bajo la
licencia MIT. Según exige esa licencia, se reproduce su aviso completo:

```
MIT License

Copyright (c) 2020 Matthew T. Kennerly (mtkennerly)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Steam
Identificadores de Steam (AppID) y nombres de carpetas de instalación,
obtenidos a través de la API pública de Steam.

## Cambios realizados respecto a las fuentes

- Solo se conservan las rutas de Windows (se han eliminado Linux, macOS,
  Lutris y Flatpak).
- Rutas corregidas (LocalLow mal ubicado, `AppData/Local/Local`, SteamID
  escritos a mano) y comprobaciones propias.
- Juegos, identificadores, tiendas, acrónimos y claves de registro añadidos o
  revisados para Arlequin SaveHub.
- Formato propio (lista de fichas con `save_locations`, `registry`,
  `acronyms`, etc.).
