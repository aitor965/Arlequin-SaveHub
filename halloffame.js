// Hall of Fame de BenchHub y BenchLab en la web: lee la BD pública (bd/manifest.json → la .db, con sql.js) igual que
// GameHub: BenchHub (tabla bench_runs: la mejor prueba limpia de cada PC en cada pestaña, best_*; sin ids) y BenchLab
// (tabla lab_runs: el mejor total de cada PC), los dos con Total/Procesador/RAM/Gráfica. Lo de versiones anteriores
// (old_version = 1, con sus puntos de entonces) va aparte, en «Versiones antiguas». Filtros: tipo de equipo
// (Todos, Sobremesa, Portátiles; Todos por defecto), marca y modelo de procesador y de gráfica.
// Los textos de cada idioma, abajo en TEXTOS (la página dice el suyo en <html lang>).
(function () {
  var TEXTOS = {
    es: {
      cargando: 'Cargando los resultados de la comunidad…', error: 'No se han podido cargar los resultados. Prueba a recargar la página.',
      vacio: 'Aún no hay pruebas publicadas.', nadie: 'Nadie con estos filtros.',
      pestanas: { total: 'Total', cpu: 'Procesador', ram: 'RAM', gpu: 'Gráfica' },
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub: la prueba rápida de procesador, RAM y gráfica. Sale la mejor prueba de cada PC en cada parte.',
      labInfo: 'BenchHub: sale el mejor total de cada PC.',
      antiguas: 'Versiones antiguas', antiguasInfo: 'Pruebas hechas con versiones anteriores, con sus puntos de entonces: no se comparan con las de ahora.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Procesador y RAM') + ' v' + a, g && 'Gráfica v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Procesador ' + c + ' · RAM ' + r + ' · Gráfica ' + g },
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
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub: the quick processor, RAM and graphics test. Each PC shows its best test in each part.',
      labInfo: 'BenchHub: each PC shows its best total.',
      antiguas: 'Older versions', antiguasInfo: 'Tests run with earlier versions, with their original scores: not comparable with current ones.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Processor and RAM') + ' v' + a, g && 'Graphics v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Processor ' + c + ' · RAM ' + r + ' · Graphics ' + g },
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
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub：处理器、内存和显卡的快速测试。显示每台电脑在每个部分的最佳测试。',
      labInfo: 'BenchHub：显示每台电脑的最佳总分。',
      antiguas: '旧版本', antiguasInfo: '使用旧版测试完成的结果，保留当时的分数：不与当前分数比较。',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : '处理器和内存') + ' v' + a, g && '显卡 v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return '处理器 ' + c + ' · 内存 ' + r + ' · 显卡 ' + g },
      tipos: { todos: '全部', sobremesa: '台式机', portatil: '笔记本' },
      marcaCpu: '处理器品牌', modeloCpu: '处理器型号', marcaGpu: '显卡品牌', modeloGpu: '显卡型号',
      todas: '全部', todos: '全部', quitar: '清除筛选', anonimo: '匿名', creador: 'Arlequin GameHub 创作者',
      portatil: '笔记本', puestos: function (n) { return n + ' 台电脑' },
      actualizado: function (f) { return '更新于 ' + f },
    },
    ru: {
      cargando: 'Загружаем результаты сообщества…', error: 'Не удалось загрузить результаты. Попробуйте обновить страницу.',
      vacio: 'Опубликованных тестов пока нет.', nadie: 'Никого с такими фильтрами.',
      pestanas: { total: 'Итого', cpu: 'Процессор', ram: 'ОЗУ', gpu: 'Видеокарта' },
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub: быстрый тест процессора, ОЗУ и видеокарты. Показан лучший тест каждого ПК в каждой части.',
      labInfo: 'BenchHub: показан лучший итог каждого ПК.',
      antiguas: 'Старые версии', antiguasInfo: 'Тесты на прежних версиях, с тогдашними очками: не сравниваются с нынешними.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Процессор и ОЗУ') + ' v' + a, g && 'Видеокарта v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Процессор ' + c + ' · ОЗУ ' + r + ' · Видеокарта ' + g },
      tipos: { todos: 'Все', sobremesa: 'Настольные', portatil: 'Ноутбуки' },
      marcaCpu: 'Бренд процессора', modeloCpu: 'Модель процессора', marcaGpu: 'Бренд видеокарты', modeloGpu: 'Модель видеокарты',
      todas: 'Все', todos: 'Все', quitar: 'Сбросить фильтры', anonimo: 'Аноним', creador: 'Создатель Arlequin GameHub',
      portatil: 'Ноутбук', puestos: function (n) { return n + ' ПК' },
      actualizado: function (f) { return 'Обновлено ' + f },
    },
    'pt-BR': {
      cargando: 'Carregando os resultados da comunidade…', error: 'Não foi possível carregar os resultados. Tente recarregar a página.',
      vacio: 'Ainda não há testes publicados.', nadie: 'Ninguém com esses filtros.',
      pestanas: { total: 'Total', cpu: 'Processador', ram: 'RAM', gpu: 'Placa de vídeo' },
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub: o teste rápido de processador, RAM e placa de vídeo. Aparece o melhor teste de cada PC em cada parte.',
      labInfo: 'BenchHub: aparece o melhor total de cada PC.',
      antiguas: 'Versões antigas', antiguasInfo: 'Testes feitos com versões anteriores, com os pontos da época: não se comparam com os de agora.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Processador e RAM') + ' v' + a, g && 'Placa de vídeo v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Processador ' + c + ' · RAM ' + r + ' · Placa de vídeo ' + g },
      tipos: { todos: 'Todos', sobremesa: 'Desktops', portatil: 'Notebooks' },
      marcaCpu: 'Marca do processador', modeloCpu: 'Modelo do processador', marcaGpu: 'Marca da placa de vídeo', modeloGpu: 'Modelo da placa de vídeo',
      todas: 'Todas', todos: 'Todos', quitar: 'Limpar filtros', anonimo: 'Anônimo', creador: 'Criador do Arlequin GameHub',
      portatil: 'Notebook', puestos: function (n) { return n === 1 ? '1 PC' : n + ' PCs' },
      actualizado: function (f) { return 'Atualizado em ' + f },
    },
    de: {
      cargando: 'Ergebnisse der Community werden geladen…', error: 'Die Ergebnisse konnten nicht geladen werden. Lade die Seite neu.',
      vacio: 'Noch keine veröffentlichten Tests.', nadie: 'Niemand mit diesen Filtern.',
      pestanas: { total: 'Gesamt', cpu: 'Prozessor', ram: 'RAM', gpu: 'Grafikkarte' },
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub: der schnelle Test für Prozessor, RAM und Grafikkarte. Jeder PC zeigt seinen besten Test in jedem Teil.',
      labInfo: 'BenchHub: Jeder PC zeigt sein bestes Gesamtergebnis.',
      antiguas: 'Ältere Versionen', antiguasInfo: 'Tests mit früheren Versionen, mit ihren damaligen Punkten: nicht mit den aktuellen vergleichbar.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Prozessor und RAM') + ' v' + a, g && 'Grafikkarte v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Prozessor ' + c + ' · RAM ' + r + ' · Grafikkarte ' + g },
      tipos: { todos: 'Alle', sobremesa: 'Desktops', portatil: 'Laptops' },
      marcaCpu: 'Prozessormarke', modeloCpu: 'Prozessormodell', marcaGpu: 'Grafikkartenmarke', modeloGpu: 'Grafikkartenmodell',
      todas: 'Alle', todos: 'Alle', quitar: 'Filter zurücksetzen', anonimo: 'Anonym', creador: 'Ersteller von Arlequin GameHub',
      portatil: 'Laptop', puestos: function (n) { return n === 1 ? '1 PC' : n + ' PCs' },
      actualizado: function (f) { return 'Aktualisiert am ' + f },
    },
    fr: {
      cargando: 'Chargement des résultats de la communauté…', error: 'Impossible de charger les résultats. Essaie de recharger la page.',
      vacio: 'Aucun test publié pour l’instant.', nadie: 'Personne avec ces filtres.',
      pestanas: { total: 'Total', cpu: 'Processeur', ram: 'RAM', gpu: 'Carte graphique' },
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub : le test rapide de processeur, RAM et carte graphique. Chaque PC affiche son meilleur test dans chaque partie.',
      labInfo: 'BenchHub : chaque PC affiche son meilleur total.',
      antiguas: 'Anciennes versions', antiguasInfo: 'Tests faits avec des versions précédentes, avec leurs points de l’époque : ils ne se comparent pas aux actuels.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Processeur et RAM') + ' v' + a, g && 'Carte graphique v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Processeur ' + c + ' · RAM ' + r + ' · Carte graphique ' + g },
      tipos: { todos: 'Tous', sobremesa: 'Ordinateurs de bureau', portatil: 'Portables' },
      marcaCpu: 'Marque du processeur', modeloCpu: 'Modèle du processeur', marcaGpu: 'Marque de la carte graphique', modeloGpu: 'Modèle de la carte graphique',
      todas: 'Toutes', todos: 'Tous', quitar: 'Effacer les filtres', anonimo: 'Anonyme', creador: 'Créateur d’Arlequin GameHub',
      portatil: 'Portable', puestos: function (n) { return n === 1 ? '1 PC' : n + ' PC' },
      actualizado: function (f) { return 'Mis à jour le ' + f },
    },
    it: {
      cargando: 'Caricamento dei risultati della community…', error: 'Impossibile caricare i risultati. Prova a ricaricare la pagina.',
      vacio: 'Ancora nessun test pubblicato.', nadie: 'Nessuno con questi filtri.',
      pestanas: { total: 'Totale', cpu: 'Processore', ram: 'RAM', gpu: 'Scheda video' },
      modos: { hub: 'BenchHub', lab: 'BenchHub' },
      hubInfo: 'BenchHub: il test veloce di processore, RAM e scheda video. Ogni PC mostra il suo miglior test in ogni parte.',
      labInfo: 'BenchHub: ogni PC mostra il suo miglior totale.',
      antiguas: 'Versioni precedenti', antiguasInfo: 'Test fatti con versioni precedenti, con i punti di allora: non si confrontano con quelli attuali.',
      version: function (a, g, lab) { return [a && (lab ? 'BenchHub' : 'Processore e RAM') + ' v' + a, g && 'Scheda video v' + g].filter(Boolean).join(' · ') },
      partes: function (c, r, g) { return 'Processore ' + c + ' · RAM ' + r + ' · Scheda video ' + g },
      tipos: { todos: 'Tutti', sobremesa: 'Desktop', portatil: 'Portatili' },
      marcaCpu: 'Marca del processore', modeloCpu: 'Modello del processore', marcaGpu: 'Marca della scheda video', modeloGpu: 'Modello della scheda video',
      todas: 'Tutte', todos: 'Tutti', quitar: 'Togli i filtri', anonimo: 'Anonimo', creador: 'Creatore di Arlequin GameHub',
      portatil: 'Portatile', puestos: function (n) { return n === 1 ? '1 PC' : n + ' PC' },
      actualizado: function (f) { return 'Aggiornato il ' + f },
    },
  }
  var lang = document.documentElement.lang
  var T = TEXTOS[lang] || TEXTOS.en
  var raiz = lang === 'es' ? '' : '../'
  var SQLJS = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.13.0/'

  // ---- AimHub (24-10-2026, pedido por el dueño) ----
  // Su ranking no va en la BD pública: lo publica Control Hub en Supabase (tabla `publico`, clave `aimhub`) después de
  // revisar cada partida, y se lee igual que lo lee GameHub, con la llave pública (solo deja leer lo público). Por modo y
  // duración: las 50 mejores (`top`, con su configuración) y todos los valores (`valores`). Se baja al abrir la pestaña.
  var AIM = {
    es: {
      titulo: 'Los que mejor apuntan de la comunidad',
      lema: 'Las mejores partidas de <b>AimHub</b> (Herramientas → AimHub en GameHub, de momento en la beta): la mejor de cada jugador en cada modo y duración, revisadas antes de salir.',
      beta: 'beta', modos: { rejilla: 'Rejilla', flick: 'Flick', micro: 'Microajustes', seguimiento: 'Seguimiento', reaccion: 'Reacción' },
      info: 'Con cada partida sale con qué se jugó: juego y sensibilidad, DPI, FOV y Hz de la pantalla. Reacción: la media de 5 rondas (menos es mejor).',
      nadie: 'Aún no hay nadie en este modo.', precision: 'precisión', porDiana: 'por diana', enDiana: 'en la diana', mejor: 'mejor', vertical: 'vertical',
      jugadores: function (n) { return n === 1 ? '1 jugador' : n + ' jugadores' },
    },
    en: {
      titulo: 'The best aimers in the community',
      lema: 'The best <b>AimHub</b> runs (Tools → AimHub in GameHub, in the beta for now): each player’s best in every mode and length, checked before they go up.',
      beta: 'beta', modos: { rejilla: 'Grid', flick: 'Flick', micro: 'Micro-adjust', seguimiento: 'Tracking', reaccion: 'Reaction' },
      info: 'Each run shows what it was played with: game and sensitivity, DPI, FOV and screen Hz. Reaction: the average of 5 rounds (lower is better).',
      nadie: 'Nobody in this mode yet.', precision: 'accuracy', porDiana: 'per target', enDiana: 'on target', mejor: 'best', vertical: 'vertical',
      jugadores: function (n) { return n === 1 ? '1 player' : n + ' players' },
    },
    'zh-CN': {
      titulo: '社区里枪法最好的玩家',
      lema: '<b>AimHub</b> 的最佳成绩（GameHub 中的 工具 → AimHub，目前在测试版中）：每位玩家在每个模式和时长下的最好成绩，发布前经过审核。',
      beta: '测试版', modos: { rejilla: '网格', flick: '甩枪', micro: '微调', seguimiento: '跟枪', reaccion: '反应' },
      info: '每局成绩都会显示所用设置：游戏和灵敏度、DPI、FOV 和屏幕刷新率。反应：5 轮的平均值（越低越好）。',
      nadie: '这个模式还没有人。', precision: '命中率', porDiana: '每个靶子', enDiana: '在靶上', mejor: '最佳', vertical: '垂直',
      jugadores: function (n) { return n + ' 名玩家' },
    },
    ru: {
      titulo: 'Самые меткие в сообществе',
      lema: 'Лучшие игры в <b>AimHub</b> (Инструменты → AimHub в GameHub, пока в бете): лучшая игра каждого игрока в каждом режиме и длительности, проверенная перед публикацией.',
      beta: 'бета', modos: { rejilla: 'Сетка', flick: 'Флик', micro: 'Микрокоррекция', seguimiento: 'Слежение', reaccion: 'Реакция' },
      info: 'У каждой игры видно, с чем она сыграна: игра и чувствительность, DPI, FOV и частота экрана. Реакция: среднее за 5 раундов (меньше — лучше).',
      nadie: 'В этом режиме пока никого нет.', precision: 'точность', porDiana: 'на мишень', enDiana: 'на мишени', mejor: 'лучшее', vertical: 'по вертикали',
      jugadores: function (n) { return 'Игроков: ' + n },
    },
    'pt-BR': {
      titulo: 'Quem mira melhor na comunidade',
      lema: 'As melhores partidas do <b>AimHub</b> (Ferramentas → AimHub no GameHub, por enquanto na beta): a melhor de cada jogador em cada modo e duração, revisadas antes de sair.',
      beta: 'beta', modos: { rejilla: 'Grade', flick: 'Flick', micro: 'Microajustes', seguimiento: 'Rastreamento', reaccion: 'Reação' },
      info: 'Cada partida mostra com o que foi jogada: jogo e sensibilidade, DPI, FOV e Hz da tela. Reação: a média de 5 rodadas (menos é melhor).',
      nadie: 'Ainda não há ninguém neste modo.', precision: 'precisão', porDiana: 'por alvo', enDiana: 'no alvo', mejor: 'melhor', vertical: 'vertical',
      jugadores: function (n) { return n === 1 ? '1 jogador' : n + ' jogadores' },
    },
    de: {
      titulo: 'Die besten Schützen der Community',
      lema: 'Die besten Runden in <b>AimHub</b> (Werkzeuge → AimHub in GameHub, vorerst in der Beta): die beste Runde jedes Spielers in jedem Modus und jeder Dauer, vor der Veröffentlichung geprüft.',
      beta: 'Beta', modos: { rejilla: 'Raster', flick: 'Flick', micro: 'Feinjustierung', seguimiento: 'Tracking', reaccion: 'Reaktion' },
      info: 'Bei jeder Runde steht, womit sie gespielt wurde: Spiel und Empfindlichkeit, DPI, FOV und Hz des Bildschirms. Reaktion: der Schnitt aus 5 Runden (weniger ist besser).',
      nadie: 'In diesem Modus ist noch niemand.', precision: 'Genauigkeit', porDiana: 'pro Ziel', enDiana: 'im Ziel', mejor: 'Bestwert', vertical: 'vertikal',
      jugadores: function (n) { return n === 1 ? '1 Spieler' : n + ' Spieler' },
    },
    fr: {
      titulo: 'Les meilleurs viseurs de la communauté',
      lema: 'Les meilleures parties d’<b>AimHub</b> (Outils → AimHub dans GameHub, pour l’instant dans la bêta) : la meilleure de chaque joueur dans chaque mode et durée, vérifiées avant d’être publiées.',
      beta: 'bêta', modos: { rejilla: 'Grille', flick: 'Flick', micro: 'Micro-ajustements', seguimiento: 'Suivi', reaccion: 'Réaction' },
      info: 'Chaque partie indique avec quoi elle a été jouée : jeu et sensibilité, DPI, FOV et Hz de l’écran. Réaction : la moyenne de 5 manches (moins, c’est mieux).',
      nadie: 'Personne dans ce mode pour l’instant.', precision: 'précision', porDiana: 'par cible', enDiana: 'sur la cible', mejor: 'meilleur', vertical: 'vertical',
      jugadores: function (n) { return n === 1 ? '1 joueur' : n + ' joueurs' },
    },
    it: {
      titulo: 'I migliori a mirare della community',
      lema: 'Le migliori partite di <b>AimHub</b> (Strumenti → AimHub in GameHub, per ora nella beta): la migliore di ogni giocatore in ogni modalità e durata, controllate prima di uscire.',
      beta: 'beta', modos: { rejilla: 'Griglia', flick: 'Flick', micro: 'Microregolazioni', seguimiento: 'Tracciamento', reaccion: 'Reazione' },
      info: 'Ogni partita mostra con cosa è stata giocata: gioco e sensibilità, DPI, FOV e Hz dello schermo. Reazione: la media di 5 round (meno è meglio).',
      nadie: 'Ancora nessuno in questa modalità.', precision: 'precisione', porDiana: 'per bersaglio', enDiana: 'sul bersaglio', mejor: 'migliore', vertical: 'verticale',
      jugadores: function (n) { return n === 1 ? '1 giocatore' : n + ' giocatori' },
    },
  }
  var A = AIM[lang] || AIM.en
  var AIM_URL = 'https://pkspmnhyllchgyfctmzt.supabase.co/rest/v1/publico?clave=eq.aimhub&select=datos'
  var LLAVE_PUBLICA = 'sb_publishable_XVN-ErEgZIgKVh6Ct1nYfg_9bSEyMXu'
  // Los colores y el orden de GameHub (AimHub.jsx); el Calentamiento no tiene ranking.
  var AIM_MODOS = [{ id: 'rejilla', color: '#ff9000' }, { id: 'flick', color: '#ff3b3b' }, { id: 'micro', color: '#3d9bff' },
    { id: 'seguimiento', color: '#1de9d0' }, { id: 'reaccion', color: '#ffd23f' }]
  // El nombre de cada juego de AimHub (JUEGOS de src/aimhub.js en GameHub) y su unidad, si tiene.
  var JUEGOS = { cs2: 'Counter-Strike 2', valorant: 'VALORANT', apex: 'Apex Legends', overwatch2: 'Overwatch 2', fortnite: 'Fortnite %',
    cod: 'Call of Duty', r6: 'Rainbow Six Siege', thefinals: 'THE FINALS', marvelrivals: 'Marvel Rivals', deadlock: 'Deadlock', tf2: 'Team Fortress 2',
    titanfall2: 'Titanfall 2', destiny2: 'Destiny 2', rust: 'Rust', tarkov: 'Escape from Tarkov', csgo: 'CS:GO', cs16: 'Counter-Strike 1.6',
    halflife: 'Half-Life', l4d2: 'Left 4 Dead 2', portal2: 'Portal 2', gmod: "Garry's Mod", doometernal: 'DOOM Eternal', quake: 'Quake Champions',
    quakelive: 'Quake Live', kovaaks: "KovaaK's" }
  var aim // undefined: sin pedir · null: no se pudo · si no, el documento
  function pedirAim() {
    aim = false
    fetch(AIM_URL, { headers: { apikey: LLAVE_PUBLICA }, cache: 'no-cache' }).then(function (r) { if (!r.ok) throw r; return r.json() })
      .then(function (l) { aim = (l[0] && l[0].datos) || { categorias: {} } }).catch(function () { aim = null }).then(pintar)
  }

  // Como en GameHub: la columna de cada pestaña y su color.
  // (En BenchLab no hay best_*: cada PC sale con su mejor total, ordenado por la parte elegida.)
  var PESTANAS = [
    { id: 'total', marca: 'best_total', valor: 'total', color: '#ffd23f' },
    { id: 'cpu', marca: 'best_cpu', valor: 'cpu_score', color: '#ff9000' },
    { id: 'ram', marca: 'best_ram', valor: 'ram_score', color: '#3d9bff' },
    { id: 'gpu', marca: 'best_gpu', valor: 'gpu_score', color: '#2ee6a0' },
  ]
  // Desde la 26.10.4 BenchHub es una sola prueba (la que era BenchLab): solo su Hall of Fame.
  var MODOS = [{ id: 'lab', color: '#b06bff' }]
  // Las pruebas de versiones anteriores (old_version = 1) van aparte, por versión.
  function claveVersion(f) { return (f.lab_version != null ? f.lab_version : f.cpu_version != null ? f.cpu_version : '') + '|' + (f.gpu_version != null ? f.gpu_version : '') }
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
  var errorBench = false
  var lab = []
  var estado = { seccion: 'bench', aimModo: 'rejilla', aimDur: 60, modo: 'lab', pestana: 'total', antigua: '', tipo: 'todos', marcaCpu: '', modeloCpu: '', marcaGpu: '', modeloGpu: '' }
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
    try {
      var rl = bd.exec('SELECT * FROM lab_runs ORDER BY position')[0]
      lab = rl ? rl.values.map(function (v) { var o = {}; rl.columns.forEach(function (c, i) { o[c] = v[i] }); return o }) : []
    } catch (e) { lab = [] }
    bd.close()
    var f = String(m.published_at || '').slice(0, 10)
    if (f) document.getElementById('hall-fecha').textContent = T.actualizado(new Date(f + 'T12:00:00Z').toLocaleDateString(lang))
    pintar()
  }).catch(function () { errorBench = true; pintar() })

  function guardar() { try { sessionStorage.setItem('hall', JSON.stringify(estado)) } catch (e) { /* nada */ } }
  function unicos(l) { return l.filter(function (x, i) { return x && l.indexOf(x) === i }).sort(function (a, b) { return corto(a).localeCompare(corto(b), lang, { numeric: true }) }) }
  function opciones(valores, elegido, todos, nombre) {
    return '<option value="">' + todos + '</option>' + valores.map(function (v) {
      return '<option value="' + esc(v) + '"' + (v === elegido ? ' selected' : '') + '>' + esc(nombre ? nombre(v) : v) + '</option>'
    }).join('')
  }

  // Arriba, BenchHub (los PCs) o AimHub (la puntería); el título y el texto de la página cambian con la pestaña.
  var cabeza = document.querySelector('.cabeza-pagina h1'), lema = document.querySelector('.cabeza-pagina .lema')
  var original = [cabeza.innerHTML, lema.innerHTML]
  function secciones() {
    var enAim = estado.seccion === 'aim'
    cabeza.innerHTML = enAim ? A.titulo : original[0]
    lema.innerHTML = enAim ? A.lema : original[1]
    return '<div class="hall-pestanas hall-modos">' + [['bench', 'BenchHub', '#b06bff'], ['aim', 'AimHub <small>' + A.beta + '</small>', '#ff5fb8']].map(function (x) {
      return '<button type="button" data-seccion="' + x[0] + '" style="--c:' + x[2] + '"' + (x[0] === estado.seccion ? ' class="activa"' : '') + '>' + x[1] + '</button>'
    }).join('') + '</div>'
  }
  function enlazarSecciones() {
    caja.querySelectorAll('[data-seccion]').forEach(function (b) { b.onclick = function () { estado.seccion = b.getAttribute('data-seccion'); guardar(); pintar() } })
  }

  function pintar() {
    if (estado.seccion === 'aim') return pintarAim()
    if (!filas.length && !lab.length) { caja.innerHTML = secciones() + '<p class="hall-aviso">' + (errorBench ? T.error : T.vacio) + '</p>'; enlazarSecciones(); return }
    estado.modo = 'lab'
    if (estado.pestana === 'lab') estado.pestana = 'total'
    var enLab = estado.modo === 'lab'
    var p = PESTANAS.filter(function (x) { return x.id === estado.pestana })[0] || PESTANAS[0]
    var color = enLab && p.id === 'total' ? '#b06bff' : p.color
    var todas = enLab ? lab : filas
    var versiones = todas.filter(function (f) { return f.old_version }).map(claveVersion).filter(function (v, i, l) { return l.indexOf(v) === i })
    if (estado.antigua && versiones.indexOf(estado.antigua) < 0) estado.antigua = ''
    var porTipo = function (f) { return estado.tipo === 'todos' || (estado.tipo === 'portatil') === !!f.laptop }
    var deLaPestana = todas.filter(function (f) { return estado.antigua ? f.old_version && claveVersion(f) === estado.antigua : !f.old_version })
      .filter(function (f) { return (enLab || f[p.marca]) && f[p.valor] != null && porTipo(f) })
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

    var html = secciones()
    html += MODOS.length < 2 ? '' : '<div class="hall-pestanas hall-modos">' + MODOS.map(function (x) {
      return '<button type="button" data-modo="' + x.id + '" style="--c:' + x.color + '"' + (x.id === estado.modo ? ' class="activa"' : '') + '>' + T.modos[x.id] + '</button>'
    }).join('') + '</div>'
    html += '<div class="hall-pestanas" role="tablist">' + PESTANAS.map(function (x) {
      var c = enLab && x.id === 'total' ? '#b06bff' : x.color
      return '<button type="button" role="tab" data-pestana="' + x.id + '" style="--c:' + c + '"' + (x.id === p.id ? ' class="activa" aria-selected="true"' : ' aria-selected="false"') + '>' + T.pestanas[x.id] + '</button>'
    }).join('') +
      (versiones.length ? '<button type="button" class="hall-antiguas' + (estado.antigua ? ' activa' : '') + '" data-antiguas>' + T.antiguas + '</button>' : '') + '</div>'
    html += '<p class="hall-info">' + (enLab ? T.labInfo : T.hubInfo) + '</p>'
    if (estado.antigua) {
      html += '<p class="hall-info">' + T.antiguasInfo + '</p><div class="hall-tipos hall-versiones">' + versiones.map(function (v) {
        var x = v.split('|')
        return '<button type="button" data-version="' + esc(v) + '"' + (v === estado.antigua ? ' class="activo"' : '') + '>' + esc(T.version(x[0], x[1], enLab)) + '</button>'
      }).join('') + '</div>'
    }
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
        var ram = [f.ram_gb && f.ram_gb + ' GB', f.ram_type && (f.ram_mts ? f.ram_type + '-' + f.ram_mts : f.ram_type), enLab && f.ram_timings && 'CL' + f.ram_timings].filter(Boolean).join(' ')
        var piezas = [
          f.cpu_model && '<span style="color:' + (MARCAS[f.cpu_brand] || 'inherit') + '">' + esc(corto(f.cpu_model)) + '</span>',
          f.gpu_model && '<span style="color:' + (MARCAS[f.gpu_brand] || 'inherit') + '">' + esc(corto(f.gpu_model)) + '</span>',
          ram && esc(ram),
          f.laptop ? esc(T.portatil) : '',
        ].filter(Boolean).join(' · ')
        return '<li class="cristal' + (f.creator ? ' creador' : '') + '" data-pos="' + f.position + '" tabindex="0" title="' + esc(N.ver) + '">' +
          '<span class="puesto' + (puesto <= 3 ? ' podio p' + puesto : '') + '">' + (puesto <= 3 ? '🏆' : puesto) + '</span>' +
          '<span class="quien"><b>' + (f.nickname ? esc(f.nickname) : '<i>' + T.anonimo + '</i>') + '</b>' +
            (f.creator ? '<span class="insignia">★ ' + T.creador + '</span>' : '') +
            '<span class="piezas">' + piezas + '</span>' +
            (enLab && f.cpu_score != null ? '<span class="piezas">' + esc(T.partes(num.format(f.cpu_score), num.format(f.ram_score), num.format(f.gpu_score))) + '</span>' : '') +
            '</span>' +
          '<span class="puntos" style="color:' + color + '">' + num.format(Math.round(f[p.valor])) + '</span>' +
          '</li>'
      }).join('') + '</ol>'
    }
    caja.innerHTML = html
    enlazarSecciones()

    // Pulsar una prueba: la ventana con todo lo suyo, para compararla con otras.
    caja.querySelectorAll('[data-pos]').forEach(function (li) {
      var abrirla = function () { var pos = Number(li.getAttribute('data-pos')); var f = todas.filter(function (x) { return x.position === pos })[0]; if (f) abrir(f) }
      li.onclick = abrirla
      li.onkeydown = function (e) { if (e.key === 'Enter') abrirla() }
    })
    caja.querySelectorAll('[data-pestana]').forEach(function (b) { b.onclick = function () { estado.pestana = b.getAttribute('data-pestana'); guardar(); pintar() } })
    caja.querySelectorAll('[data-modo]').forEach(function (b) { b.onclick = function () { estado.modo = b.getAttribute('data-modo'); estado.antigua = ''; guardar(); pintar() } })
    caja.querySelectorAll('[data-version]').forEach(function (b) { b.onclick = function () { estado.antigua = b.getAttribute('data-version'); guardar(); pintar() } })
    var va = caja.querySelector('[data-antiguas]')
    if (va) va.onclick = function () { estado.antigua = estado.antigua ? '' : versiones[0]; guardar(); pintar() }
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
  // AimHub: un modo (y su duración, menos en Reacción) y su ranking, como la pestaña Hall of Fame de AimHub en GameHub.
  function pintarAim() {
    var html = secciones()
    if (aim === undefined) pedirAim()
    var m = AIM_MODOS.filter(function (x) { return x.id === estado.aimModo })[0] || AIM_MODOS[0]
    var menos = m.id === 'reaccion'
    if ([30, 60, 90].indexOf(estado.aimDur) < 0) estado.aimDur = 60
    html += '<div class="hall-pestanas" role="tablist">' + AIM_MODOS.map(function (x) {
      return '<button type="button" role="tab" data-aim-modo="' + x.id + '" style="--c:' + x.color + '"' + (x.id === m.id ? ' class="activa" aria-selected="true"' : ' aria-selected="false"') + '>' + A.modos[x.id] + '</button>'
    }).join('') + '</div>'
    if (!menos) html += '<div class="hall-tipos hall-versiones">' + [30, 60, 90].map(function (s) {
      return '<button type="button" data-aim-dur="' + s + '"' + (s === estado.aimDur ? ' class="activo"' : '') + '>' + s + ' s</button>'
    }).join('') + '</div>'
    html += '<p class="hall-info">' + A.info + '</p>'
    var datos = aim && aim.categorias && aim.categorias[menos ? 'reaccion' : m.id + ':' + estado.aimDur]
    var top = (datos && datos.top) || []
    var n1 = function (v, d) { return v == null ? '—' : new Intl.NumberFormat(lang, { maximumFractionDigits: d || 0 }).format(Number(v)) }
    if (aim === undefined || aim === false) html += '<p class="hall-aviso">' + T.cargando + '</p>'
    else if (aim === null) html += '<p class="hall-aviso">' + T.error + '</p>'
    else if (!top.length) html += '<p class="hall-aviso">' + A.nadie + '</p>'
    else {
      html += '<p class="hall-cuenta">' + A.jugadores((datos.valores || top).length) + '</p><ol class="hall-lista">' + top.map(function (f, i) {
        var puesto = i + 1, c = f.config || {}
        var juego = JUEGOS[c.game]
        var sens = juego && c.sens != null ? esc(juego.replace(' %', '')) + ' ' + n1(c.sens, 3) + (juego.slice(-2) === ' %' ? ' %' : '') : c.cm360 != null ? n1(c.cm360, 1) + ' cm/360°' : ''
        var config = [sens, c.dpi && n1(c.dpi) + ' DPI', c.vertical && Math.abs(c.vertical - 1) > 0.001 && A.vertical + ' ' + n1(c.vertical * 100) + ' %',
          c.fov && 'FOV ' + n1(c.fov) + '°', c.hz && n1(c.hz) + ' Hz'].filter(Boolean).join(' · ')
        var extra = menos ? A.mejor + ' ' + n1(f.mejor_ms) + ' ms'
          : m.id === 'seguimiento' ? n1(f.en_diana, 1) + ' % ' + A.enDiana
            : n1(f.precision, 1) + ' % ' + A.precision + ' · ' + n1(f.ms_diana) + ' ms ' + A.porDiana
        return '<li class="cristal">' +
          '<span class="puesto' + (puesto <= 3 ? ' podio p' + puesto : '') + '">' + (puesto <= 3 ? '🏆' : puesto) + '</span>' +
          '<span class="quien"><b>' + (f.apodo ? esc(f.apodo) : '<i>' + T.anonimo + '</i>') + '</b>' +
            '<span class="piezas">' + esc(extra) + '</span>' + (config ? '<span class="piezas">' + config + '</span>' : '') + '</span>' +
          '<span class="puntos" style="color:' + m.color + '">' + (menos ? n1(f.valor) + ' ms' : n1(f.valor)) + '</span>' +
          '</li>'
      }).join('') + '</ol>'
    }
    caja.innerHTML = html
    enlazarSecciones()
    caja.querySelectorAll('[data-aim-modo]').forEach(function (b) { b.onclick = function () { estado.aimModo = b.getAttribute('data-aim-modo'); guardar(); pintar() } })
    caja.querySelectorAll('[data-aim-dur]').forEach(function (b) { b.onclick = function () { estado.aimDur = Number(b.getAttribute('data-aim-dur')); guardar(); pintar() } })
  }

  // ---- Ver una prueba y compararla con otras (hasta 4), como en GameHub ----

  var NOMBRES = {
    es: {
      ver: 'Ver la prueba y comparar', titulo: 'Pruebas del Hall of Fame', anadir: '+ Añadir otra para comparar', max: 'Como mucho 4 a la vez.',
      buscar: 'Buscar por apodo, procesador o gráfica', quitar: 'Quitar', cerrar: 'Cerrar',
      ayuda: 'En verde, la mejor de cada dato; el % es frente a la primera; en amarillo, lo que no es igual.',
      g: { puntos: 'Puntos', piezas: 'Piezas', cpu: 'Procesador', ram: 'RAM', gpu: 'Gráfica', ajustes: 'Ajustes' },
      f: { total: 'Total', cpu: 'Procesador', ram: 'RAM', gpu: 'Gráfica', nucleos: 'Núcleos / hilos', vram: 'VRAM', ramTxt: 'RAM', fabrica: 'RAM de fábrica',
        portatil: 'Portátil', si: 'Sí', no: 'No', fecha: 'Fecha', version: 'Versión', isa: 'Instrucciones', driver: 'Driver',
        uno: '1 núcleo', todos: 'Todos los núcleos', mhz1: 'MHz con 1 núcleo', mhzN: 'MHz con todos', limite: 'Frenado por calor o energía', temp: 'Temperatura máxima',
        vatios: 'Consumo máximo', lectura: 'Lectura', escritura: 'Escritura', copia: 'Copia', latencia: 'Latencia', cache: 'Latencia a', fps: 'FPS',
        fps1: '1 % más lento', fps01: '0,1 % más lento', mhz: 'MHz', mhzMem: 'MHz de la memoria', consumoPct: 'Consumo (% del máximo)', uso: 'Uso',
        hilo1: '1 hilo', hilosN: 'todos los hilos', hilos: 'hilos', escalado: 'Escalado', nucleo: 'Núcleo', ancho: 'Lectura con' },
      pruebas: { comprimir: 'Comprimir', resumenes: 'Cifrar y resumir', fisica: 'Física', logica: 'Lógica', juego: 'Juego', vectorial: 'Vectorial' },
      datos: { un_nucleo: '1 núcleo (las 5 pruebas)', todos: 'Todos los núcleos (las 5 pruebas)', mhz_1: 'MHz con 1 hilo', entre_nucleos: 'Latencia entre núcleos (media)',
        entre_nucleos_max: 'Latencia entre núcleos (la peor)', entre_nucleos_ccd: 'Latencia entre núcleos del mismo CCD', pts_vatio: 'Puntos por vatio',
        lectura: 'Lectura', escritura: 'Escritura', copia: 'Copia', latencia: 'Latencia (1 GB)', latencia_carga: 'Latencia con carga', l1: 'Caché L1', l2: 'Caché L2', l3: 'Caché L3',
        lectura_1ccd: 'Lectura con un solo CCD', escritura_1ccd: 'Escritura con un solo CCD', copia_1ccd: 'Copia con un solo CCD',
        'vram.lectura': 'VRAM: lectura', 'vram.escritura': 'VRAM: escritura', 'vram.copia': 'VRAM: copia', 'vram.latencia': 'VRAM: latencia', 'vram.errores': 'VRAM: errores',
        tflops: 'Cálculo puro (FP32)', 'pcie.subida': 'PCIe: del PC a la gráfica', 'pcie.bajada': 'PCIe: de la gráfica al PC',
        fps: 'FPS', fps_1: '1 % más lento', fps_01: '0,1 % más lento', fps_vatio: 'FPS por vatio', mhz: 'MHz', temp: 'temperatura máxima', vatios: 'consumo máximo',
        hotspot: 'punto más caliente', vram_temp: 'temperatura de la memoria', voltaje: 'voltaje máximo' },
    },
    en: {
      ver: 'View the test and compare', titulo: 'Hall of Fame tests', anadir: '+ Add another to compare', max: 'At most 4 at a time.',
      buscar: 'Search by nickname, processor or graphics card', quitar: 'Remove', cerrar: 'Close',
      ayuda: 'In green, the best of each figure; the % is against the first one; in yellow, what differs.',
      g: { puntos: 'Points', piezas: 'Parts', cpu: 'Processor', ram: 'RAM', gpu: 'Graphics', ajustes: 'Settings' },
      f: { total: 'Total', cpu: 'Processor', ram: 'RAM', gpu: 'Graphics', nucleos: 'Cores / threads', vram: 'VRAM', ramTxt: 'RAM', fabrica: 'Rated RAM speed',
        portatil: 'Laptop', si: 'Yes', no: 'No', fecha: 'Date', version: 'Version', isa: 'Instructions', driver: 'Driver',
        uno: '1 core', todos: 'All cores', mhz1: 'MHz on 1 core', mhzN: 'MHz on all cores', limite: 'Throttled by heat or power', temp: 'Peak temperature',
        vatios: 'Peak power', lectura: 'Read', escritura: 'Write', copia: 'Copy', latencia: 'Latency', cache: 'Latency at', fps: 'FPS',
        fps1: '1% low', fps01: '0.1% low', mhz: 'MHz', mhzMem: 'Memory MHz', consumoPct: 'Power (% of max)', uso: 'Usage',
        hilo1: '1 thread', hilosN: 'all threads', hilos: 'threads', escalado: 'Scaling', nucleo: 'Core', ancho: 'Read with' },
      pruebas: { comprimir: 'Compression', resumenes: 'Encryption and hashing', fisica: 'Physics', logica: 'Logic', juego: 'Game', vectorial: 'Vector' },
      datos: { un_nucleo: '1 core (all 5 tests)', todos: 'All cores (all 5 tests)', mhz_1: 'MHz on 1 thread', entre_nucleos: 'Core-to-core latency (average)',
        entre_nucleos_max: 'Core-to-core latency (worst)', entre_nucleos_ccd: 'Core-to-core latency within a CCD', pts_vatio: 'Points per watt',
        lectura: 'Read', escritura: 'Write', copia: 'Copy', latencia: 'Latency (1 GB)', latencia_carga: 'Latency under load', l1: 'L1 cache', l2: 'L2 cache', l3: 'L3 cache',
        lectura_1ccd: 'Read on a single CCD', escritura_1ccd: 'Write on a single CCD', copia_1ccd: 'Copy on a single CCD',
        'vram.lectura': 'VRAM: read', 'vram.escritura': 'VRAM: write', 'vram.copia': 'VRAM: copy', 'vram.latencia': 'VRAM: latency', 'vram.errores': 'VRAM: errors',
        tflops: 'Raw compute (FP32)', 'pcie.subida': 'PCIe: PC to graphics', 'pcie.bajada': 'PCIe: graphics to PC',
        fps: 'FPS', fps_1: '1% low', fps_01: '0.1% low', fps_vatio: 'FPS per watt', mhz: 'MHz', temp: 'peak temperature', vatios: 'peak power',
        hotspot: 'hotspot', vram_temp: 'memory temperature', voltaje: 'peak voltage' },
    },
    'zh-CN': {
      ver: '查看测试并比较', titulo: '名人堂测试', anadir: '+ 添加另一个进行比较', max: '最多同时 4 个。',
      buscar: '按昵称、处理器或显卡搜索', quitar: '移除', cerrar: '关闭',
      ayuda: '绿色为每项数据的最佳值；百分比相对于第一个；黄色表示不相同的项。',
      g: { puntos: '分数', piezas: '硬件', cpu: '处理器', ram: '内存', gpu: '显卡', ajustes: '设置' },
      f: { total: '总分', cpu: '处理器', ram: '内存', gpu: '显卡', nucleos: '核心 / 线程', vram: '显存', ramTxt: '内存', fabrica: '内存额定频率',
        portatil: '笔记本', si: '是', no: '否', fecha: '日期', version: '版本', isa: '指令集', driver: '驱动',
        uno: '单核', todos: '全核', mhz1: '单核频率', mhzN: '全核频率', limite: '因温度或功耗降频', temp: '最高温度',
        vatios: '最大功耗', lectura: '读取', escritura: '写入', copia: '复制', latencia: '延迟', cache: '延迟', fps: 'FPS',
        fps1: '1% 低帧', fps01: '0.1% 低帧', mhz: '频率', mhzMem: '显存频率', consumoPct: '功耗（最大值的百分比）', uso: '占用',
        hilo1: '1 线程', hilosN: '全部线程', hilos: '线程', escalado: '扩展', nucleo: '核心', ancho: '读取' },
      pruebas: { comprimir: '压缩', resumenes: '加密和哈希', fisica: '物理', logica: '逻辑', juego: '游戏', vectorial: '向量' },
      datos: { un_nucleo: '单核（全部 5 项）', todos: '全核（全部 5 项）', mhz_1: '单线程频率', entre_nucleos: '核心间延迟（平均）',
        entre_nucleos_max: '核心间延迟（最差）', entre_nucleos_ccd: '同一 CCD 内的核心间延迟', pts_vatio: '每瓦分数',
        lectura: '读取', escritura: '写入', copia: '复制', latencia: '延迟（1 GB）', latencia_carga: '负载下延迟', l1: 'L1 缓存', l2: 'L2 缓存', l3: 'L3 缓存',
        lectura_1ccd: '单 CCD 读取', escritura_1ccd: '单 CCD 写入', copia_1ccd: '单 CCD 复制',
        'vram.lectura': '显存：读取', 'vram.escritura': '显存：写入', 'vram.copia': '显存：复制', 'vram.latencia': '显存：延迟', 'vram.errores': '显存：错误',
        tflops: '纯计算（FP32）', 'pcie.subida': 'PCIe：电脑到显卡', 'pcie.bajada': 'PCIe：显卡到电脑',
        fps: 'FPS', fps_1: '1% 低帧', fps_01: '0.1% 低帧', fps_vatio: '每瓦 FPS', mhz: '频率', temp: '最高温度', vatios: '最大功耗',
        hotspot: '热点温度', vram_temp: '显存温度', voltaje: '最高电压' },
    },
  }
  var N = NOMBRES[lang] || NOMBRES.en
  var ISA = { avx512: 'AVX-512', avx2: 'AVX2', sse2: 'SSE2' }
  var RES = { '1080p': '1080p', '1440p': '1440p', '4k': '4K' }
  // Los ajustes que GameHub apunta en español: su nombre en cada idioma (los técnicos, como PPT o FCLK, se quedan).
  var AJ = {
    en: { 'Plan de energía': 'Power plan', 'Integridad de memoria': 'Memory integrity', 'Modo de juego': 'Game Mode', 'Programación de GPU por hardware': 'Hardware-accelerated GPU scheduling',
      'Núcleos / hilos': 'Cores / threads', 'Instrucciones': 'Instructions', 'Capacidad': 'Capacity', 'Módulos': 'Modules', 'RAM de fábrica': 'Rated RAM speed',
      'MHz todos': 'MHz all cores', 'Vcore máx.': 'Max Vcore', 'Temp. máx.': 'Max temp.', 'Consumo máx.': 'Max power', 'Temp. VRM máx.': 'Max VRM temp.',
      'PPT usado': 'PPT used', 'TDC usado': 'TDC used', 'EDC usado': 'EDC used', 'Temp. RAM máx.': 'Max RAM temp.', 'Gráfica MHz': 'GPU MHz',
      'Gráfica frenada por': 'GPU limited by', 'Límite de consumo de la gráfica': 'GPU power limit', 'Gráfica temp. máx.': 'GPU max temp.',
      'Gráfica punto caliente máx.': 'GPU max hotspot', 'Gráfica temp. memoria máx.': 'GPU max memory temp.', 'Gráfica voltaje máx.': 'GPU max voltage',
      'Gráfica consumo máx.': 'GPU max power', 'Gráfica ventilador máx.': 'GPU max fan speed' },
    'zh-CN': { 'Plan de energía': '电源计划', 'Integridad de memoria': '内存完整性', 'Modo de juego': '游戏模式', 'Programación de GPU por hardware': '硬件加速 GPU 计划',
      'Núcleos / hilos': '核心 / 线程', 'Instrucciones': '指令集', 'Capacidad': '容量', 'Módulos': '内存条', 'RAM de fábrica': '内存额定频率',
      'MHz todos': '全核频率', 'Vcore máx.': '最高 Vcore', 'Temp. máx.': '最高温度', 'Consumo máx.': '最大功耗', 'Temp. VRM máx.': 'VRM 最高温度',
      'PPT usado': 'PPT 占用', 'TDC usado': 'TDC 占用', 'EDC usado': 'EDC 占用', 'Temp. RAM máx.': '内存最高温度', 'Gráfica MHz': '显卡频率',
      'Gráfica frenada por': '显卡受限于', 'Límite de consumo de la gráfica': '显卡功耗上限', 'Gráfica temp. máx.': '显卡最高温度',
      'Gráfica punto caliente máx.': '显卡最高热点温度', 'Gráfica temp. memoria máx.': '显存最高温度', 'Gráfica voltaje máx.': '显卡最高电压',
      'Gráfica consumo máx.': '显卡最大功耗', 'Gráfica ventilador máx.': '显卡最高风扇转速' },
  }
  function nombreAjuste(n) { return (AJ[lang] || (lang === 'es' ? {} : AJ.en))[n] || n }
  function json(t) { if (t == null || typeof t !== 'string') return t; try { return JSON.parse(t) } catch (e) { return null } }

  function nombreDato(id, isa) {
    var p = id.split('.'), D = N.datos
    if (p[0] === 'cpu') {
      if (N.pruebas[p[1]]) return N.pruebas[p[1]] + (p[1] === 'vectorial' && isa ? ' (' + (ISA[isa] || isa) + ')' : '') + ' · ' + (p[2] === '1' ? N.f.hilo1 : N.f.hilosN)
      return D[p[1]] || id
    }
    if (p[0] === 'ram') return D[p[1]] || id
    var resto = p.slice(1).join('.')
    if (D[resto] && !RES[p[1]]) return D[resto]
    return (RES[p[1]] || p[1]) + ' · ' + (D[p[2]] || p[2])
  }
  function unidadDe(id) {
    var p = id.split('.')
    if (p[0] === 'cpu') return p[1] === 'vectorial' ? 'GFLOPS' : p[1] === 'mhz_1' ? 'MHz' : p[1].indexOf('entre_nucleos') === 0 ? 'ns' : p[1] === 'pts_vatio' ? 'pts/W' : ''
    if (p[0] === 'ram') return /^(lectura|escritura|copia)/.test(p[1]) ? 'GB/s' : 'ns'
    if (p[1] === 'vram') return p[2] === 'latencia' ? 'ns' : p[2] === 'errores' ? '' : 'GB/s'
    if (p[1] === 'tflops') return 'TFLOPS'
    if (p[1] === 'pcie') return 'GB/s'
    return { fps: 'FPS', fps_1: 'FPS', fps_01: 'FPS', fps_vatio: 'FPS/W', mhz: 'MHz', temp: '°C', hotspot: '°C', vram_temp: '°C', vatios: 'W', voltaje: 'V' }[p[2]] || ''
  }
  // El orden de los datos de BenchLab, como en GameHub (la BD los guarda por orden alfabético).
  var ORDEN = ['cpu.comprimir', 'cpu.resumenes', 'cpu.fisica', 'cpu.logica', 'cpu.juego', 'cpu.vectorial', 'cpu.un_nucleo', 'cpu.todos', 'cpu.mhz_1',
    'cpu.entre_nucleos', 'cpu.pts_vatio', 'ram.lectura', 'ram.escritura', 'ram.copia', 'ram.latencia', 'ram.l1', 'ram.l2', 'ram.l3',
    'gpu.1080p', 'gpu.1440p', 'gpu.4k', 'gpu.vram', 'gpu.tflops', 'gpu.pcie']
  var SUB = ['fps', 'fps_1', 'fps_01', 'fps_vatio', 'mhz', 'temp', 'vatios', 'hotspot', 'vram_temp', 'voltaje']
  function orden(id) {
    var i = -1
    ORDEN.forEach(function (o, k) { if (i < 0 && (id === o || id.indexOf(o + '.') === 0 || id.indexOf(o + '_') === 0)) i = k })
    var p = id.split('.')
    var resto = p[0] === 'gpu' && RES[p[1]] ? SUB.indexOf(p[2]) : (p[2] === 'n' ? 1 : 0) + (/_1ccd|_ccd|_max|_carga/.test(id) ? 0.5 : 0)
    return (i < 0 ? 99 : i) * 100 + (resto < 0 ? 50 : resto)
  }
  function menosMejor(id) { return /latencia|entre_nucleos|hotspot|vram_temp|voltaje|\.temp$|\.vatios$|^ram\.l[123]$|errores|limite|temp_max|watts/.test(id) }
  var GRUPO_AJ = {
    ram: ['Capacidad', 'Módulos', 'RAM de fábrica', 'RAM', 'UCLK:MCLK', 'MCLK', 'UCLK', 'FCLK', 'VSOC', 'tCL-tRCD-tRP-tRAS', 'tRC', 'tRFC', 'tRFC (ns)', 'tRRDS', 'tRRDL', 'tFAW', 'tWTRS', 'tWTRL', 'tWR', 'tRTP', 'tCWL', 'GDM', 'Command Rate', 'Temp. RAM máx.'],
    gpu: ['VRAM', 'Driver', 'PCIe', 'Resizable BAR', 'Límite de consumo de la gráfica', 'Gráfica MHz', 'VRAM MHz', 'Gráfica frenada por'],
  }
  function grupoAjuste(n) { return GRUPO_AJ.ram.indexOf(n) >= 0 ? 'ram' : GRUPO_AJ.gpu.indexOf(n) >= 0 || n.indexOf('Gráfica ') === 0 ? 'gpu' : 'cpu' }

  // Todo lo que se sabe de una fila, en grupos de {k, texto, v (número) o t (texto), u (unidad), menos}.
  function datosDe(f, enLabFila) {
    var g = { puntos: [], piezas: [], cpu: [], ram: [], gpu: [], ajustes: [] }
    var n = function (grupo, k, texto, v, u, menos) { if (v != null && v !== '') g[grupo].push({ k: k, texto: texto, v: Number(v), u: u || '', menos: !!menos }) }
    var t = function (grupo, k, texto, v) { if (v != null && v !== '') g[grupo].push({ k: k, texto: texto, t: String(v) }) }
    n('puntos', 'p.total', N.f.total, f.total); n('puntos', 'p.cpu', N.f.cpu, f.cpu_score); n('puntos', 'p.ram', N.f.ram, f.ram_score); n('puntos', 'p.gpu', N.f.gpu, f.gpu_score)
    t('piezas', 'z.cpu', N.f.cpu, corto(f.cpu_model)); t('piezas', 'z.hilos', N.f.nucleos, f.cpu_cores ? f.cpu_cores + ' / ' + f.cpu_threads : null)
    t('piezas', 'z.gpu', N.f.gpu, corto(f.gpu_model)); t('piezas', 'z.vram', N.f.vram, f.gpu_vram_gb ? Math.round(f.gpu_vram_gb) + ' GB' : null)
    t('piezas', 'z.ram', N.f.ramTxt, [f.ram_gb && f.ram_gb + ' GB', f.ram_type && (f.ram_mts ? f.ram_type + '-' + f.ram_mts : f.ram_type), f.ram_timings && 'CL' + f.ram_timings].filter(Boolean).join(' '))
    t('piezas', 'z.fab', N.f.fabrica, f.ram_rated_mts ? f.ram_rated_mts + ' MT/s' + (f.ram_rated_cl ? ' CL' + f.ram_rated_cl : '') : null)
    t('piezas', 'z.isa', N.f.isa, f.isa ? ISA[f.isa] || f.isa : null)
    t('piezas', 'z.lap', N.f.portatil, f.laptop ? N.f.si : N.f.no)
    t('piezas', 'z.fecha', N.f.fecha, f.run_on)
    t('piezas', 'z.ver', N.f.version, enLabFila ? (f.lab_version != null ? 'BenchHub v' + f.lab_version : null) : [f.cpu_version != null && 'CPU v' + f.cpu_version, f.gpu_version != null && 'GPU v' + f.gpu_version].filter(Boolean).join(' · '))
    if (enLabFila) {
      var d = json(f.data) || {}
      Object.keys(d).sort(function (a, b) { return orden(a) - orden(b) }).forEach(function (id) {
        var grupo = id.split('.')[0]
        if (g[grupo]) n(grupo, 'd.' + id, nombreDato(id, f.isa), d[id], unidadDe(id), menosMejor(id))
      })
      var c = json(f.curves) || {}
      ;(c.threads || []).forEach(function (x) { n('cpu', 'th' + x[0], N.f.escalado + ' · ' + (x[0] === 1 ? N.f.hilo1 : x[0] + ' ' + N.f.hilos), x[1]) })
      ;(c.cores || []).forEach(function (x) { n('cpu', 'nu' + x[0], N.f.nucleo + ' #' + x[0], x[1]); n('cpu', 'nm' + x[0], N.f.nucleo + ' #' + x[0] + ' · MHz', x[2], 'MHz') })
      ;(c.bandwidth || []).forEach(function (x) { n('ram', 'bw' + x[0], N.f.ancho + ' ' + (x[0] === 1 ? N.f.hilo1 : x[0] + ' ' + N.f.hilos), x[1], 'GB/s') })
      ;(json(f.settings) || []).forEach(function (a) { t('ajustes', 'a.' + a[0], nombreAjuste(a[0]), a[1]) })
    } else {
      n('cpu', 'c.uno', N.f.uno, f.cpu_single); n('cpu', 'c.todos', N.f.todos, f.cpu_multi)
      ;(json(f.cpu_tests) || []).forEach(function (x) {
        n('cpu', 'c.' + x.id + '.1', (N.pruebas[x.id] || x.id) + ' · ' + N.f.hilo1, x.single)
        n('cpu', 'c.' + x.id + '.n', (N.pruebas[x.id] || x.id) + ' · ' + N.f.hilosN, x.multi)
      })
      n('cpu', 'c.mhz1', N.f.mhz1, f.cpu_mhz_single, 'MHz'); n('cpu', 'c.mhzN', N.f.mhzN, f.cpu_mhz_multi, 'MHz')
      n('cpu', 'c.limite', N.f.limite, f.cpu_limit_pct, '%', true); n('cpu', 'c.temp', N.f.temp, f.cpu_temp_max, '°C', true); n('cpu', 'c.vatios', N.f.vatios, f.cpu_watts_max, 'W', true)
      n('ram', 'r.lect', N.f.lectura, f.ram_read, 'GB/s'); n('ram', 'r.escr', N.f.escritura, f.ram_write, 'GB/s'); n('ram', 'r.copia', N.f.copia, f.ram_copy, 'GB/s')
      n('ram', 'r.lat', N.f.latencia, f.ram_latency, 'ns', true)
      ;(json(f.ram_caches) || []).forEach(function (x) { n('ram', 'r.c' + x.kb, N.f.cache + ' ' + (x.kb >= 1024 ? x.kb / 1024 + ' MB' : x.kb + ' KB'), x.ns, 'ns', true) })
      n('gpu', 'g.fps', N.f.fps, f.gpu_fps, 'FPS'); n('gpu', 'g.fps1', N.f.fps1, f.gpu_fps_1low, 'FPS')
      n('gpu', 'g.mhz', N.f.mhz, f.gpu_mhz, 'MHz'); n('gpu', 'g.mhzm', N.f.mhzMem, f.gpu_mem_mhz, 'MHz')
      n('gpu', 'g.temp', N.f.temp, f.gpu_temp_max, '°C', true); n('gpu', 'g.vatios', N.f.vatios, f.gpu_watts_max, 'W', true)
      n('gpu', 'g.pct', N.f.consumoPct, f.gpu_power_pct, '%', true); n('gpu', 'g.uso', N.f.uso, f.gpu_busy_pct, '%')
      t('gpu', 'g.driver', N.f.driver, f.gpu_driver)
    }
    return g
  }

  var comparando = []
  var eligiendo = false
  var busqueda = ''
  var capa = null
  function abrir(f) { comparando = [f]; eligiendo = false; busqueda = ''; pintarCapa() }
  function cerrar() { comparando = []; if (capa) { capa.remove(); capa = null } document.removeEventListener('keydown', teclaCapa) }
  function teclaCapa(e) { if (e.key === 'Escape') cerrar() }
  var COLORES = ['#ffd23f', '#1de9d0', '#ff5fb8', '#b06bff']
  function decimales(v) { return Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2 }
  var nf = function (v) { return new Intl.NumberFormat(lang, { maximumFractionDigits: decimales(v) }).format(v) }

  function pintarCapa() {
    if (!comparando.length) return cerrar()
    var enLabC = estado.modo === 'lab'
    var cols = comparando.map(function (f) { return datosDe(f, enLabC) })
    var grupos = ['puntos', 'piezas', 'cpu', 'ram', 'gpu', 'ajustes']
    var colorG = { puntos: '#b06bff', piezas: '#8a93b2', cpu: '#ff9000', ram: '#3d9bff', gpu: '#2ee6a0', ajustes: '#ff5fb8' }
    var plantilla = 'minmax(9rem,1.2fr) repeat(' + cols.length + ', minmax(0,1fr))'
    var h = '<div class="hall-capa-caja cristal" role="dialog" aria-modal="true">' +
      '<div class="hall-capa-cabeza"><b>' + N.titulo + '</b><button type="button" class="hall-capa-x" data-cerrar aria-label="' + N.cerrar + '">✕</button></div>' +
      '<p class="hall-capa-ayuda">' + N.ayuda + '</p>'
    h += comparando.length < 4 ? '<button type="button" class="hall-capa-anadir" data-anadir>' + N.anadir + '</button>' : '<p class="hall-capa-ayuda">' + N.max + '</p>'
    if (eligiendo) {
      var usadas = comparando.map(function (f) { return f.position })
      var q = busqueda.trim().toLowerCase()
      var opciones = (enLabC ? lab : filas).filter(function (f) { return usadas.indexOf(f.position) < 0 })
        .filter(function (f) { return !q || ((f.nickname || '') + ' ' + f.cpu_model + ' ' + f.gpu_model).toLowerCase().indexOf(q) >= 0 })
        .sort(function (a, b) { return (b.total || 0) - (a.total || 0) })
      h += '<div class="hall-capa-elegir"><input type="search" data-buscar placeholder="' + esc(N.buscar) + '" value="' + esc(busqueda) + '"><div class="hall-capa-opciones">' +
        opciones.map(function (f) {
          return '<button type="button" data-elegir="' + f.position + '"><b>' + (f.nickname ? esc(f.nickname) : '<i>' + T.anonimo + '</i>') + '</b> <span>' + esc(corto(f.cpu_model)) + ' · ' + esc(corto(f.gpu_model)) +
            (f.old_version ? ' · ' + T.antiguas : '') + '</span><em>' + (f.total != null ? num.format(Math.round(f.total)) : '—') + '</em></button>'
        }).join('') + '</div></div>'
    }
    h += '<div class="hall-capa-tabla"><div class="hall-capa-rejilla" style="grid-template-columns:' + plantilla + '"><span></span>' +
      comparando.map(function (f, i) {
        return '<div class="hall-capa-col" style="--c:' + COLORES[i] + '"><b>' + (f.nickname ? esc(f.nickname) : '<i>' + T.anonimo + '</i>') + '</b>' +
          (comparando.length > 1 ? '<button type="button" data-quitar-col="' + i + '" title="' + N.quitar + '">✕</button>' : '') +
          (f.creator ? '<span class="insignia">★ ' + T.creador + '</span>' : '') + '</div>'
      }).join('')
    grupos.forEach(function (gr) {
      var claves = []
      cols.forEach(function (c) { c[gr].forEach(function (x) { if (claves.indexOf(x.k) < 0) claves.push(x.k) }) })
      if (!claves.length) return
      h += '<p class="hall-capa-grupo" style="color:' + colorG[gr] + '">' + N.g[gr] + '</p>'
      claves.forEach(function (k) {
        var celdas = cols.map(function (c) { return c[gr].filter(function (x) { return x.k === k })[0] })
        var una = celdas.filter(Boolean)[0]
        h += '<span class="hall-capa-nombre" title="' + esc(una.texto) + '">' + esc(una.texto) + '</span>'
        if (una.t != null) {
          var distintos = celdas.map(function (x) { return x ? x.t : '' }).filter(function (v, i, l) { return v && l.indexOf(v) === i }).length > 1
          h += celdas.map(function (x) { return '<span class="hall-capa-v' + (distintos ? ' distinto' : '') + '" title="' + esc(x ? x.t : '') + '">' + (x ? esc(x.t) : '—') + '</span>' }).join('')
        } else {
          var vals = celdas.map(function (x) { return x ? x.v : null })
          var nums = vals.filter(function (v) { return v != null })
          var mejor = nums.length > 1 && nums.some(function (v) { return v !== nums[0] }) ? (una.menos ? Math.min.apply(null, nums) : Math.max.apply(null, nums)) : null
          h += vals.map(function (v, i) {
            if (v == null) return '<span class="hall-capa-v vacio">—</span>'
            var dif = i > 0 && vals[0] ? (v - vals[0]) / vals[0] * 100 : null
            var col = dif == null || Math.abs(dif) < 1.5 ? '' : ((una.menos ? dif < 0 : dif > 0) ? ' sube' : ' baja')
            return '<span class="hall-capa-v' + (v === mejor ? ' mejor' : '') + '">' + nf(v) + (una.u ? ' <small>' + una.u + '</small>' : '') +
              (dif != null && Math.abs(dif) >= 0.05 ? ' <small class="dif' + col + '">' + (dif > 0 ? '+' : '') + nf(dif) + '%</small>' : '') + '</span>'
          }).join('')
        }
      })
    })
    h += '</div></div></div>'
    if (!capa) {
      capa = document.createElement('div')
      capa.className = 'hall-capa'
      document.body.appendChild(capa)
      document.addEventListener('keydown', teclaCapa)
      capa.addEventListener('mousedown', function (e) { if (e.target === capa) cerrar() })
    }
    capa.innerHTML = h
    capa.querySelector('[data-cerrar]').onclick = cerrar
    var an = capa.querySelector('[data-anadir]')
    if (an) an.onclick = function () { eligiendo = !eligiendo; pintarCapa(); var b = capa.querySelector('[data-buscar]'); if (b) b.focus() }
    var bu = capa.querySelector('[data-buscar]')
    if (bu) bu.oninput = function () { busqueda = bu.value; var pos = bu.selectionStart; pintarCapa(); var b2 = capa.querySelector('[data-buscar]'); b2.focus(); b2.setSelectionRange(pos, pos) }
    capa.querySelectorAll('[data-elegir]').forEach(function (b) {
      b.onclick = function () {
        var pos = Number(b.getAttribute('data-elegir'))
        var f = (estado.modo === 'lab' ? lab : filas).filter(function (x) { return x.position === pos })[0]
        if (f) { comparando.push(f); eligiendo = false; busqueda = ''; pintarCapa() }
      }
    })
    capa.querySelectorAll('[data-quitar-col]').forEach(function (b) { b.onclick = function () { comparando.splice(Number(b.getAttribute('data-quitar-col')), 1); pintarCapa() } })
  }
})()
