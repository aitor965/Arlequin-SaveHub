// Estadísticas de la comunidad en la web (31-10-2026, pedido por el dueño): lo mismo que Estadísticas de GameHub
// (src/componentes/Estadisticas.jsx), con sus pestañas, filtros y detalle, pero sin «lo tuyo» (la web no conoce tu PC).
// Lee la BD pública (bd/manifest.json → la .db, con sql.js) como el Hall of Fame: hardware_stats (las listas ya
// contadas), hardware_rows + meta.hw_columns (equipos anónimos para los filtros) y lab_runs (Rendimiento).
// Textos: en español aquí; los demás idiomas, en estadisticas-textos.js (sacados de los de GameHub con
// herramientas/textos_web_estadisticas.py del repo de GameHub, más los propios de la web).
(function () {
  var lang = document.documentElement.lang
  var DIC = (window.TEXTOS_ESTADISTICAS || {})[lang] || {}
  var raiz = lang === 'es' ? '' : '../'
  var SQLJS = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.13.0/'
  function t(s, v) {
    var r = DIC[s] || s
    return v ? r.replace(/\{(\w+)\}/g, function (m, k) { return v[k] != null ? v[k] : m }) : r
  }
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] }) }

  // Con menos equipos que esto, un filtro no enseña nada (así nadie queda señalado).
  var MIN_GRUPO = 3
  var VISIBLES = 5
  var SECCIONES = [
    { id: 'hardware', nombre: 'Hardware', color: '#ff9000', icono: '🖥️',
      grupos: [
        ['Procesador', ['Procesador (marca)', 'Procesador (modelo)', 'Núcleos', 'Hilos']],
        ['Gráfica', ['Gráfica (marca)', 'Gráfica (modelo)', 'Gráfica (ensamblador)', 'Memoria de la gráfica', 'Vatios de gráficas NVIDIA de portátil']],
        ['Memoria', ['RAM', 'Tipo de RAM', 'Velocidad de RAM', 'Latencia CL de la RAM', 'Velocidad y latencia de la RAM', 'Perfil de la RAM']],
        ['Placa base', ['Placa base (marca)', 'Placa base (modelo)']],
        ['Discos', ['Espacio total en discos', 'Discos (modelo)', 'Discos NVMe (M.2)', 'Espacio NVMe total', 'Discos SSD SATA', 'Espacio SSD SATA total', 'Discos duros (HDD)', 'Espacio HDD total']],
      ],
      filtros: ['Procesador (marca)', 'Procesador (modelo)', 'Gráfica (marca)', 'Gráfica (modelo)', 'Memoria de la gráfica', 'RAM', 'Tipo de RAM', 'Tipo de equipo', 'GameHub descargado de'] },
    { id: 'perifericos', nombre: 'Periféricos', color: '#ff5fb8', icono: '🖱️',
      grupos: [
        ['Pantalla principal', ['Pulgadas (monitor principal)', 'Resolución (pantalla principal)', 'Frecuencia (pantalla principal)', 'Tipo de panel (monitor principal)', 'Monitor principal (modelo)']],
        ['Todas las pantallas', ['Número de pantallas', 'Modelo (todos los monitores)', 'Pulgadas (todos los monitores)', 'Resolución (todos los monitores)', 'Frecuencia (todos los monitores)', 'Tipo de panel (todos los monitores)']],
        ['Teclado y ratón', ['Teclado (marca)', 'Teclado (modelo)', 'Ratón (marca)', 'Ratón (modelo)']],
        ['Mandos', ['Mandos (marca)', 'Mandos (modelo)']],
      ],
      filtros: ['Pulgadas (monitor principal)', 'Resolución (pantalla principal)', 'Frecuencia (pantalla principal)', 'Tipo de panel (monitor principal)', 'Monitor principal (modelo)', 'Número de pantallas', 'Teclado (marca)', 'Ratón (marca)', 'Tipo de equipo', 'GameHub descargado de'] },
    { id: 'sistema', nombre: 'Sistema e Internet', color: '#1de9d0', icono: '🌐',
      grupos: [
        ['Sistema', ['Sistema operativo', 'Tipo de equipo', 'GameHub descargado de']],
        ['Internet', ['Conexión a internet', 'Velocidad de bajada', 'Velocidad de subida', 'Ping', 'País']],
      ],
      filtros: ['Sistema operativo', 'Tipo de equipo', 'GameHub descargado de', 'Conexión a internet', 'Velocidad de bajada', 'Velocidad de subida', 'Ping'] },
  ]
  var MAS_USADO = { id: 'top', nombre: 'Lo más usado', color: '#b06bff', icono: '🏆', grupos: [], filtros: [], resumen: 'Lo que más tiene la gente en cada cosa' }
  var RENDIMIENTO = { id: 'rendimiento', nombre: 'Rendimiento', color: '#ff9000', icono: '⚡', filtros: [], resumen: 'BenchHub: puntos por modelo',
    grupos: [['Errores de hardware (WHEA)', ['WHEA en BenchHub', 'WHEA jugando']]] }
  var JUEGOS = { id: 'juegos', nombre: 'Juegos', color: '#2ee6a0', icono: '🎮', filtros: [], resumen: 'A qué juega la gente',
    grupos: [['Lo más jugado', ['Juegos (último mes)', 'Juegos (últimos 2 meses)']]],
    nota: 'Cada PC cuenta una vez por juego, aunque lo juegue muchas veces. Salen de las partidas con los FPS medidos (de 1 minuto o más) de quien comparte sus partidas.' }
  var PESTANAS = [MAS_USADO].concat(SECCIONES, [RENDIMIENTO, JUEGOS])
  var MES_JUEGOS = /^Juegos \((\d{4})-(\d{2})\)$/
  function gruposJuegos(cats) {
    var meses = Object.keys(cats || {}).filter(function (c) { return MES_JUEGOS.test(c) }).sort().reverse()
    return meses.length ? [[JUEGOS.grupos[0][0], meses]] : JUEGOS.grupos
  }
  function nombreCategoria(c) {
    var m = MES_JUEGOS.exec(c)
    if (!m) return t(c)
    var mes = new Date(Number(m[1]), Number(m[2]) - 1, 1).toLocaleDateString(lang, { month: 'long', year: 'numeric' })
    return mes.charAt(0).toUpperCase() + mes.slice(1)
  }
  var COLUMNAS_MAS_USADO = [['hardware'], ['perifericos', 'sistema']]
  var FUERA_DE_MAS_USADO = ['Número de pantallas', 'Modelo (todos los monitores)', 'Pulgadas (todos los monitores)', 'Resolución (todos los monitores)',
    'Frecuencia (todos los monitores)', 'Tipo de panel (todos los monitores)', 'Vatios de gráficas NVIDIA de portátil', 'Perfil de la RAM',
    'Espacio NVMe total', 'Espacio SSD SATA total', 'Espacio HDD total']
  var JUNTO = { 'Discos NVMe (M.2)': 'Espacio NVMe total', 'Discos SSD SATA': 'Espacio SSD SATA total', 'Discos duros (HDD)': 'Espacio HDD total' }
  var NOTAS = { 'País': 'Sale del «País o región» que tiene puesto cada uno en Windows, nunca de su IP: si alguien lo tiene mal, su país sale mal.' }
  var MODELOS_DE = { 'Procesador (marca)': 'Procesador (modelo)', 'Gráfica (marca)': 'Gráfica (modelo)',
    'Teclado (marca)': 'Teclado (modelo)', 'Ratón (marca)': 'Ratón (modelo)', 'Mandos (marca)': 'Mandos (modelo)' }

  // Colores de cada marca (AMD rojo, Intel azul, NVIDIA verde) en procesadores y gráficas.
  var CON_MARCA = ['Procesador (marca)', 'Procesador (modelo)', 'Gráfica (marca)', 'Gráfica (modelo)', 'Vatios de gráficas NVIDIA de portátil']
  var MARCAS = [[/\bamd\b|ryzen|radeon|threadripper/i, '#ed1c24'], [/intel/i, '#0071c5'], [/nvidia|geforce|\brtx\b|\bgtx\b/i, '#76b900']]
  function colorMarca(c, v) {
    if (CON_MARCA.indexOf(c) < 0) return null
    var m = MARCAS.filter(function (x) { return x[0].test(String(v)) })[0]
    return m ? m[1] : null
  }
  var pulgadas = function (p) { return Math.round(p * 10) / 10 + '"' }
  // Solo el modelo (la marca ya la dice el color), como GameHub; el nombre completo, al pasar el ratón.
  function soloModelo(c, v) {
    var s = String(v).replace(/\((r|tm)\)|®|™/gi, '').replace(/\s+/g, ' ').trim()
    if (/custom (apu|gpu) 0(405|932)/i.test(s)) return 'Steam Deck'
    if (c === 'Procesador (modelo)') {
      return s.replace(/\b\d+(st|nd|rd|th) Gen\s*/i, '').replace(/\s+(with|w\/)\s.*$/i, '').replace(/\s+\d+-Core.*$/i, '')
        .replace(/\s*\bProcessor\b/i, '').replace(/^(AMD|Intel)\s+/i, '').replace(/^Core\s+(?=i\d|Ultra)/i, '')
        .replace(/^Ryzen\s+(\d\s+)?/i, '').trim() || s
    }
    if (c === 'Gráfica (modelo)') {
      return s.replace(/^(NVIDIA|AMD|Intel)\s+/i, '').replace(/^GeForce\s+/i, '').replace(/^Radeon\s+(?=RX\s)/i, '')
        .replace(/\s+GPU$/i, '').replace(/^(.*\d\w*)\s+Graphics$/i, '$1').trim() || s
    }
    if (c === 'País' && /^[A-Z]{2}$/.test(s)) {
      try { return new Intl.DisplayNames([lang], { type: 'region' }).of(s) || s } catch (e) { return s }
    }
    var cuantos = s.match(/^(\d+) (núcleos|hilos)$/)
    if (cuantos) return t('{n} ' + cuantos[2], { n: cuantos[1] })
    return t(s.replace(/(\d+\.\d{2,})"/g, function (_, p) { return pulgadas(Number(p)) }))
  }

  // Orden: de más a menos equipos; con los mismos, de mejor a peor (más es mejor).
  var numeros = function (v) { return (String(v).match(/\d+(\.\d+)?/g) || []).map(Number) }
  var tope = function (v) { var n = numeros(v); return n.length ? n[n.length - 1] * (String(v).charAt(0) === '>' ? 1.01 : 1) : 0 }
  var menosEsMejor = function (v) { return -tope(v) }
  // Los modelos de procesador y gráfica valen por su rendimiento en juegos (rendimiento.js, la lista de GameHub);
  // los que no están en la lista van detrás.
  var R = window.RENDIMIENTO || {}
  var puesto = function (f) { return function (v) { var p = f ? f(v) : null; return p == null ? -Infinity : -p } }
  var ORDEN = {
    'Procesador (modelo)': puesto(R.puestoProcesador), 'Gráfica (modelo)': puesto(R.puestoGrafica),
    'Núcleos': tope, 'Hilos': tope, 'Memoria de la gráfica': tope, 'Vatios de gráficas NVIDIA de portátil': function (v) { return tope(String(v).split(' · ')[0]) },
    'RAM': tope, 'Tipo de RAM': tope, 'Velocidad de RAM': tope, 'Latencia CL de la RAM': menosEsMejor,
    'Velocidad y latencia de la RAM': function (v) { var n = numeros(v); return n[0] && n[1] ? -n[1] * 2000 / n[0] : -Infinity },
    'Espacio total en discos': tope, 'Discos NVMe (M.2)': tope, 'Espacio NVMe total': tope, 'Discos SSD SATA': tope, 'Espacio SSD SATA total': tope, 'Discos duros (HDD)': tope, 'Espacio HDD total': tope,
    'Pulgadas (monitor principal)': tope, 'Resolución (pantalla principal)': function (v) { return numeros(v).slice(0, 2).reduce(function (a, b) { return a * b }, 1) },
    'Frecuencia (pantalla principal)': tope, 'Número de pantallas': tope,
    'Velocidad de bajada': tope, 'Velocidad de subida': tope, 'Ping': menosEsMejor,
  }
  var sinValor = function (v) { return v === 'Otros' || v === 'Sin marca conocida' }
  function ordenar(c, filas) {
    var valor = ORDEN[c]
    return filas.map(function (f, i) { return [f, i] }).sort(function (a, b) {
      return sinValor(a[0].valor) - sinValor(b[0].valor) || b[0].equipos - a[0].equipos || (valor ? valor(b[0].valor) - valor(a[0].valor) || 0 : 0) || a[1] - b[1]
    }).map(function (x) { return x[0] })
  }
  function reparto(filas, i) {
    var cuenta = {}, orden = []
    filas.forEach(function (f) {
      var v = f[i]
      if (v == null || v === '') return
      if (!(v in cuenta)) { cuenta[v] = 0; orden.push(v) }
      cuenta[v]++
    })
    var total = orden.reduce(function (a, v) { return a + cuenta[v] }, 0)
    return orden.map(function (v) { return { valor: v, equipos: cuenta[v], porcentaje: Math.round(1000 * cuenta[v] / total) / 10 } })
  }

  // ---- Rendimiento (BenchHub): los puntos de cada modelo con la mejor prueba de cada PC (lab_runs) ----
  function json(x) { if (typeof x !== 'string') return x; try { return JSON.parse(x) } catch (e) { return null } }
  var mediana = function (v) { var s = v.slice().sort(function (a, b) { return a - b }), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2 }
  function ajuste(f, k) { var a = (json(f.settings) || []).filter(function (x) { return x[0] === k })[0]; return a ? a[1] : null }
  function whea(f) {
    var w = (json(f.warnings) || []).filter(function (a) { return a.id === 'whea' })[0]
    if (w) return Number(w.n) || 0
    var s = ajuste(f, 'WHEA')
    return s == null ? null : Number(s) || 0
  }
  function deBench(lab) {
    var filas = lab.filter(function (f) { return !f.old_version })
    function modelos(modelo, valor) {
      var g = {}, orden = []
      filas.forEach(function (f) {
        var m = modelo(f), v = valor(f)
        if (!m || v == null || isNaN(v)) return
        if (!g[m]) { g[m] = []; orden.push(m) }
        g[m].push(Number(v))
      })
      return orden.map(function (m) { return { modelo: m, pcs: g[m].length, normal: Math.round(mediana(g[m])), mejor: Math.round(Math.max.apply(null, g[m])) } })
        .sort(function (a, b) { return b.normal - a.normal })
    }
    var num = function (x) { var v = parseFloat(x); return v > 0 ? v : null }
    var pc = function (f) { return [f.nickname || '', f.cpu_model || '', f.gpu_model || '', !!f.laptop].join('|') }
    var porPc = {}
    filas.forEach(function (f) { var w = whea(f); if (w != null) porPc[pc(f)] = (porPc[pc(f)] || 0) + w })
    var w = reparto(Object.keys(porPc).map(function (k) { return [porPc[k] > 0 ? 'Con WHEA' : 'Sin WHEA'] }), 0)
    return {
      cpu: modelos(function (f) { return f.cpu_model }, function (f) { return f.cpu_score }),
      gpu: modelos(function (f) { return f.gpu_model }, function (f) { return f.gpu_score }),
      mhzCpu: modelos(function (f) { return f.cpu_model }, function (f) { return num((json(f.data) || {})['cpu.mhz_1']) }),
      mhzGpu: modelos(function (f) { return f.gpu_model }, function (f) { return num(ajuste(f, 'Gráfica MHz')) }),
      categorias: { 'WHEA en BenchHub': w },
    }
  }

  // ---- Carga ----
  var caja = document.getElementById('estadisticas')
  var d = null, bench = null, error = false
  var estado = { seccion: 'top', filtros: {} }
  try { var g0 = JSON.parse(sessionStorage.getItem('estadisticas') || 'null'); if (g0) estado = Object.assign(estado, g0) } catch (e) { /* sin almacenamiento */ }
  function guardar() { try { sessionStorage.setItem('estadisticas', JSON.stringify(estado)) } catch (e) { /* nada */ } }
  function cargarScript(src) {
    return new Promise(function (ok, mal) { var s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = mal; document.head.appendChild(s) })
  }
  function filasDe(bd, sql) {
    try {
      var r = bd.exec(sql)[0]
      return r ? r.values.map(function (v) { var o = {}; r.columns.forEach(function (c, i) { o[c] = v[i] }); return o }) : []
    } catch (e) { return [] }
  }
  caja.innerHTML = '<p class="hall-aviso">' + esc(t('Cargando las estadísticas de la comunidad…')) + '</p>'
  Promise.all([
    cargarScript(SQLJS + 'sql-wasm.js').then(function () { return window.initSqlJs({ locateFile: function (f) { return SQLJS + f } }) }),
    fetch(raiz + 'bd/manifest.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw r; return r.json() })
      .then(function (m) { return fetch(raiz + 'bd/' + m.file).then(function (r) { if (!r.ok) throw r; return r.arrayBuffer() }) }),
  ]).then(function (todo) {
    var bd = new todo[0].Database(new Uint8Array(todo[1]))
    var meta = {}
    filasDe(bd, 'SELECT key, value FROM meta').forEach(function (f) { meta[f.key] = f.value })
    var categorias = {}
    filasDe(bd, 'SELECT category, value, installations, percent FROM hardware_stats ORDER BY category, position').forEach(function (f) {
      (categorias[f.category] = categorias[f.category] || []).push({ valor: f.value, equipos: f.installations, porcentaje: f.percent })
    })
    d = {
      equipos: Number(meta.hw_installations) || 0, dias: Number(meta.hw_days) || 180,
      actualizado: String(meta.generated_at || '').slice(0, 10), categorias: categorias,
      columnas: json(meta.hw_columns) || [],
      filas: filasDe(bd, 'SELECT data FROM hardware_rows ORDER BY position').map(function (f) { return json(f.data) }).filter(Boolean),
    }
    bench = deBench(filasDe(bd, 'SELECT * FROM lab_runs ORDER BY position'))
    bd.close()
    pintar()
  }).catch(function () { error = true; pintar() })

  // ---- Pintar ----
  function barra(pct, color, max) {
    return '<span class="est-barra"><span style="width:' + Math.max(3, pct / (max || 100) * 100) + '%;background:' + color + '"></span></span>'
  }
  function cifra(f) { return '<span class="est-cifra"><b>' + f.porcentaje + '%</b> · ' + f.equipos + '</span>' }

  var detalle = null, abiertas = {}
  function pintar() {
    if (error || !d) { caja.innerHTML = '<p class="hall-aviso">' + esc(error ? t('No se han podido cargar las estadísticas. Prueba a recargar la página.') : t('Cargando las estadísticas de la comunidad…')) + '</p>'; return }
    if (!Object.keys(d.categorias).length) { caja.innerHTML = '<p class="hall-aviso">' + esc(t('Todavía no hay estadísticas')) + '</p>'; return }
    var s = PESTANAS.filter(function (x) { return x.id === estado.seccion })[0] || PESTANAS[0]
    var esTop = s === MAS_USADO, esRend = s === RENDIMIENTO, esJuegos = s === JUEGOS
    var conSecciones = SECCIONES.indexOf(s) >= 0
    var columnas = d.columnas, todas = d.filas
    var conFiltros = columnas.length > 0 && todas.length > 0
    var activos = conSecciones ? Object.keys(estado.filtros).filter(function (c) { return estado.filtros[c] != null && columnas.indexOf(c) >= 0 }).map(function (c) { return [c, estado.filtros[c]] }) : []
    var filtradas = todas.filter(function (f) { return activos.every(function (a) { return f[columnas.indexOf(a[0])] === a[1] }) })
    var filtrando = activos.length > 0
    var pocos = filtrando && filtradas.length < MIN_GRUPO
    function datosDe(c) {
      if (bench && bench.categorias[c]) return bench.categorias[c].length ? ordenar(c, bench.categorias[c]) : null
      if (!filtrando) return d.categorias[c] && ordenar(c, d.categorias[c])
      var origen = activos.length === 1 && activos[0][0] === 'GameHub descargado de' && d.categorias['País (' + activos[0][1] + ')']
      if (c === 'País' && origen) return ordenar(c, origen)
      var i = columnas.indexOf(c)
      return i < 0 ? null : ordenar(c, reparto(filtradas, i))
    }
    function opcionesDe(c) {
      var i = columnas.indexOf(c)
      var base = todas.filter(function (f) { return activos.every(function (a) { return a[0] === c || f[columnas.indexOf(a[0])] === a[1] }) })
      return ordenar(c, reparto(base, i).filter(function (o) { return o.valor !== 'Otros' }))
    }
    var nFiltros = Object.keys(estado.filtros).filter(function (c) { return estado.filtros[c] != null }).length
    var fecha = /^\d{4}-\d{2}-\d{2}$/.test(d.actualizado) ? new Date(d.actualizado + 'T12:00:00').toLocaleDateString(lang) : d.actualizado
    var h = '<p class="est-intro">' + esc(t(d.equipos === 1 ? '1 equipo de la comunidad (últimos {dias} días) · actualizado el {fecha}. Solo datos agrupados: nada identifica a nadie.' : '{n} equipos de la comunidad (últimos {dias} días) · actualizado el {fecha}. Solo datos agrupados: nada identifica a nadie.', { n: d.equipos, dias: d.dias, fecha: fecha })) +
      ' ' + esc(t('Los datos se revisan a mano antes de salir, así que pueden tardar en actualizarse.')) + '</p>'

    h += '<div class="est-pestanas">' + PESTANAS.map(function (x) {
      var n = SECCIONES.indexOf(x) >= 0 ? nFiltros : 0
      var sub = n ? (n === 1 ? t('1 filtro puesto') : t('{n} filtros puestos', { n: n })) : x.resumen ? t(x.resumen) : x.grupos.map(function (g) { return t(g[0]) }).join(' · ')
      return '<button type="button" data-pestana="' + x.id + '" style="--c:' + x.color + '"' + (x === s ? ' class="activa"' : '') + '>' +
        '<span class="est-icono">' + x.icono + '</span><span class="est-nombre"><b>' + esc(t(x.nombre)) + '</b><small>' + esc(sub) + '</small></span></button>'
    }).join('') + '</div>'

    if (esTop) {
      h += '<div class="est-top">' + COLUMNAS_MAS_USADO.map(function (ids) {
        return '<div class="est-top-col">' + SECCIONES.filter(function (sec) { return ids.indexOf(sec.id) >= 0 }).map(function (sec) {
          var grupos = sec.grupos.map(function (g) { return [g[0], g[1].filter(function (c) { return FUERA_DE_MAS_USADO.indexOf(c) < 0 && (datosDe(c) || []).length })] })
            .filter(function (g) { return g[1].length })
          if (!grupos.length) return ''
          return '<div class="cristal est-caja"><p class="est-seccion" style="color:' + sec.color + '">' + esc(t(sec.nombre)) + '</p>' + grupos.map(function (g) {
            return '<p class="est-grupo-top">' + esc(t(g[0])) + '</p>' + g[1].map(function (c) { return masUsado(c, datosDe(c), sec.color, JUNTO[c] && datosDe(JUNTO[c])) }).join('')
          }).join('') + '</div>'
        }).join('') + '</div>'
      }).join('') + '</div>'
    }

    if (esRend) {
      if (!bench || (!bench.cpu.length && !bench.gpu.length)) h += '<div class="cristal est-vacio">' + esc(t('Aún no hay pruebas de BenchHub publicadas.')) + '</div>'
      else {
        h += '<p class="est-titulo" style="color:' + s.color + '">' + esc(t('Puntos por modelo')) + '</p>' +
          '<p class="est-nota">' + esc(t('La mejor prueba limpia de cada PC en BenchHub. Lo normal es la mitad de los PC con ese modelo; la raya, el mejor.')) + '</p>' +
          '<div class="est-rejilla ancha">' + rendimiento('Procesador', 'Procesador (modelo)', bench.cpu, s.color) + rendimiento('Gráfica', 'Gráfica (modelo)', bench.gpu, '#2ee6a0') + '</div>'
        if (bench.mhzCpu.length || bench.mhzGpu.length) {
          h += '<p class="est-titulo" style="color:' + s.color + '">' + esc(t('Frecuencias (información)')) + '</p>' +
            '<p class="est-nota">' + esc(t('Solo información: más MHz no siempre es más rendimiento. Lo normal es la mitad de los PC con ese modelo; la raya, el más alto.')) + '</p>' +
            '<div class="est-rejilla ancha">' + rendimiento('Procesador: MHz con 1 núcleo', 'Procesador (modelo)', bench.mhzCpu, s.color, 'MHz') + rendimiento('Gráfica: MHz', 'Gráfica (modelo)', bench.mhzGpu, '#2ee6a0', 'MHz') + '</div>'
        }
        h += '<p class="est-nota">' + esc(t('En GameHub también salen la RAM de serie y con OC, la memoria de la gráfica y cuántos llevan overclock.')) + '</p>'
      }
    }

    var grupos = esJuegos ? gruposJuegos(d.categorias) : s.grupos
    if (esJuegos) {
      h += '<p class="est-nota">' + esc(t(JUEGOS.nota)) + '</p>'
      if (!grupos.some(function (g) { return g[1].some(function (c) { return (datosDe(c) || []).length }) })) h += '<div class="cristal est-vacio">' + esc(t('Los juegos más jugados llegan con la próxima actualización de las estadísticas.')) + '</div>'
    }

    if (conSecciones) {
      var aqui = s.filtros.concat(activos.map(function (a) { return a[0] }).filter(function (c) { return s.filtros.indexOf(c) < 0 }))
      h += '<div class="cristal est-filtros"><div class="est-filtros-cabeza"><b>' + s.icono + ' ' + esc(t('Compárate: filtra por lo que quieras')) + '</b>' +
        (filtrando ? '<button type="button" class="hall-quitar" data-quitar>✕ ' + esc(t('Quitar filtros')) + '</button>' : '') + '</div>'
      if (conFiltros) {
        h += '<div class="est-selects">' + aqui.filter(function (c) { return columnas.indexOf(c) >= 0 }).map(function (c) {
          var v = estado.filtros[c]
          return '<label' + (v != null ? ' class="activo" style="--c:' + s.color + '"' : '') + '><span>' + esc(nombreCategoria(c)) + '</span><select data-filtro="' + esc(c) + '">' +
            '<option value="">' + esc(t('Todos')) + '</option>' + opcionesDe(c).map(function (o) {
              return '<option value="' + esc(o.valor) + '"' + (o.valor === v ? ' selected' : '') + '>' + esc(soloModelo(c, o.valor)) + ' · ' + o.equipos + '</option>'
            }).join('') + '</select></label>'
        }).join('') + '</div>'
        h += '<p class="est-cuenta"' + (filtrando ? ' style="color:' + s.color + '"' : '') + '>' + esc(filtrando
          ? t(filtradas.length === 1 ? 'Coincide 1 de {total} equipos ({p} %).' : 'Coinciden {n} de {total} equipos ({p} %).', { n: filtradas.length, total: todas.length, p: Math.round(1000 * filtradas.length / Math.max(1, todas.length)) / 10 })
          : t('Elige, por ejemplo, una gráfica o unas pulgadas y verás qué tienen los equipos como ese.')) + '</p>'
      } else h += '<p class="est-cuenta">' + esc(t('Los filtros llegan con la próxima actualización de las estadísticas.')) + '</p>'
      h += '</div>'
    }

    if (!esTop) {
      if (pocos) {
        h += '<div class="cristal est-vacio"><b>' + esc(t('Muy pocos equipos con estos filtros')) + '</b><br>' + esc(t('Hacen falta al menos {n} para enseñar algo (así nadie queda señalado). Quita algún filtro.', { n: MIN_GRUPO })) + '</div>'
      } else {
        grupos.forEach(function (g) {
          var presentes = g[1].filter(function (c) { return (datosDe(c) || []).length })
          if (!presentes.length) return
          h += '<p class="est-titulo" style="color:' + s.color + '">' + esc(t(g[0])) + '</p><div class="est-rejilla">' +
            presentes.map(function (c) { return categoria(c, datosDe(c), s.color) }).join('') + '</div>'
        })
      }
      if (filtrando && !pocos) h += '<p class="est-nota">' + esc(t('Con filtros, el país solo sale al filtrar únicamente por «GameHub descargado de» y, si quedan menos de 3 equipos, no se enseña el resultado.')) + '</p>'
    }
    caja.innerHTML = h

    caja.querySelectorAll('[data-pestana]').forEach(function (b) { b.onclick = function () { estado.seccion = b.getAttribute('data-pestana'); guardar(); pintar() } })
    caja.querySelectorAll('[data-abrir]').forEach(function (b) { b.onclick = function () { detalle = b.getAttribute('data-abrir'); abiertas = {}; pintarDetalle() } })
    caja.querySelectorAll('[data-filtro]').forEach(function (sel) {
      sel.onchange = function () { var c = sel.getAttribute('data-filtro'); if (sel.value) estado.filtros[c] = sel.value; else delete estado.filtros[c]; guardar(); pintar() }
    })
    var q = caja.querySelector('[data-quitar]')
    if (q) q.onclick = function () { estado.filtros = {}; guardar(); pintar() }

    // El detalle de una categoría, en una capa encima (como el comparador del Hall of Fame).
    var capa = document.querySelector('.est-capa')
    if (capa && !detalle) capa.remove()
    if (detalle) pintarDetalle()
    function pintarDetalle() {
      var filas = datosDe(detalle)
      if (!filas || !filas.length) { detalle = null; var c0 = document.querySelector('.est-capa'); if (c0) c0.remove(); return }
      var modelos = MODELOS_DE[detalle] ? datosDe(MODELOS_DE[detalle]) : null
      var junto = esTop && JUNTO[detalle] ? datosDe(JUNTO[detalle]) : null
      var filtrable = conFiltros && s.filtros.indexOf(detalle) >= 0 && columnas.indexOf(detalle) >= 0
      var max = Math.max.apply(null, filas.map(function (f) { return f.porcentaje }))
      var total = filas.reduce(function (a, f) { return a + f.equipos }, 0)
      function fila(c, f, mx, sangria, extra) {
        return '<div class="est-fila' + (sangria ? ' sangria' : '') + '"><span class="est-valor" title="' + esc(f.valor) + '">' + esc(soloModelo(c, f.valor)) + '</span>' +
          barra(f.porcentaje, colorMarca(c, f.valor) || s.color, mx) + cifra(f) + (extra || '') +
          (filtrable && !sangria && c === detalle && f.valor !== 'Otros' ? '<button type="button" class="est-embudo" data-filtrar="' + esc(f.valor) + '" title="' + esc(t('Filtrar por esto')) + '">⏷</button>' : '') + '</div>'
      }
      var lista = filas.map(function (f) {
        var suyos = modelos ? modelos.filter(function (m) { return m.valor !== 'Otros' && String(m.valor).toLowerCase().indexOf(String(f.valor).toLowerCase()) >= 0 }) : []
        var abierta = abiertas[f.valor]
        var extra = suyos.length ? '<button type="button" class="est-modelos" data-marca="' + esc(f.valor) + '" style="color:' + s.color + '" title="' + esc(t('Ver sus modelos')) + '">' + suyos.length + ' ' + (abierta ? '▴' : '▾') + '</button>' : ''
        return fila(detalle, f, max, false, extra) + (abierta ? suyos.map(function (m) { return fila(MODELOS_DE[detalle], m, max, true) }).join('') : '')
      }).join('')
      var h2 = '<div class="hall-capa-caja cristal est-detalle" role="dialog" aria-modal="true"><div class="hall-capa-cabeza"><b>' + esc(nombreCategoria(detalle)) + '</b>' +
        '<button type="button" class="hall-capa-x" data-cerrar aria-label="✕">✕</button></div>' +
        '<p class="hall-capa-ayuda">' + esc(t('{n} respuestas · {v} valores distintos', { n: total, v: filas.length })) + '</p><div class="est-detalle-lista' + (junto ? ' dos' : '') + '">'
      if (junto) {
        var mj = Math.max.apply(null, junto.map(function (f) { return f.porcentaje }))
        h2 += '<div><p class="est-grupo-top">' + esc(t('Cantidad')) + '</p>' + lista + '</div><div><p class="est-grupo-top">' + esc(t('Tamaño')) + '</p>' +
          junto.map(function (f) { return fila(JUNTO[detalle], f, mj) }).join('') + '</div>'
      } else h2 += '<div>' + lista + '</div>'
      h2 += '</div>' + (NOTAS[detalle] ? '<p class="est-nota">' + esc(t(NOTAS[detalle])) + '</p>' : '') +
        (modelos ? '<p class="est-nota">' + esc(t('Pulsa el número de una marca para ver sus modelos.')) + '</p>' : '') +
        (filtrable ? '<p class="est-nota">' + esc(t('El embudo filtra todas las estadísticas por ese valor.')) + '</p>' : '') + '</div>'
      var capa2 = document.querySelector('.est-capa')
      if (!capa2) {
        capa2 = document.createElement('div')
        capa2.className = 'hall-capa est-capa'
        document.body.appendChild(capa2)
        capa2.addEventListener('mousedown', function (e) { if (e.target === capa2) cerrar() })
      }
      capa2.innerHTML = h2
      capa2.querySelector('[data-cerrar]').onclick = cerrar
      capa2.querySelectorAll('[data-marca]').forEach(function (b) { b.onclick = function () { var m = b.getAttribute('data-marca'); abiertas[m] = !abiertas[m]; pintarDetalle() } })
      capa2.querySelectorAll('[data-filtrar]').forEach(function (b) { b.onclick = function () { estado.filtros[detalle] = b.getAttribute('data-filtrar'); detalle = null; guardar(); pintar() } })
    }
  }
  function cerrar() { detalle = null; var c = document.querySelector('.est-capa'); if (c) c.remove() }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && detalle) cerrar() })

  // Una tarjeta: las 5 primeras con su barra y «Ver todos».
  function categoria(c, todas, color) {
    var max = Math.max.apply(null, todas.map(function (f) { return f.porcentaje }))
    return '<div class="cristal est-tarjeta" data-abrir="' + esc(c) + '" title="' + esc(t('Ver el detalle')) + '"><p class="est-tarjeta-titulo">' + esc(nombreCategoria(c)) + '</p>' +
      todas.slice(0, VISIBLES).map(function (f, k) {
        return '<div class="est-fila"><span class="est-puesto">' + (k + 1) + '</span><span class="est-valor" title="' + esc(f.valor) + '">' + esc(soloModelo(c, f.valor)) + '</span>' +
          barra(f.porcentaje, colorMarca(c, f.valor) || color, max) + cifra(f) + '</div>'
      }).join('') +
      (todas.length > VISIBLES ? '<span class="est-ver" style="color:' + color + '">' + esc(t('Ver todos ({n})', { n: todas.length })) + '</span>' : '') +
      (NOTAS[c] ? '<p class="est-nota">' + esc(t(NOTAS[c])) + '</p>' : '') + '</div>'
  }
  // «Lo más usado»: una línea con lo que más tiene la gente en una categoría (y el espacio, en los discos).
  function masUsado(c, filas, color, junto) {
    var top = filas.filter(function (f) { return !sinValor(f.valor) })[0]
    if (!top) return ''
    var otro = junto && junto.filter(function (f) { return !sinValor(f.valor) })[0]
    var empatados = filas.filter(function (f) { return f !== top && !sinValor(f.valor) && f.equipos === top.equipos }).length
    return '<button type="button" class="est-linea" data-abrir="' + esc(c) + '" title="' + esc(t('Ver el detalle')) + '">' +
      '<span class="est-linea-cat">' + esc(nombreCategoria(c)) + '</span>' +
      '<span class="est-linea-valor" title="' + esc(top.valor) + '">' + (otro ? '<small>' + esc(t('Cantidad')) + '</small> ' : '') + esc(soloModelo(c, top.valor)) +
      (otro ? ' <small class="est-junto">' + esc(t('Tamaño')) + '</small> ' + esc(soloModelo(JUNTO[c], otro.valor)) + ' <small>' + otro.porcentaje + '%</small>' : '') + '</span>' +
      '<span class="est-linea-barra">' + barra(top.porcentaje, colorMarca(c, top.valor) || color) + cifra(top) + '</span>' +
      (empatados ? '<span class="est-linea-nota">' + esc(empatados === 1 ? t('Empatado con 1 más') : t('Empatado con {n} más', { n: empatados })) + '</span>' : '') + '</button>'
  }
  // Rendimiento: lo normal (la mediana de los PC con ese modelo), el mejor (la raya) y cuántos PC.
  function rendimiento(titulo, tipo, filas, color, unidad) {
    if (!filas || !filas.length) return ''
    var max = Math.max.apply(null, filas.map(function (f) { return f.mejor }))
    var nf = new Intl.NumberFormat(lang)
    return '<div class="cristal est-tarjeta fija"><p class="est-tarjeta-titulo">' + esc(t(titulo)) + '</p>' + filas.map(function (f, k) {
      return '<div class="est-fila"><span class="est-puesto">' + (k + 1) + '</span><span class="est-valor" title="' + esc(f.modelo) + '">' + esc(soloModelo(tipo, f.modelo)) + '</span>' +
        '<span class="est-barra"><span style="width:' + Math.max(3, f.normal / max * 100) + '%;background:' + color + '"></span>' +
        (f.mejor > f.normal ? '<i style="left:calc(' + (f.mejor / max * 100) + '% - 2px)" title="' + esc(t('El mejor')) + '"></i>' : '') + '</span>' +
        '<span class="est-cifra" title="' + esc(t('Lo normal · el mejor · PC')) + '"><b>' + nf.format(f.normal) + ' ' + esc(unidad || t('puntos')) + '</b> · ' + nf.format(f.mejor) + ' · ' +
        esc(f.pcs === 1 ? t('1 PC') : t('{n} PC', { n: f.pcs })) + '</span></div>'
    }).join('') + '</div>'
  }
})()
