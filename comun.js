// Cabecera y pie de todas las páginas de arlequinsavehub.com, escritos una sola vez aquí.
// Cada página pone <header data-cabecera></header> (y justo después este script) y
// <footer data-pie></footer>; en <body data-pagina="…"> dice cuál es, para iluminar su botón.
// Idiomas: las páginas en español en la raíz y las mismas traducidas en una carpeta por idioma (/en/, /zh-cn/…),
// con <html lang="…">. Idioma nuevo: su carpeta, una fila en IDIOMAS y sus textos en TEXTOS.
(function () {
  var DISCORD = 'https://discord.gg/nvu32qXGgg'
  var DESCARGA = 'https://arlequinsavehub.com/descargas/Arlequin-GameHub-Setup.exe'
  // La versión de la Microsoft Store y el día que salió esa versión (no el día que llegó a la Store): cambiarla con cada
  // estable que se suba a la Store.
  var TIENDA_MS = ['26.11.2', '2026-11-09']
  // La última versión de descarga directa (versión, día, bytes del instalador de descargas/): cambiarla al publicar.
  var DIRECTA = ['26.11.2.beta7', '2026-11-14', 12682990]
  // La preview de Linux del botón «Linux (preview)» (versión, día, bytes de la AppImage de descargas/linux/, a trozos):
  // la cambia publicar_linux_web.py de GameHub. null = aún no hay AppImage en la web: el botón no sale.
  var LINUX = ['26.11.0.preview2', '2026-11-03', 122939896]
  // [código, carpeta, abreviatura, nombre en su idioma, color del botón]
  var IDIOMAS = [
    ['es', '', 'ES', 'Español', 'linear-gradient(135deg, #ff3b3b, #ffd23f 140%)'],
    ['en', 'en/', 'EN', 'English', 'linear-gradient(135deg, #3d9bff, #1de9d0 140%)'],
    ['zh-CN', 'zh-cn/', '中文', '简体中文', 'linear-gradient(135deg, #ff3b3b, #ff9000 140%)'],
    ['ru', 'ru/', 'RU', 'Русский', 'linear-gradient(135deg, #3d9bff, #ff4d5e 140%)'],
    ['pt-BR', 'pt-br/', 'PT', 'Português (Brasil)', 'linear-gradient(135deg, #2ee6a0, #ffd23f 140%)'],
    ['de', 'de/', 'DE', 'Deutsch', 'linear-gradient(135deg, #ffd23f, #ff3b3b 140%)'],
    ['fr', 'fr/', 'FR', 'Français', 'linear-gradient(135deg, #3d9bff, #ff5fb8 140%)'],
    ['it', 'it/', 'IT', 'Italiano', 'linear-gradient(135deg, #2ee6a0, #ff3b3b 140%)'],
    ['ja', 'ja/', '日本語', '日本語', 'linear-gradient(135deg, #ff3b3b, #ff5fb8 140%)'],
    ['pl', 'pl/', 'PL', 'Polski', 'linear-gradient(135deg, #ff4d5e, #ffd23f 140%)'],
  ]
  // Bandera de cada idioma, dibujada aquí (en Windows los emojis de banderas salen como letras).
  var BANDERAS = {
    'es': "<rect width='30' height='20' fill='#c60b1e'/><rect y='5' width='30' height='10' fill='#ffc400'/>",
    'en': "<rect width='30' height='20' fill='#012169'/><path d='M0,0 30,20M30,0 0,20' stroke='#fff' stroke-width='4'/><path d='M0,0 30,20M30,0 0,20' stroke='#c8102e' stroke-width='1.5'/><path d='M15,0V20M0,10H30' stroke='#fff' stroke-width='6'/><path d='M15,0V20M0,10H30' stroke='#c8102e' stroke-width='3.4'/>",
    'zh-CN': "<rect width='30' height='20' fill='#ee1c25'/><polygon points='5.0,2.0 5.7,4.1 7.9,4.1 6.1,5.4 6.8,7.4 5.0,6.1 3.2,7.4 3.9,5.4 2.1,4.1 4.3,4.1' fill='#ffff00'/><polygon points='9.1,2.5 9.6,2.0 9.2,1.3 9.9,1.6 10.4,1.1 10.3,1.8 11.0,2.1 10.3,2.3 10.2,3.0 9.9,2.4' fill='#ffff00'/><polygon points='11.0,4.1 11.7,3.8 11.6,3.1 12.1,3.6 12.7,3.3 12.4,3.9 12.9,4.5 12.2,4.3 11.8,5.0 11.7,4.3' fill='#ffff00'/><polygon points='11.0,6.7 11.8,6.7 12.0,6.0 12.2,6.7 12.9,6.7 12.4,7.1 12.6,7.8 12.0,7.4 11.4,7.8 11.6,7.1' fill='#ffff00'/><polygon points='9.2,8.4 9.9,8.6 10.4,8.1 10.3,8.8 11.0,9.0 10.3,9.2 10.3,10.0 9.9,9.4 9.2,9.5 9.6,9.0' fill='#ffff00'/>",
    'ru': "<rect y='0' width='30' height='6.7' fill='#fff'/><rect y='6.7' width='30' height='6.7' fill='#0039a6'/><rect y='13.3' width='30' height='6.7' fill='#d52b1e'/>",
    'pt-BR': "<rect width='30' height='20' fill='#009c3b'/><polygon points='15,2.5 27.5,10 15,17.5 2.5,10' fill='#ffdf00'/><circle cx='15' cy='10' r='4.3' fill='#002776'/>",
    'de': "<rect y='0' width='30' height='6.7' fill='#000'/><rect y='6.7' width='30' height='6.7' fill='#dd0000'/><rect y='13.3' width='30' height='6.7' fill='#ffce00'/>",
    'fr': "<rect x='0' width='10' height='20' fill='#0055a4'/><rect x='10' width='10' height='20' fill='#fff'/><rect x='20' width='10' height='20' fill='#ef4135'/>",
    'it': "<rect x='0' width='10' height='20' fill='#009246'/><rect x='10' width='10' height='20' fill='#fff'/><rect x='20' width='10' height='20' fill='#ce2b37'/>",
    'ja': "<rect width='30' height='20' fill='#fff'/><circle cx='15' cy='10' r='6' fill='#bc002d'/>",
    'pl': "<rect width='30' height='10' fill='#fff'/><rect y='10' width='30' height='10' fill='#dc143c'/>",
  }
  function bandera(codigo) {
    return '<svg class="bandera" viewBox="0 0 30 20" aria-hidden="true">' + BANDERAS[codigo] + '</svg>'
  }
  var TEXTOS = {
    es: { soloDirecta: "Solo en la descarga directa", general: 'General', hubs: 'Hubs', estadisticas: 'Estadísticas', inicio: 'Inicio', funciones: 'Funciones', hud: 'HUD y mirilla', comunidad: 'Comunidad', pro: 'Free y Pro', novedades: 'Novedades',
      soporte: 'Soporte', descargar: '⬇ Descargar', menu: 'Menú', paginas: 'Páginas', logoInicio: 'Arlequin GameHub: inicio',
      privacidad: 'Política de privacidad', condiciones: 'Condiciones del servicio', contacto: 'Contacto', idioma: 'Idioma', version: 'Versión' },
    en: { soloDirecta: "Direct download only", general: 'General', hubs: 'Hubs', estadisticas: 'Statistics', inicio: 'Home', funciones: 'Features', hud: 'HUD & crosshair', comunidad: 'Community', pro: 'Free & Pro', novedades: "What's new",
      soporte: 'Support', descargar: '⬇ Download', menu: 'Menu', paginas: 'Pages', logoInicio: 'Arlequin GameHub: home',
      privacidad: 'Privacy policy', condiciones: 'Terms of service', contacto: 'Contact', idioma: 'Language', version: 'Version' },
    'zh-CN': { soloDirecta: "仅限直接下载版", general: '通用', hubs: 'Hubs', estadisticas: '统计', inicio: '首页', funciones: '功能', hud: 'HUD 和准星', comunidad: '社区', pro: 'Free 和 Pro', novedades: '更新内容',
      soporte: '支持', descargar: '⬇ 下载', menu: '菜单', paginas: '页面', logoInicio: 'Arlequin GameHub：首页',
      privacidad: '隐私政策', condiciones: '服务条款', contacto: '联系', idioma: '语言', version: '版本' },
    ru: { soloDirecta: "Только при прямой загрузке", general: 'Общее', hubs: 'Hubs', estadisticas: 'Статистика', inicio: 'Главная', funciones: 'Функции', hud: 'HUD и прицел', comunidad: 'Сообщество', pro: 'Free и Pro', novedades: 'Новости',
      soporte: 'Поддержка', descargar: '⬇ Скачать', menu: 'Меню', paginas: 'Страницы', logoInicio: 'Arlequin GameHub: главная',
      privacidad: 'Политика конфиденциальности', condiciones: 'Условия использования', contacto: 'Контакты', idioma: 'Язык', version: 'Версия' },
    'pt-BR': { soloDirecta: "Só no download direto", general: 'Geral', hubs: 'Hubs', estadisticas: 'Estatísticas', inicio: 'Início', funciones: 'Recursos', hud: 'HUD e mira', comunidad: 'Comunidade', pro: 'Free e Pro', novedades: 'Novidades',
      soporte: 'Suporte', descargar: '⬇ Baixar', menu: 'Menu', paginas: 'Páginas', logoInicio: 'Arlequin GameHub: início',
      privacidad: 'Política de privacidade', condiciones: 'Termos de serviço', contacto: 'Contato', idioma: 'Idioma', version: 'Versão' },
    de: { soloDirecta: "Nur im Direktdownload", general: 'Allgemein', hubs: 'Hubs', estadisticas: 'Statistiken', inicio: 'Start', funciones: 'Funktionen', hud: 'HUD und Fadenkreuz', comunidad: 'Community', pro: 'Free und Pro', novedades: 'Neuigkeiten',
      soporte: 'Support', descargar: '⬇ Herunterladen', menu: 'Menü', paginas: 'Seiten', logoInicio: 'Arlequin GameHub: Start',
      privacidad: 'Datenschutzerklärung', condiciones: 'Nutzungsbedingungen', contacto: 'Kontakt', idioma: 'Sprache', version: 'Version' },
    fr: { soloDirecta: "Téléchargement direct uniquement", general: 'Général', hubs: 'Hubs', estadisticas: 'Statistiques', inicio: 'Accueil', funciones: 'Fonctionnalités', hud: 'HUD et réticule', comunidad: 'Communauté', pro: 'Free et Pro', novedades: 'Nouveautés',
      soporte: 'Assistance', descargar: '⬇ Télécharger', menu: 'Menu', paginas: 'Pages', logoInicio: 'Arlequin GameHub : accueil',
      privacidad: 'Politique de confidentialité', condiciones: 'Conditions d’utilisation', contacto: 'Contact', idioma: 'Langue', version: 'Version' },
    it: { soloDirecta: "Solo con il download diretto", general: 'Generale', hubs: 'Hubs', estadisticas: 'Statistiche', inicio: 'Home', funciones: 'Funzioni', hud: 'HUD e mirino', comunidad: 'Community', pro: 'Free e Pro', novedades: 'Novità',
      soporte: 'Supporto', descargar: '⬇ Scarica', menu: 'Menu', paginas: 'Pagine', logoInicio: 'Arlequin GameHub: home',
      privacidad: 'Informativa sulla privacy', condiciones: 'Termini di servizio', contacto: 'Contatti', idioma: 'Lingua', version: 'Versione' },
    ja: { soloDirecta: "直接ダウンロード版のみ", general: '一般', hubs: 'Hubs', estadisticas: '統計', inicio: 'ホーム', funciones: '機能', hud: 'HUDとクロスヘア', comunidad: 'コミュニティ', pro: 'Free と Pro', novedades: '新着情報',
      soporte: 'サポート', descargar: '⬇ ダウンロード', menu: 'メニュー', paginas: 'ページ', logoInicio: 'Arlequin GameHub：ホーム',
      privacidad: 'プライバシーポリシー', condiciones: '利用規約', contacto: 'お問い合わせ', idioma: '言語', version: 'バージョン' },
    pl: { soloDirecta: "Tylko w pobieraniu bezpośrednim", general: 'Ogólne', hubs: 'Hubs', estadisticas: 'Statystyki', inicio: 'Strona główna', funciones: 'Funkcje', hud: 'HUD i celownik', comunidad: 'Społeczność', pro: 'Free i Pro', novedades: 'Nowości',
      soporte: 'Pomoc', descargar: '⬇ Pobierz', menu: 'Menu', paginas: 'Strony', logoInicio: 'Arlequin GameHub: strona główna',
      privacidad: 'Polityka prywatności', condiciones: 'Warunki korzystania', contacto: 'Kontakt', idioma: 'Język', version: 'Wersja' },
  }
  // Menú «Funciones»: [página, icono, color, beta (true), «directa» (solo en la descarga directa) o etiqueta] y, por idioma, «todas» y el nombre de cada una (null = el de HUD).
  var FUNCIONES = [
    ["biblioteca.html", "🎮", "var(--naranja)", false],
    ["savehub.html", "💾", "var(--rojo)", false],
    ["loothub.html", "💎", "var(--verde)"],
    ["shophub.html", "🛒", "var(--amarillo)", false],
    ["socialhub.html", "📡", "var(--azul)", false],
    ["fixhub.html", "🛠️", "var(--amarillo)", "directa"],
    ["emuhub.html", "🕹️", "var(--rosa)", "directa"],
    ["replayhub.html", "🎬", "var(--rosa)"],
    ["benchhub.html", "🏁", "var(--naranja)", false],
    ["aimhub.html", "🎯", "var(--morado)"],
    ["diskhub.html", "💽", "var(--azul)"],
    ["protonhub.html", "⚛️", "var(--rosa)", "Linux"],
    ["play-hub.html", "📺", "var(--naranja)", false],
    ["tvhub.html", "📽️", "var(--turquesa)", false],
    ["remotehub.html", "📱", "var(--verde)", false],
    ["ficha-del-juego.html", "🚦", "var(--verde)", false],
    ["ajustes-graficos.html", "🎛️", "var(--turquesa)", false],
    ["fps.html", "📈", "var(--turquesa)", false],
    ["tu-pc.html", "🖥️", "var(--azul)", false],
    ["hud.html", "📟", "var(--rosa)", false],
    ["chat.html", "💬", "var(--rosa)", false],
    ["caja-de-la-suerte.html", "🎁", "var(--amarillo)", false],
    ["potato-mode.html", "🥔", "var(--amarillo)", false],
    ["a-tu-gusto.html", "🎨", "var(--morado)", false],
  ]
  var NOMBRES_FUNCIONES = {
    "es": ["Todas las funciones", "Biblioteca", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "La ficha de cada juego", "Ajustes gráficos", "Tus FPS", "Tu PC", null, "Chat", "Caja de la suerte", "POTATO MODE", "A tu gusto"],
    "en": ["All features", "Library", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "Each game's page", "Graphics settings", "Your FPS", "Your PC", null, "Chat", "Lucky box", "POTATO MODE", "Your way"],
    "zh-CN": ["全部功能", "游戏库", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "游戏详情页", "画面设置", "你的 FPS", "你的电脑", null, "聊天", "幸运宝箱", "POTATO MODE", "随心定制"],
    "ru": ["Все функции", "Библиотека", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "Страница каждой игры", "Настройки графики", "Ваш FPS", "Ваш ПК", null, "Чат", "Коробка удачи", "POTATO MODE", "Под себя"],
    "pt-BR": ["Todos os recursos", "Biblioteca", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "A página de cada jogo", "Configurações gráficas", "Seu FPS", "Seu PC", null, "Chat", "Caixa da sorte", "POTATO MODE", "Do seu jeito"],
    "de": ["Alle Funktionen", "Bibliothek", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "Die Seite jedes Spiels", "Grafikeinstellungen", "Deine FPS", "Dein PC", null, "Chat", "Glückskiste", "POTATO MODE", "Nach deinem Geschmack"],
    "fr": ["Toutes les fonctionnalités", "Bibliothèque", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "La fiche de chaque jeu", "Réglages graphiques", "Tes FPS", "Ton PC", null, "Chat", "Boîte chanceuse", "POTATO MODE", "À ton goût"],
    "it": ["Tutte le funzioni", "Libreria", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "La scheda di ogni gioco", "Impostazioni grafiche", "I tuoi FPS", "Il tuo PC", null, "Chat", "Scatola della fortuna", "POTATO MODE", "A modo tuo"],
    "ja": ["すべての機能", "ライブラリ", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "各ゲームの詳細ページ", "グラフィック設定", "あなたのFPS", "あなたのPC", null, "チャット", "ラッキーボックス", "POTATO MODE", "自分好みに"],
    "pl": ["Wszystkie funkcje", "Biblioteka", "SaveHub", "LootHub", "ShopHub", "SocialHub", "FixHub", "EmuHub", "ReplayHub", "BenchHub", "AimHub", "DiskHub", "ProtonHub", "Play Hub", "TVHub", "RemoteHub", "Strona każdej gry", "Ustawienia graficzne", "Twoje FPS", "Twój PC", null, "Czat", "Skrzynia szczęścia", "POTATO MODE", "Po swojemu"],
  }
  var lang = document.documentElement.lang
  var este = IDIOMAS.filter(function (i) { return i[0] === lang })[0] || IDIOMAS[0]
  var raiz = este[1] ? '../' : ''
  var archivo = location.pathname.split('/').pop() || 'index.html'
  function buscar(codigo) { return IDIOMAS.filter(function (i) { return i[0] === codigo })[0] }

  // Idioma: el elegido en el selector; si no se ha elegido, el del navegador (los de la web; si no, inglés),
  // como el programa. Solo se cambia solo desde las páginas en español (un enlace a /en/ se respeta) o si se
  // eligió otro. Los buscadores no se redirigen (cada página tiene sus enlaces hreflang).
  var elegido = null
  try { elegido = localStorage.getItem('idioma') } catch (e) { /* sin almacenamiento */ }
  var robot = /bot|crawl|spider|slurp|google|bing|yandex|duckduck|baidu|facebookexternalhit|preview/i.test(navigator.userAgent)
  if (!robot) {
    var navegador = String((navigator.languages && navigator.languages[0]) || navigator.language || '').toLowerCase()
    // Los de la web por su prefijo (pt = Brasil); si no, inglés.
    var prefijos = { es: 'es', zh: 'zh-CN', ru: 'ru', pt: 'pt-BR', de: 'de', fr: 'fr', it: 'it', ja: 'ja', pl: 'pl' }
    var porNavegador = prefijos[navegador.slice(0, 2)] || 'en'
    var quiere = buscar(elegido) || (este[0] === 'es' ? buscar(porNavegador) : este)
    if (quiere[0] !== este[0]) { location.replace(raiz + quiere[1] + archivo + location.hash); return }
  }

  var T = TEXTOS[este[0]]
  // [id, enlace, texto, color]: cada botón se ilumina con su color al estar en su página.
  var PAGINAS = [
    ['inicio', 'index.html', T.inicio, '#ff3b3b'],
    ['funciones', 'funciones.html', T.funciones, '#ff9000'],
    ['comunidad', 'comunidad.html', T.comunidad, '#b06bff'],
    ['halloffame', 'halloffame.html', 'Hall of Fame', '#ffd23f'],
    ['estadisticas', 'estadisticas.html', T.estadisticas, '#ff5fb8'],
    ['pro', 'pro.html', T.pro, '#2ee6a0'],
    ['novedades', 'novedades.html', T.novedades, '#1de9d0'],
    ['soporte', 'soporte.html', T.soporte, '#3d9bff'],
  ]
  var actual = document.body.getAttribute('data-pagina') || ''
  var logo = '<span class="a">Arlequin</span><span class="hub">GameHub</span>'

  // «Funciones» se abre en la lista de todas (iluminado también en sus páginas y en las de SaveHub y HUD).
  var nombresF = NOMBRES_FUNCIONES[este[0]]
  function desplegable(p) {
    var activo = actual === 'funciones' || actual === 'hud' || actual === 'savehub'
    return '<details class="desplegable"><summary style="--c:' + p[3] + '"' + (activo ? ' class="activo"' : '') + '>' + p[2] + '</summary><div>' +
      '<a class="todas" href="funciones.html"' + (archivo === 'funciones.html' ? ' aria-current="page"' : '') + '>' + nombresF[0] + '</a>' +
      grupo(false, T.general) + grupo(true, T.hubs) + '</div></details>'
  }
  // Dos grupos con su título: lo general y los «…Hub» (Play Hub va en lo general).
  function grupo(hubs, titulo) {
    return '<div class="grupo"><h3>' + titulo + '</h3>' +
      FUNCIONES.map(function (f, i) {
        if (/hub\.html$/.test(f[0]) && f[0] !== 'play-hub.html' ? !hubs : hubs) return ''
        return '<a href="' + f[0] + '" style="--c:' + f[2] + '"' + (archivo === f[0] ? ' aria-current="page"' : '') + '><span>' + f[1] + '</span>' +
          (nombresF[i + 1] || T.hud) + (f[3] ? ' <small>' + (f[3] === true ? 'beta' : f[3] === 'directa' ? T.soloDirecta : f[3]) + '</small>' : '') + '</a>'
      }).join('') + '</div>'
  }
  var enlaces = PAGINAS.map(function (p) {
    if (p[0] === 'funciones') return desplegable(p)
    var activo = p[0] === actual
    return '<a href="' + p[1] + '" style="--c:' + p[3] + '"' + (activo ? ' class="activo" aria-current="page"' : '') + '>' + p[2] + '</a>'
  }).join('')
  // Selector de idioma: el de la página iluminado con su color y, al abrirlo, la misma página en los demás.
  var idioma = '<details class="idioma"><summary title="' + T.idioma + '" style="--c:' + este[4] + '">' + bandera(este[0]) + este[2] + '</summary><div>' +
    IDIOMAS.map(function (i) {
      return '<a href="' + raiz + i[1] + archivo + '" data-idioma="' + i[0] + '" hreflang="' + i[0] + '" lang="' + i[0] + '"' +
        (i === este ? ' aria-current="true"' : '') + '>' + bandera(i[0]) + i[3] + '</a>'
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
    var funciones = cab.querySelector('.desplegable')
    document.addEventListener('click', function (e) { if (!funciones.contains(e.target)) funciones.open = false })
    // Que el panel no se salga de la ventana: si se pasa por la derecha, se mueve a la izquierda.
    var panel = funciones.querySelector('div')
    function encajar() {
      panel.style.marginLeft = ''
      if (!funciones.open || getComputedStyle(panel).position !== 'absolute') return
      var sobra = panel.getBoundingClientRect().right - (document.documentElement.clientWidth - 16)
      if (sobra > 0) panel.style.marginLeft = -sobra + 'px'
    }
    funciones.addEventListener('toggle', encajar)
    window.addEventListener('resize', encajar)
    // En el móvil, «atrás» cierra el menú ☰ o un desplegable en vez de irse a la página anterior: al abrir uno se
    // apunta un paso en el historial y al cerrarlo se quita. Un enlace pulsado con el menú abierto quita ese paso antes.
    var irA = null
    function abiertoAlgo() { return cab.classList.contains('abierta') || funciones.open || selector.open }
    function cerrarTodo() {
      cab.classList.remove('abierta'); boton.setAttribute('aria-expanded', 'false'); boton.textContent = '☰'
      funciones.open = false; selector.open = false
    }
    function sincronizarAtras() {
      setTimeout(function () {
        var marcado = history.state && history.state.menuWeb
        if (abiertoAlgo() && !marcado) history.pushState({ menuWeb: 1 }, '')
        else if (!abiertoAlgo() && marcado) history.back()
      }, 0)
    }
    boton.addEventListener('click', sincronizarAtras)
    funciones.addEventListener('toggle', sincronizarAtras)
    selector.addEventListener('toggle', sincronizarAtras)
    window.addEventListener('popstate', function () {
      if (irA) { var a = irA; irA = null; location.href = a; return }
      if (abiertoAlgo()) cerrarTodo()
    })
    window.addEventListener('pageshow', function () { irA = null; if (abiertoAlgo()) cerrarTodo() })
    cab.addEventListener('click', function (e) {
      var a = e.target.closest('a[href]')
      if (!a || !(history.state && history.state.menuWeb) || a.target === '_blank' || e.ctrlKey || e.metaKey || e.shiftKey) return
      e.preventDefault(); irA = a.href; history.back()
    })
    // Si la barra no cabe (depende del idioma y del ancho), menú ☰ en vez de cortar botones.
    var fila = cab.querySelector('.contenedor')
    function caber() {
      cab.classList.remove('estrecha')
      if (fila.scrollWidth > fila.clientWidth) cab.classList.add('estrecha')
      else if (cab.classList.contains('abierta') && getComputedStyle(boton).display === 'none') {
        cab.classList.remove('abierta'); boton.setAttribute('aria-expanded', 'false'); boton.textContent = '☰'
        sincronizarAtras()
      }
    }
    caber()
    window.addEventListener('resize', caber)
    if (document.fonts) document.fonts.ready.then(caber)
  }

  function pie() {
    var p = document.querySelector('[data-pie]')
    if (p) {
      p.outerHTML =
        '<div class="barra"></div>' +
        '<footer class="pie-web">' +
          '<span class="logo">' + logo + '</span>' +
          '<a class="discord" href="' + DISCORD + '" target="_blank" rel="noopener">Discord</a>' +
          '<a href="soporte.html">' + T.soporte + '</a>' +
          '<a href="privacy-policy.html">' + T.privacidad + '</a>' +
          '<a href="terms-of-service.html">' + T.condiciones + '</a>' +
          '<a href="mailto:arlequinsavehub@gmail.com">' + T.contacto + '</a>' +
          '<span>© Arlequin</span>' +
        '</footer>'
    }
    // Debajo del texto de los botones de descarga (no el de la cabecera): qué versión es y qué día salió.
    function detalle(a, version, fecha, bytes) {
      var dia = new Date(fecha + (fecha.length === 10 ? 'T12:00:00' : ''))
      var texto = T.version + ' ' + version + ' · ' + dia.toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' }) +
        (bytes ? ' · ' + Math.round(bytes / 1048576) + ' MB' : '')
      a.innerHTML = '<span class="boton-dos"><span>' + a.innerHTML + '</span><small class="detalle"></small></span>'
      a.querySelector('.detalle').textContent = texto
    }
    var botones = function (sel) { return Array.prototype.filter.call(document.querySelectorAll(sel), function (a) { return !a.closest('header') }) }
    botones('a.tienda-ms').forEach(function (a) { detalle(a, TIENDA_MS[0], TIENDA_MS[1]) })
    botones('a.linux').forEach(function (a) {
      if (LINUX) return detalle(a, LINUX[0], LINUX[1], LINUX[2])
      // Sin AppImage: fuera el botón y su nota.
      var caja = a.closest('.acciones') || a
      var nota = caja.nextElementSibling
      if (nota && nota.classList.contains('nota')) nota.remove()
      caja.remove()
    })
    // La última versión publicada (numeración tipo AMD: 26.10.beta8, 26.10.1…).
    var directas = botones('a[href$="Arlequin-GameHub-Setup.exe"]')
    if (document.querySelector('.version') || directas.length) {
      var conDatos = function (version, fecha, bytes) {
        document.querySelectorAll('.version').forEach(function (e) { e.textContent = version })
        directas.forEach(function (a) { detalle(a, version, fecha, bytes) })
      }
      // Desde el 03-11-2026 el instalador está en esta web (Cloudflare): manda DIRECTA.
      conDatos(DIRECTA[0], DIRECTA[1], DIRECTA[2])
    }
  }
  // Las capturas se amplían al pulsarlas (y se cierran con otro clic o Esc).
  function zoom() {
    document.querySelectorAll('.captura img').forEach(function (img) {
      img.addEventListener('click', function () {
        var capa = document.createElement('div')
        capa.className = 'zoom'
        capa.innerHTML = '<img alt="">'
        capa.firstChild.src = img.currentSrc || img.src
        capa.firstChild.alt = img.alt
        function cerrar() { capa.remove(); document.removeEventListener('keydown', tecla) }
        function tecla(e) { if (e.key === 'Escape') cerrar() }
        capa.addEventListener('click', cerrar)
        document.addEventListener('keydown', tecla)
        document.body.appendChild(capa)
      })
    })
  }
  // Cifras de la portada (10-11-2026): las publica Control Hub con cada BD en bd/cifras.json. Sin el archivo, no sale.
  var CIFRAS = {
    es: ['Instalaciones totales de Arlequin {n}', 'Instalaciones nuevas últimos 30 días {n}', 'Usuarios activos últimos 30 días {n}', '{n} H jugadas usando Arlequin', '{n} juegos en la base de datos'],
    en: ['Total Arlequin installs {n}', 'New installs in the last 30 days {n}', 'Active users in the last 30 days {n}', '{n} H played using Arlequin', '{n} games in the database'],
    'zh-CN': ['Arlequin 总安装量 {n}', '最近 30 天新增安装 {n}', '最近 30 天活跃用户 {n}', '使用 Arlequin 游玩了 {n} 小时', '数据库中有 {n} 款游戏'],
    ru: ['Всего установок Arlequin {n}', 'Новых установок за 30 дней {n}', 'Активных пользователей за 30 дней {n}', '{n} ч игры с Arlequin', '{n} игр в базе данных'],
    'pt-BR': ['Instalações totais do Arlequin {n}', 'Novas instalações nos últimos 30 dias {n}', 'Usuários ativos nos últimos 30 dias {n}', '{n} H jogadas usando o Arlequin', '{n} jogos no banco de dados'],
    de: ['Arlequin-Installationen gesamt {n}', 'Neue Installationen der letzten 30 Tage {n}', 'Aktive Nutzer der letzten 30 Tage {n}', '{n} Std. gespielt mit Arlequin', '{n} Spiele in der Datenbank'],
    fr: ['Installations totales d’Arlequin {n}', 'Nouvelles installations ces 30 derniers jours {n}', 'Utilisateurs actifs ces 30 derniers jours {n}', '{n} H de jeu avec Arlequin', '{n} jeux dans la base de données'],
    it: ['Installazioni totali di Arlequin {n}', 'Nuove installazioni ultimi 30 giorni {n}', 'Utenti attivi ultimi 30 giorni {n}', '{n} ore giocate usando Arlequin', '{n} giochi nel database'],
    ja: ['Arlequin 総インストール数 {n}', '直近30日の新規インストール {n}', '直近30日のアクティブユーザー {n}', 'Arlequin を使って {n} 時間プレイ', 'データベースに {n} 本のゲーム'],
    pl: ['Łączna liczba instalacji Arlequin {n}', 'Nowe instalacje z ostatnich 30 dni {n}', 'Aktywni użytkownicy z ostatnich 30 dni {n}', '{n} godz. gry z Arlequinem', '{n} gier w bazie danych'],
  }
  function cifras() {
    var caja = document.querySelector('[data-cifras]')
    if (!caja || !window.fetch) return
    var T = CIFRAS[lang] || CIFRAS.en
    // Al día (11-11-2026): Control Hub las deja en Supabase (`publico`, clave «cifras», solo lectura con la llave
    // pública) cada vez que importa. Si Supabase no contesta, las de la última BD publicada (bd/cifras.json).
    var archivo = function () { return fetch(raiz + 'bd/cifras.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw r; return r.json() }) }
    fetch('https://pkspmnhyllchgyfctmzt.supabase.co/rest/v1/publico?select=datos&clave=eq.cifras', { headers: { apikey: 'sb_publishable_XVN-ErEgZIgKVh6Ct1nYfg_9bSEyMXu' } })
      .then(function (r) { if (!r.ok) throw r; return r.json() })
      .then(function (l) { if (!l[0] || !l[0].datos || !l[0].datos.usuarios) throw 0; return l[0].datos })
      .catch(archivo).then(function (c) {
      function num(n) { return Number(n).toLocaleString(lang) }
      function txt(i, n) { return T[i].replace('{n}', '<b>' + num(n) + '</b>') }
      var trozos = []
      // Arriba las instalaciones; debajo, horas y juegos.
      if (c.usuarios) trozos.push(['var(--azul)', '👥', txt(0, c.usuarios) + (c.nuevas_30 ? ' · ' + txt(1, c.nuevas_30) : '') + (c.usuarios_30 ? ' · ' + txt(2, c.usuarios_30) : ''), true])
      if (c.horas) trozos.push(['var(--naranja)', '⏱️', txt(3, c.horas)])
      if (c.juegos) trozos.push(['var(--verde)', '🎮', txt(4, c.juegos)])
      if (!trozos.length) return
      caja.innerHTML = trozos.map(function (t) { return '<span class="cifra" style="--c: ' + t[0] + '">' + t[1] + ' ' + t[2] + '</span>' + (t[3] ? '<span class="salto"></span>' : '') }).join('')
      caja.hidden = false
    }).catch(function () { /* sin cifras: no sale nada */ })
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', cifras)
  else cifras()
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', zoom)
  else zoom()
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', pie)
  else pie()
})()
