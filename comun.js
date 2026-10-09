// Cabecera y pie de todas las páginas de arlequinsavehub.com, escritos una sola vez aquí.
// Cada página pone <header data-cabecera></header> (y justo después este script) y
// <footer data-pie></footer>; en <body data-pagina="…"> dice cuál es, para iluminar su botón.
// Dos idiomas: las páginas en español en la raíz y las mismas en inglés en /en/ (con <html lang="en">).
(function () {
  var DESCARGA = 'https://github.com/aitor965/Arlequin-GameHub-Releases/releases/latest/download/Arlequin-GameHub-Setup.exe'
  var EN = document.documentElement.lang === 'en'
  var archivo = location.pathname.split('/').pop() || 'index.html'

  // Idioma: el elegido con el botón ES / EN; si no se ha elegido, el del navegador (si no es español,
  // inglés), como el programa. Los buscadores no se redirigen (cada página tiene su enlace hreflang).
  var elegido = null
  try { elegido = localStorage.getItem('idioma') } catch (e) { /* sin almacenamiento */ }
  var robot = /bot|crawl|spider|slurp|google|bing|yandex|duckduck|baidu|facebookexternalhit|preview/i.test(navigator.userAgent)
  if (!robot) {
    var navegador = String((navigator.languages && navigator.languages[0]) || navigator.language || '').toLowerCase()
    var quiere = elegido || (navegador.indexOf('es') === 0 ? 'es' : 'en')
    if (!EN && quiere === 'en') { location.replace('en/' + archivo + location.hash); return }
    if (EN && elegido === 'es') { location.replace('../' + archivo + location.hash); return }
  }

  var T = EN
    ? { inicio: 'Home', funciones: 'Features', hud: 'HUD & crosshair', comunidad: 'Community', pro: 'Free & Pro', novedades: "What's new",
        soporte: 'Support', descargar: '⬇ Download', menu: 'Menu', paginas: 'Pages', logoInicio: 'Arlequin GameHub: home',
        privacidad: 'Privacy policy', condiciones: 'Terms of service', contacto: 'Contact', idioma: 'Idioma: español' }
    : { inicio: 'Inicio', funciones: 'Funciones', hud: 'HUD y mirilla', comunidad: 'Comunidad', pro: 'Free y Pro', novedades: 'Novedades',
        soporte: 'Soporte', descargar: '⬇ Descargar', menu: 'Menú', paginas: 'Páginas', logoInicio: 'Arlequin GameHub: inicio',
        privacidad: 'Política de privacidad', condiciones: 'Condiciones del servicio', contacto: 'Contacto', idioma: 'Language: English' }
  // [id, enlace, texto, color]: cada botón se ilumina con su color al estar en su página.
  var PAGINAS = [
    ['inicio', 'index.html', T.inicio, '#ff3b3b'],
    ['funciones', 'funciones.html', T.funciones, '#ff9000'],
    ['savehub', 'savehub.html', 'SaveHub', '#ff4d5e'],
    ['hud', 'hud.html', T.hud, '#ff5fb8'],
    ['comunidad', 'comunidad.html', T.comunidad, '#b06bff'],
    ['pro', 'pro.html', T.pro, '#2ee6a0'],
    ['novedades', 'novedades.html', T.novedades, '#1de9d0'],
    ['soporte', 'soporte.html', T.soporte, '#3d9bff'],
  ]
  var actual = document.body.getAttribute('data-pagina') || ''
  var logo = '<span class="a">Arlequin</span><span class="hub">GameHub</span>'

  var enlaces = PAGINAS.map(function (p) {
    var activo = p[0] === actual
    return '<a href="' + p[1] + '" style="--c:' + p[3] + '"' + (activo ? ' class="activo" aria-current="page"' : '') + '>' + p[2] + '</a>'
  }).join('')
  // La misma página en el otro idioma.
  var otro = (EN ? '../' : 'en/') + archivo
  var idioma = '<a class="idioma" href="' + otro + '" data-idioma="' + (EN ? 'es' : 'en') + '" hreflang="' + (EN ? 'es' : 'en') + '" title="' + T.idioma + '">' +
    '<span' + (EN ? '' : ' class="este"') + '>ES</span><span' + (EN ? ' class="este"' : '') + '>EN</span></a>'

  var cabecera = document.querySelector('[data-cabecera]')
  if (cabecera) {
    cabecera.outerHTML =
      '<header class="cabecera"><div class="contenedor">' +
        '<a href="index.html" class="logo" aria-label="' + T.logoInicio + '">' + logo + '</a>' +
        '<nav class="menu" aria-label="' + T.paginas + '">' + enlaces + '</nav>' +
        '<button class="abrir-menu" type="button" aria-label="' + T.menu + '" aria-expanded="false">☰</button>' +
        idioma +
        '<a class="boton neon" href="' + DESCARGA + '">' + T.descargar + '</a>' +
      '</div></header>'
    var cab = document.querySelector('.cabecera')
    var boton = cab.querySelector('.abrir-menu')
    boton.addEventListener('click', function () {
      var abierta = cab.classList.toggle('abierta')
      boton.setAttribute('aria-expanded', abierta ? 'true' : 'false')
      boton.textContent = abierta ? '✕' : '☰'
    })
    // Lo elegido con el botón se recuerda (y ya no se cambia solo por el idioma del navegador).
    cab.querySelector('.idioma').addEventListener('click', function () {
      try { localStorage.setItem('idioma', this.getAttribute('data-idioma')) } catch (e) { /* nada */ }
      this.href = otro + location.hash
    })
  }

  function pie() {
    var p = document.querySelector('[data-pie]')
    if (p) {
      p.outerHTML =
        '<div class="barra"></div>' +
        '<footer class="pie-web">' +
          '<span class="logo">' + logo + '</span>' +
          '<a href="soporte.html">' + T.soporte + '</a>' +
          '<a href="privacy-policy.html">' + T.privacidad + '</a>' +
          '<a href="terms-of-service.html">' + T.condiciones + '</a>' +
          '<a href="mailto:arlequinsavehub@gmail.com">' + T.contacto + '</a>' +
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
