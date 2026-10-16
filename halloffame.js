// Hall of Fame de BenchHub en la web: lee la BD pública (bd/manifest.json → la .db, con sql.js) igual que GameHub
// (tabla bench_runs: la mejor prueba limpia de cada PC en cada pestaña, best_*; sin ids). Filtros: tipo de equipo
// (Todos, Sobremesa, Portátiles; Todos por defecto), marca y modelo de procesador y de gráfica.
// Los textos de cada idioma, abajo en TEXTOS (la página dice el suyo en <html lang>).
(function () {
  var TEXTOS = {
    es: {
      cargando: 'Cargando los resultados de la comunidad…', error: 'No se han podido cargar los resultados. Prueba a recargar la página.',
      vacio: 'Aún no hay pruebas publicadas.', nadie: 'Nadie con estos filtros.',
      pestanas: { total: 'Total', cpu: 'Procesador', ram: 'RAM', gpu: 'Gráfica' },
      tipos: { todos: 'Todos', sobremesa: 'Sobremesa', portatil: 'Portátiles' },
      marcaCpu: 'Marca del procesador', modeloCpu: 'Modelo del procesador', marcaGpu: 'Marca de la gráfica', modeloGpu: 'Modelo de la gráfica',
      todas: 'Todas', todos: 'Todos', quitar: 'Quitar filtros', anonimo: 'Anónimo', creador: 'Creador de Arlequin GameHub',
      portatil: 'Portátil', puestos: function (n) { return n === 1 ? '1 PC' : n + ' PCs' },
      actualizado: function (f) { return 'Actualizado el ' + f },
    },
    en: {
      cargando: 'Loading the community results…', error: "The results couldn't be loaded. Try reloading the page.",
      vacio: 'No tests published yet.', nadie: 'Nobody with these filters.',
      pestanas: { total: 'Total', cpu: 'Processor', ram: 'RAM', gpu: 'Graphics' },
      tipos: { todos: 'All', sobremesa: 'Desktops', portatil: 'Laptops' },
      marcaCpu: 'Processor brand', modeloCpu: 'Processor model', marcaGpu: 'Graphics brand', modeloGpu: 'Graphics model',
      todas: 'All', todos: 'All', quitar: 'Clear filters', anonimo: 'Anonymous', creador: 'Creator of Arlequin GameHub',
      portatil: 'Laptop', puestos: function (n) { return n === 1 ? '1 PC' : n + ' PCs' },
      actualizado: function (f) { return 'Updated on ' + f },
    },
    'zh-CN': {
      cargando: '正在加载社区结果…', error: '无法加载结果。请尝试刷新页面。',
      vacio: '还没有发布的测试。', nadie: '没有符合这些筛选条件的结果。',
      pestanas: { total: '总分', cpu: '处理器', ram: '内存', gpu: '显卡' },
      tipos: { todos: '全部', sobremesa: '台式机', portatil: '笔记本' },
      marcaCpu: '处理器品牌', modeloCpu: '处理器型号', marcaGpu: '显卡品牌', modeloGpu: '显卡型号',
      todas: '全部', todos: '全部', quitar: '清除筛选', anonimo: '匿名', creador: 'Arlequin GameHub 创作者',
      portatil: '笔记本', puestos: function (n) { return n + ' 台电脑' },
      actualizado: function (f) { return '更新于 ' + f },
    },
  }
  var lang = document.documentElement.lang
  var T = TEXTOS[lang] || TEXTOS.es
  var raiz = lang === 'es' ? '' : '../'
  var SQLJS = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.13.0/'

  // Como en GameHub: la columna de cada pestaña y su color.
  var PESTANAS = [
    { id: 'total', marca: 'best_total', valor: 'total', color: '#ffd23f' },
    { id: 'cpu', marca: 'best_cpu', valor: 'cpu_score', color: '#ff9000' },
    { id: 'ram', marca: 'best_ram', valor: 'ram_score', color: '#3d9bff' },
    { id: 'gpu', marca: 'best_gpu', valor: 'gpu_score', color: '#2ee6a0' },
  ]
  var MARCAS = { AMD: '#ff3b3b', NVIDIA: '#76b900', Intel: '#3d9bff' }
  // «AMD Ryzen 7 9800X3D» → «Ryzen 7 9800X3D»; «NVIDIA GeForce RTX 4070» → «RTX 4070» (como GameHub).
  function corto(n) {
    return String(n || '').replace(/\((R|TM)\)|®|™/gi, '').replace(/\b(AMD|NVIDIA|Intel|GeForce|Radeon|Core)\b/g, '')
      .replace(/\b\d+(st|nd|rd|th) Gen\b/gi, '').replace(/\s+/g, ' ').trim() || '—'
  }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] }) }
  var num = new Intl.NumberFormat(lang)

  var caja = document.getElementById('hall')
  var filas = []
  var estado = { pestana: 'total', tipo: 'todos', marcaCpu: '', modeloCpu: '', marcaGpu: '', modeloGpu: '' }
  try { var g = JSON.parse(sessionStorage.getItem('hall') || 'null'); if (g) estado = Object.assign(estado, g) } catch (e) { /* sin almacenamiento */ }

  function cargarScript(src) {
    return new Promise(function (ok, mal) { var s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = mal; document.head.appendChild(s) })
  }

  caja.innerHTML = '<p class="hall-aviso">' + T.cargando + '</p>'
  Promise.all([
    cargarScript(SQLJS + 'sql-wasm.js').then(function () { return window.initSqlJs({ locateFile: function (f) { return SQLJS + f } }) }),
    fetch(raiz + 'bd/manifest.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw r; return r.json() })
      .then(function (m) { return fetch(raiz + 'bd/' + m.file).then(function (r) { if (!r.ok) throw r; return r.arrayBuffer() }).then(function (b) { return [m, b] }) }),
  ]).then(function (todo) {
    var SQL = todo[0], m = todo[1][0], bd = new SQL.Database(new Uint8Array(todo[1][1]))
    try {
      var res = bd.exec('SELECT * FROM bench_runs ORDER BY position')[0]
      filas = res ? res.values.map(function (v) { var o = {}; res.columns.forEach(function (c, i) { o[c] = v[i] }); return o }) : []
    } catch (e) { filas = [] }
    bd.close()
    var f = String(m.published_at || '').slice(0, 10)
    if (f) document.getElementById('hall-fecha').textContent = T.actualizado(new Date(f + 'T12:00:00Z').toLocaleDateString(lang))
    pintar()
  }).catch(function () { caja.innerHTML = '<p class="hall-aviso">' + T.error + '</p>' })

  function guardar() { try { sessionStorage.setItem('hall', JSON.stringify(estado)) } catch (e) { /* nada */ } }
  function unicos(l) { return l.filter(function (x, i) { return x && l.indexOf(x) === i }).sort(function (a, b) { return corto(a).localeCompare(corto(b), lang, { numeric: true }) }) }
  function opciones(valores, elegido, todos, nombre) {
    return '<option value="">' + todos + '</option>' + valores.map(function (v) {
      return '<option value="' + esc(v) + '"' + (v === elegido ? ' selected' : '') + '>' + esc(nombre ? nombre(v) : v) + '</option>'
    }).join('')
  }

  function pintar() {
    if (!filas.length) { caja.innerHTML = '<p class="hall-aviso">' + T.vacio + '</p>'; return }
    var p = PESTANAS.filter(function (x) { return x.id === estado.pestana })[0] || PESTANAS[0]
    var porTipo = function (f) { return estado.tipo === 'todos' || (estado.tipo === 'portatil') === !!f.laptop }
    var deLaPestana = filas.filter(function (f) { return f[p.marca] && f[p.valor] != null && porTipo(f) })
    // Los modelos que se ofrecen son los de la marca elegida (si hay).
    var marcasCpu = unicos(deLaPestana.map(function (f) { return f.cpu_brand }))
    var marcasGpu = unicos(deLaPestana.map(function (f) { return f.gpu_brand }))
    var modelosCpu = unicos(deLaPestana.filter(function (f) { return !estado.marcaCpu || f.cpu_brand === estado.marcaCpu }).map(function (f) { return f.cpu_model }))
    var modelosGpu = unicos(deLaPestana.filter(function (f) { return !estado.marcaGpu || f.gpu_brand === estado.marcaGpu }).map(function (f) { return f.gpu_model }))
    if (estado.modeloCpu && modelosCpu.indexOf(estado.modeloCpu) < 0) estado.modeloCpu = ''
    if (estado.modeloGpu && modelosGpu.indexOf(estado.modeloGpu) < 0) estado.modeloGpu = ''
    var lista = deLaPestana.filter(function (f) {
      return (!estado.marcaCpu || f.cpu_brand === estado.marcaCpu) && (!estado.modeloCpu || f.cpu_model === estado.modeloCpu) &&
        (!estado.marcaGpu || f.gpu_brand === estado.marcaGpu) && (!estado.modeloGpu || f.gpu_model === estado.modeloGpu)
    }).sort(function (a, b) { return b[p.valor] - a[p.valor] })
    var filtrando = estado.marcaCpu || estado.modeloCpu || estado.marcaGpu || estado.modeloGpu

    var html = '<div class="hall-pestanas" role="tablist">' + PESTANAS.map(function (x) {
      return '<button type="button" role="tab" data-pestana="' + x.id + '" style="--c:' + x.color + '"' + (x.id === p.id ? ' class="activa" aria-selected="true"' : ' aria-selected="false"') + '>' + T.pestanas[x.id] + '</button>'
    }).join('') + '</div>'
    html += '<div class="cristal hall-filtros">' +
      '<div class="hall-tipos">' + ['todos', 'sobremesa', 'portatil'].map(function (t) {
        return '<button type="button" data-tipo="' + t + '"' + (t === estado.tipo ? ' class="activo"' : '') + '>' + T.tipos[t] + '</button>'
      }).join('') + '</div>' +
      '<label>' + T.marcaCpu + '<select data-filtro="marcaCpu">' + opciones(marcasCpu, estado.marcaCpu, T.todas) + '</select></label>' +
      '<label>' + T.modeloCpu + '<select data-filtro="modeloCpu">' + opciones(modelosCpu, estado.modeloCpu, T.todos, corto) + '</select></label>' +
      '<label>' + T.marcaGpu + '<select data-filtro="marcaGpu">' + opciones(marcasGpu, estado.marcaGpu, T.todas) + '</select></label>' +
      '<label>' + T.modeloGpu + '<select data-filtro="modeloGpu">' + opciones(modelosGpu, estado.modeloGpu, T.todos, corto) + '</select></label>' +
      (filtrando ? '<button type="button" class="hall-quitar" data-quitar>✕ ' + T.quitar + '</button>' : '') +
      '</div>'
    html += '<p class="hall-cuenta">' + T.puestos(lista.length) + '</p>'
    if (!lista.length) html += '<p class="hall-aviso">' + T.nadie + '</p>'
    else {
      html += '<ol class="hall-lista">' + lista.map(function (f, i) {
        var puesto = i + 1
        var ram = [f.ram_gb && f.ram_gb + ' GB', f.ram_type && (f.ram_mts ? f.ram_type + '-' + f.ram_mts : f.ram_type)].filter(Boolean).join(' ')
        var piezas = [
          f.cpu_model && '<span style="color:' + (MARCAS[f.cpu_brand] || 'inherit') + '">' + esc(corto(f.cpu_model)) + '</span>',
          f.gpu_model && '<span style="color:' + (MARCAS[f.gpu_brand] || 'inherit') + '">' + esc(corto(f.gpu_model)) + '</span>',
          ram && esc(ram),
          f.laptop ? esc(T.portatil) : '',
        ].filter(Boolean).join(' · ')
        return '<li class="cristal' + (f.creator ? ' creador' : '') + '">' +
          '<span class="puesto' + (puesto <= 3 ? ' podio p' + puesto : '') + '">' + (puesto <= 3 ? '🏆' : puesto) + '</span>' +
          '<span class="quien"><b>' + (f.nickname ? esc(f.nickname) : '<i>' + T.anonimo + '</i>') + '</b>' +
            (f.creator ? '<span class="insignia">★ ' + T.creador + '</span>' : '') +
            '<span class="piezas">' + piezas + '</span></span>' +
          '<span class="puntos" style="color:' + p.color + '">' + num.format(Math.round(f[p.valor])) + '</span>' +
          '</li>'
      }).join('') + '</ol>'
    }
    caja.innerHTML = html

    caja.querySelectorAll('[data-pestana]').forEach(function (b) { b.onclick = function () { estado.pestana = b.getAttribute('data-pestana'); guardar(); pintar() } })
    caja.querySelectorAll('[data-tipo]').forEach(function (b) { b.onclick = function () { estado.tipo = b.getAttribute('data-tipo'); guardar(); pintar() } })
    caja.querySelectorAll('[data-filtro]').forEach(function (s) {
      s.onchange = function () {
        var k = s.getAttribute('data-filtro')
        estado[k] = s.value
        if (k === 'marcaCpu') estado.modeloCpu = ''
        if (k === 'marcaGpu') estado.modeloGpu = ''
        guardar(); pintar()
      }
    })
    var q = caja.querySelector('[data-quitar]')
    if (q) q.onclick = function () { estado.marcaCpu = estado.modeloCpu = estado.marcaGpu = estado.modeloGpu = ''; guardar(); pintar() }
  }
})()
