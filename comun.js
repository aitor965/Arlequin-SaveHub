// Cabecera y pie de todas las páginas de arlequinsavehub.com, escritos una sola vez aquí.
// Cada página pone <header data-cabecera></header> (y justo después este script) y
// <footer data-pie></footer>; en <body data-pagina="…"> dice cuál es, para iluminar su botón.
(function () {
  var DESCARGA = 'https://github.com/aitor965/Arlequin-GameHub-Releases/releases/latest/download/Arlequin-GameHub-Setup.exe'
  // [id, enlace, texto, color]: cada botón se ilumina con su color al estar en su página.
  var PAGINAS = [
    ['inicio', 'index.html', 'Inicio', '#ff3b3b'],
    ['funciones', 'funciones.html', 'Funciones', '#ff9000'],
    ['savehub', 'savehub.html', 'SaveHub', '#ff4d5e'],
    ['hud', 'hud.html', 'HUD y mirilla', '#ff5fb8'],
    ['comunidad', 'comunidad.html', 'Comunidad', '#b06bff'],
    ['pro', 'pro.html', 'Free y Pro', '#2ee6a0'],
    ['novedades', 'novedades.html', 'Novedades', '#1de9d0'],
    ['soporte', 'soporte.html', 'Soporte', '#3d9bff'],
  ]
  var actual = document.body.getAttribute('data-pagina') || ''
  var logo = '<span class="a">Arlequin</span><span class="hub">GameHub</span>'

  var enlaces = PAGINAS.map(function (p) {
    var activo = p[0] === actual
    return '<a href="' + p[1] + '" style="--c:' + p[3] + '"' + (activo ? ' class="activo" aria-current="page"' : '') + '>' + p[2] + '</a>'
  }).join('')

  var cabecera = document.querySelector('[data-cabecera]')
  if (cabecera) {
    cabecera.outerHTML =
      '<header class="cabecera"><div class="contenedor">' +
        '<a href="index.html" class="logo" aria-label="Arlequin GameHub: inicio">' + logo + '</a>' +
        '<nav class="menu" aria-label="Páginas">' + enlaces + '</nav>' +
        '<button class="abrir-menu" type="button" aria-label="Menú" aria-expanded="false">☰</button>' +
        '<a class="boton neon" href="' + DESCARGA + '">⬇ Descargar</a>' +
      '</div></header>'
    var cab = document.querySelector('.cabecera')
    var boton = cab.querySelector('.abrir-menu')
    boton.addEventListener('click', function () {
      var abierta = cab.classList.toggle('abierta')
      boton.setAttribute('aria-expanded', abierta ? 'true' : 'false')
      boton.textContent = abierta ? '✕' : '☰'
    })
  }

  function pie() {
    var p = document.querySelector('[data-pie]')
    if (p) {
      p.outerHTML =
        '<div class="barra"></div>' +
        '<footer class="pie-web">' +
          '<span class="logo">' + logo + '</span>' +
          '<a href="soporte.html">Soporte</a>' +
          '<a href="privacy-policy.html">Política de privacidad</a>' +
          '<a href="terms-of-service.html">Condiciones del servicio</a>' +
          '<a href="mailto:arlequinsavehub@gmail.com">Contacto</a>' +
          '<span>© Arlequin</span>' +
        '</footer>'
    }
    // La última versión publicada (numeración tipo AMD: 26.10.beta8, 26.10.1…).
    if (document.querySelector('.version')) {
      fetch('https://api.github.com/repos/aitor965/Arlequin-GameHub-Releases/releases/latest')
        .then(function (r) { return r.ok ? r.json() : null })
        .then(function (r) {
          if (r && r.name) document.querySelectorAll('.version').forEach(function (e) { e.textContent = r.name.replace('Arlequin GameHub ', '') })
        })
        .catch(function () {})
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', pie)
  else pie()
})()
