// Cabecera y pie de todas las páginas de arlequinsavehub.com, escritos una sola vez aquí.
// Cada página pone <header data-cabecera></header> (y justo después este script) y
// <footer data-pie></footer>; en <body data-pagina="…"> dice cuál es, para iluminar su botón.
// Idiomas: las páginas en español en la raíz y las mismas traducidas en una carpeta por idioma (/en/, /zh-cn/…),
// con <html lang="…">. Idioma nuevo: su carpeta, una fila en IDIOMAS y sus textos en TEXTOS.
(function () {
  var DESCARGA = 'https://github.com/aitor965/Arlequin-GameHub-Releases/releases/latest/download/Arlequin-GameHub-Setup.exe'
  // [código, carpeta, abreviatura, nombre en su idioma, color del botón]
  var IDIOMAS = [
    ['es', '', 'ES', 'Español', 'linear-gradient(135deg, #ff3b3b, #ffd23f 140%)'],
    ['en', 'en/', 'EN', 'English', 'linear-gradient(135deg, #3d9bff, #1de9d0 140%)'],
    ['zh-CN', 'zh-cn/', '中文', '简体中文', 'linear-gradient(135deg, #ff3b3b, #ff9000 140%)'],
  ]
  var TEXTOS = {
    es: { inicio: 'Inicio', funciones: 'Funciones', hud: 'HUD y mirilla', comunidad: 'Comunidad', pro: 'Free y Pro', novedades: 'Novedades',
      soporte: 'Soporte', descargar: '⬇ Descargar', menu: 'Menú', paginas: 'Páginas', logoInicio: 'Arlequin GameHub: inicio',
      privacidad: 'Política de privacidad', condiciones: 'Condiciones del servicio', contacto: 'Contacto', idioma: 'Idioma' },
    en: { inicio: 'Home', funciones: 'Features', hud: 'HUD & crosshair', comunidad: 'Community', pro: 'Free & Pro', novedades: "What's new",
      soporte: 'Support', descargar: '⬇ Download', menu: 'Menu', paginas: 'Pages', logoInicio: 'Arlequin GameHub: home',
      privacidad: 'Privacy policy', condiciones: 'Terms of service', contacto: 'Contact', idioma: 'Language' },
    'zh-CN': { inicio: '首页', funciones: '功能', hud: 'HUD 和准星', comunidad: '社区', pro: 'Free 和 Pro', novedades: '更新内容',
      soporte: '支持', descargar: '⬇ 下载', menu: '菜单', paginas: '页面', logoInicio: 'Arlequin GameHub：首页',
      privacidad: '隐私政策', condiciones: '服务条款', contacto: '联系', idioma: '语言' },
  }
  var lang = document.documentElement.lang
  var este = IDIOMAS.filter(function (i) { return i[0] === lang })[0] || IDIOMAS[0]
  var raiz = este[1] ? '../' : ''
  var archivo = location.pathname.split('/').pop() || 'index.html'
  function buscar(codigo) { return IDIOMAS.filter(function (i) { return i[0] === codigo })[0] }

  // Idioma: el elegido en el selector; si no se ha elegido, el del navegador (español, chino; si no, inglés),
  // como el programa. Solo se cambia solo desde las páginas en español (un enlace a /en/ se respeta) o si se
  // eligió otro. Los buscadores no se redirigen (cada página tiene sus enlaces hreflang).
  var elegido = null
  try { elegido = localStorage.getItem('idioma') } catch (e) { /* sin almacenamiento */ }
  var robot = /bot|crawl|spider|slurp|google|bing|yandex|duckduck|baidu|facebookexternalhit|preview/i.test(navigator.userAgent)
  if (!robot) {
    var navegador = String((navigator.languages && navigator.languages[0]) || navigator.language || '').toLowerCase()
    var porNavegador = navegador.indexOf('es') === 0 ? 'es' : navegador.indexOf('zh') === 0 ? 'zh-CN' : 'en'
    var quiere = buscar(elegido) || (este[0] === 'es' ? buscar(porNavegador) : este)
    if (quiere[0] !== este[0]) { location.replace(raiz + quiere[1] + archivo + location.hash); return }
  }

  var T = TEXTOS[este[0]]
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
  // Selector de idioma: el de la página iluminado con su color y, al abrirlo, la misma página en los demás.
  var idioma = '<details class="idioma"><summary title="' + T.idioma + '" style="--c:' + este[4] + '">' + este[2] + '</summary><div>' +
    IDIOMAS.map(function (i) {
      return '<a href="' + raiz + i[1] + archivo + '" data-idioma="' + i[0] + '" hreflang="' + i[0] + '" lang="' + i[0] + '"' +
        (i === este ? ' aria-current="true"' : '') + '>' + i[3] + '</a>'
    }).join('') + '</div></details>'

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
    // Lo elegido en el selector se recuerda (y ya no se cambia solo por el idioma del navegador).
    var selector = cab.querySelector('.idioma')
    selector.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        try { localStorage.setItem('idioma', this.getAttribute('data-idioma')) } catch (e) { /* nada */ }
        this.href = this.getAttribute('href').split('#')[0] + location.hash
      })
    })
    document.addEventListener('click', function (e) { if (!selector.contains(e.target)) selector.open = false })
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
