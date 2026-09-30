// API simulada para ver y diseñar la interfaz en un navegador normal
// (npm run dev). No toca nada del disco: solo imita las respuestas de Python.

const JUEGOS = {
  '🎮 STEAM': [
    ['Elden Ring', 2, 1, '48.2 MB', 1], ['Cyberpunk 2077', 3, 2, '112.9 MB', 0], ['Hades II', 1, 0, '3.1 MB', 2],
    ['Baldur\'s Gate 3', 5, 3, '1.2 GB', 1], ['Stardew Valley', 1, 1, '2.4 MB', 6], ['Hollow Knight', 0, 0, '1.1 MB', null],
    ['Red Dead Redemption 2', 2, 0, '28.4 MB', 12], ['The Witcher 3: Wild Hunt', 4, 4, '310.0 MB', 3],
    ['Sekiro: Shadows Die Twice', 0, 0, '9.8 MB', null], ['Terraria', 1, 1, '15.2 MB', 30],
  ],
  '🟪 EPIC GAMES': [
    ['Alan Wake 2', 1, 0, '6.3 MB', 4], ['Hogwarts Legacy', 0, 0, '41.0 MB', null], ['Death Stranding', 2, 2, '12.6 MB', 9],
  ],
  '🟣 GOG': [['Disco Elysium', 1, 1, '188.0 MB', 20], ['Cuphead', 0, 0, '0.4 MB', null]],
  '🔵 UBISOFT CONNECT': [['Assassin\'s Creed Valhalla', 1, 0, '22.0 MB', 45]],
  '➕ CARPETAS AÑADIDAS MANUALMENTE': [['Mi emulador PS2', 1, 0, '256.0 MB', 2]],
}

const TIENDAS = {
  '🎮 STEAM': 'Steam', '🟪 EPIC GAMES': 'Epic Games', '🟣 GOG': 'GOG',
  '🔵 UBISOFT CONNECT': 'Ubisoft Connect', '➕ CARPETAS AÑADIDAS MANUALMENTE': 'Manual',
}

let seleccion = new Set()
const historialRecursos = []
let rev = 1
const cerrados = new Set(['═══ 🌐 JUEGOS 100% ONLINE (el progreso se guarda en el servidor) ═══'])
const colaEventos = []
let esperando = null
let nubeConectada = true
let escaneando = false
let tarea = ''

function emitir(evento) {
  colaEventos.push(evento)
  if (esperando) { const r = esperando; esperando = null; r() }
}

function construirArbol() {
  const arbol = []
  const ahora = Date.now() / 1000
  for (const [grupo, juegos] of Object.entries(JUEGOS)) {
    const clave = `--- ${grupo} ---`
    arbol.push({
      tipo: 'grupo', texto: grupo, clave,
      hijos: juegos.map(([nombre, local, nube, tamano, dias]) => {
        const ts = dias === null ? 0 : ahora - dias * 86400 - 3600 * 3
        const id = `${nombre} (${tamano})`
        return {
          tipo: 'juego', id, nombre, tienda: TIENDAS[grupo],
          local, nube, tamano, tamano_bytes: parseFloat(tamano) * (tamano.includes('GB') ? 1024 ** 3 : 1024 ** 2),
          ultimo: dias === null ? '' : dias === 0 ? 'hoy 14:32' : dias === 1 ? 'ayer 21:10' : dias < 7 ? `hace ${dias} días` : '12/09/2026',
          ultimo_ts: ts, detalle: grupo.includes('MANUAL') ? 'D:/Emuladores/PCSX2/memcards' : '%APPDATA%/…/Saves',
          respaldable: true, manual: grupo.includes('MANUAL'),
        }
      }),
    })
  }
  arbol.push({
    tipo: 'seccion', texto: '🌐 JUEGOS 100% ONLINE (el progreso se guarda en el servidor)',
    clave: '═══ 🌐 JUEGOS 100% ONLINE (el progreso se guarda en el servidor) ═══',
    hijos: [{
      tipo: 'grupo', texto: '🎮 STEAM (online)', clave: '--- 🎮 STEAM (online) ---',
      hijos: ['Counter-Strike 2', 'Dota 2', 'Apex Legends'].map((n) => ({
        tipo: 'juego', id: n, nombre: n, tienda: 'Steam', local: 0, nube: 0, tamano: '', tamano_bytes: 0,
        ultimo: '', ultimo_ts: 0, detalle: 'progreso en el servidor', respaldable: false, manual: false,
      })),
    }],
  })
  return arbol
}

export function crearApiSimulada() {
  setTimeout(() => emitir({ tipo: 'listo' }), 300)
  if (new URLSearchParams(window.location.search).has('bienvenida')) setTimeout(() => emitir({
    tipo: 'dialogo', id: 'b1', clase: 'bienvenida', titulo: 'Bienvenido', necesita_ruta: true,
    ruta_predeterminada: 'C:/Users/Demo/Desktop/Arlequin Backups', version: '2.0.0-beta.3' }), 200)
  if (new URLSearchParams(window.location.search).get('demo') !== 'limpia') setTimeout(() => emitir({
    tipo: 'toast', titulo: 'Modo demostración',
    texto: 'Estás viendo la interfaz en un navegador con datos de ejemplo.', error: false,
  }), 900)
  return {
    iniciar: async () => ({ version: '2.0.0-beta.1', version_motor: '1.1.9', listo: true,
      filtros: ['Todos', 'Con copia local', 'Sin copia local', 'En la nube', 'Sin subir a la nube'] }),
    esperar_eventos: (timeout) => new Promise((resolver) => {
      if (colaEventos.length) return resolver(colaEventos.splice(0))
      esperando = () => resolver(colaEventos.splice(0))
      setTimeout(() => { if (esperando) { esperando = null; resolver(colaEventos.splice(0)) } }, timeout * 1000)
    }),
    responder: async (id, valor) => { console.log('[simulada] respuesta', id, valor); return true },
    estado: async () => ({
      textos: {
        update_status: { texto: '✓ ASH 2.0.0-beta.1', color: '#2ecc71' },
        db_stats: { texto: 'BD: 21.482 juegos', color: '#95a5a6' },
        db_status: { texto: '✓ Base de datos al día', color: '#2ecc71' },
        partidas: { texto: 'Partidas 18', color: 'white' },
        launchers: { texto: 'instalados → Steam 42 · Epic 11 · GOG 4 · Ubisoft 2', color: '#bdc3c7' },
        ruta: { texto: 'Guardando en: C:/Users/Demo/Desktop/Arlequin Backups', color: '#bdc3c7' },
        scan: { texto: escaneando ? '⏳ Escaneando...' : '🔍 Escanear', color: 'white' },
      },
      escaneando, ocupado: !!tarea, tarea, rev,
      ruta_backups: 'C:/Users/Demo/Desktop/Arlequin Backups',
      disco: { unidad: 'C:', total: 512e9, libre: 138e9, usado: 374e9 },
      nube: {
        conectada: nubeConectada, clave: 'google', nombre: nubeConectada ? 'Google Drive' : '', color: '#1fa463',
        cuenta: 'demo@gmail.com', ultima_subida: '29/09/2026 22:14', espacio: '3,2 GB usados de 15 GB',
        auto: true, subiendo: false, descargando: false,
        proveedores: [
          { clave: 'google', nombre: 'Google Drive', color: '#1fa463', configurado: true },
          { clave: 'onedrive', nombre: 'OneDrive', color: '#28a8ea', configurado: true },
          { clave: 'dropbox', nombre: 'Dropbox', color: '#0061fe', configurado: true },
        ],
      },
      bd_total: 21482, ultimo_escaneo_s: 3.4, version: '2.0.0-beta.1', version_motor: '1.1.9', ocultos: 3, manuales: 1,
    }),
    tabla: async () => ({ rev, arbol: construirArbol(), cerrados: [...cerrados], seleccion: [...seleccion] }),
    plegar: async (clave, cerrado) => { cerrado ? cerrados.add(clave) : cerrados.delete(clave); return true },
    escanear: async () => {
      escaneando = true; tarea = 'Escaneando juegos'; emitir({ tipo: 'estado' })
      setTimeout(() => { escaneando = false; tarea = ''; rev++; emitir({ tipo: 'estado' }); emitir({ tipo: 'tabla', rev }) }, 3500)
      return true
    },
    actualizar_todo: async () => {
      emitir({ tipo: 'dialogo', id: 'x1', clase: 'info', titulo: 'Actualizar',
        mensaje: 'Se han comprobado el programa, la base de datos y la nube.\n\nPrograma: actualizado\nBase de datos: 21.482 juegos verificados\nNube: 34 copias verificadas' })
      return true
    },
    respaldar: async (ids) => {
      tarea = `Respaldando ${ids.length} juegos`; emitir({ tipo: 'estado' })
      setTimeout(() => {
        tarea = ''; emitir({ tipo: 'estado' })
        emitir({ tipo: 'dialogo', id: 'x2', clase: 'info', titulo: 'Operación completada', mensaje: `¡Backup completado!\n\nJuegos correctos: ${ids.length}/${ids.length}` })
      }, 1800)
      return true
    },
    restaurar: async () => {
      emitir({ tipo: 'dialogo', id: 'x3', clase: 'elegir_backup', titulo: 'Varios backups encontrados', juego: 'Elden Ring',
        reciente: 'b', opciones: [
          { ts: 1, etiqueta: '🟢 Copia actual (29/09/2026 14:32)', ruta: 'b' },
          { ts: 1, etiqueta: '🗓️ Copia del 20/09/2026 10:02', ruta: 'c' },
          { ts: 1, etiqueta: '↩️ Antes de restaurar (18/09/2026 19:40)', ruta: 'd' },
        ] })
      return true
    },
    ocultar: async (ids) => {
      emitir({ tipo: 'dialogo', id: 'x4', clase: 'sino', titulo: 'Ocultar', mensaje: `¿Quieres ocultar los ${ids.length} juegos seleccionados de la lista?` })
      return true
    },
    anadir_carpeta: async () => {
      emitir({ tipo: 'dialogo', id: 'x5', clase: 'texto', titulo: 'Nombre del juego', mensaje: '¿Qué nombre quieres darle a este juego en la lista?', valor: 'Mi juego' })
      return true
    },
    quitar_manual: async () => true,
    subir_a_nube: async () => true,
    verificar_copia: async () => true,
    verificar_todas: async () => true,
    diagnostico: async () => {
      emitir({ tipo: 'texto', titulo: 'Diagnóstico', texto: '🩺 DIAGNÓSTICO: Elden Ring\n\nDetectado en Steam (appid 1245620)\nRuta de guardado: %APPDATA%/EldenRing/76561198000000000\n  ✓ existe · 48.2 MB\nBackup: C:/Users/Demo/Desktop/Arlequin Backups/Elden Ring\n  ✓ 2 copias locales\n' })
      return true
    },
    estadisticas_bd: async () => { emitir({ tipo: 'texto', titulo: 'Estadísticas BD', texto: '📊 ESTADÍSTICAS DE ARLEQUIN GAME DB\n\nJuegos únicos en la base de datos: 21.482\n  Con ruta de guardado conocida: 17.903\n\nJUEGOS POR PLATAFORMA\n  Steam: 18.211\n  GOG: 3.120\n  Epic: 1.044' }); return true },
    instrucciones: async () => { emitir({ tipo: 'texto', titulo: 'Instrucciones de uso', texto: '📘 INSTRUCCIONES DE USO\n\n1. ESCANEAR\nASH detecta los juegos instalados…' }); return true },
    opciones: async () => { emitir({ tipo: 'abrir', panel: 'opciones' }); return true },
    opciones_cargar: async () => ({
      iniciar_windows: true, iniciar_minimizado: false, minimizar_en_bandeja: true, comprobar_actualizaciones: true,
      avisos_automaticos: 'Solo errores', mostrar_sin_datos: true, mostrar_previstos: true, mostrar_online: false,
      hash_solo_idle: false, hash_idle_min: 5, local_periodico: true, local_valor: 1, local_unidad: 'días',
      local_solo_idle: true, local_cierre: true, max_backups: 5, copia_antes_restaurar: true, verificacion_semanal: false,
      patrones_exclusion: '*.log; ShaderCache', nube_periodica: true, nube_valor: 7, nube_unidad: 'días', nube_cierre: false,
      max_copias_nube: 5, limite_subida: 0, no_red_medida: true, compresion: 'Rápido', anti_corrupcion: true,
      anti_corrupcion_pct: 30, obs_pause: false,
      juegos: Object.values(JUEGOS).flat().map(([n, , , t]) => ({ id: `${n} (${t})`, nombre: n })),
      excluidos: { local_periodico: ['Terraria (15.2 MB)'], local_cierre: [], nube_periodico: ["Baldur's Gate 3 (1.2 GB)", 'Mi emulador PS2 (256.0 MB)'], nube_cierre: [] },
      avisos_opciones: ['Nunca', 'Solo errores', 'Siempre'], nube_conectada: nubeConectada,
      contribuir: false, contribuir_estado: {},
    }),
    opciones_guardar: async () => ({ ok: true }),
    instrucciones_avanzadas: async () => true,
    contribuir_vista_previa: async () => `RUTAS APRENDIDAS (2)
  • Rust · Steam 252490
      <home>/AppData/LocalLow/Facepunch Studios LTD/Rust   [candidata]
  • Peak · Steam 3527290
      <home>/AppData/LocalLow/LandCrab/PEAK   [candidata]`,
    opciones_clasicas: async () => true,
    abrir_carpeta_backups: async () => true,
    cambiar_carpeta_backups: async () => true,
    abrir_carpeta_save: async () => true,
    abrir_carpeta_backup: async () => true,
    abrir_ruta: async () => true,
    abrir_enlace: async () => true,
    abrir_log: async () => true,
    detalles: async (id) => {
      const juego = construirArbol().flatMap((g) => g.hijos.flatMap((h) => (h.tipo === 'grupo' ? h.hijos : [h]))).find((j) => j.id === id)
      if (!juego) return null
      return {
        ...juego,
        rutas: [{ ruta: `C:/Users/Demo/AppData/Roaming/${juego.nombre}/Saves`, existe: true, tamano: juego.tamano, modificado: '29/09/2026 14:30' }],
        carpeta_backup: `C:/Users/Demo/Desktop/Arlequin Backups/${juego.nombre}`,
        copias: [
          { ts: 1, etiqueta: '🟢 Copia actual (29/09/2026 14:32)', ruta: 'a' },
          { ts: 1, etiqueta: '🗓️ Copia del 20/09/2026 10:02', ruta: 'b' },
        ].slice(0, Math.max(1, juego.local)),
        copias_nube: Array.from({ length: juego.nube }, (_, i) => ({ fecha: `2${8 - i}/09/2026 22:1${i}`, tamano: juego.tamano })),
        evidencia: 'Steam appid 1245620 · coincidencia exacta', confianza: 'alta', instalacion: 'D:/SteamLibrary/steamapps/common/' + juego.nombre,
      }
    },
    ocultos_listar: async () => ['Wallpaper Engine', 'Steamworks Common Redistributables', 'SteamVR'],
    ocultos_mostrar: async () => true,
    sinlauncher_listar: async () => ['D:/Juegos DRM-free'],
    sinlauncher_anadir: async () => ['D:/Juegos DRM-free', 'E:/Portables'],
    sinlauncher_quitar: async () => [],
    reescanear: async () => true,
    nube_estado: async () => ({}),
    nube_conectar: async () => { nubeConectada = true; emitir({ tipo: 'estado' }); return true },
    nube_desconectar: async () => { nubeConectada = false; emitir({ tipo: 'estado' }); return true },
    nube_espacio: async () => '3,2 GB usados de 15 GB',
    nube_sincronizar: async () => new Promise((r) => setTimeout(() => r({ ok: true, texto: 'Sincronizado con Google Drive' }), 900)),
    nube_preparar: async () => true,
    nube_cerrar_panel: async () => true,
    nube_subir_todo: async () => true,
    nube_lista_descarga: async () => new Promise((r) => setTimeout(() => r({ ok: true, filas: [
      { idx: 0, juego: 'Elden Ring', fecha: '28/09/2026 22:14', size: 48e6, tamano: '45.8 MB', estado: 'igual', copias: [{ id: 'a', fecha: '28/09/2026 22:14', tamano: '45.8 MB' }] },
      { idx: 1, juego: 'Baldur\'s Gate 3', fecha: '27/09/2026 20:01', size: 1.2e9, tamano: '1.1 GB', estado: 'distinta', copias: [{ id: 'b', fecha: '27/09/2026 20:01', tamano: '1.1 GB' }, { id: 'c', fecha: '20/09/2026 18:00', tamano: '1.0 GB' }] },
      { idx: 2, juego: 'Persona 5 Royal', fecha: '02/09/2026 11:30', size: 9e6, tamano: '8.6 MB', estado: 'no_local', copias: [{ id: 'd', fecha: '02/09/2026 11:30', tamano: '8.6 MB' }] },
    ] }), 700)),
    nube_descargar: async () => {
      let f = 0
      const t = setInterval(() => {
        f += 0.1
        emitir({ tipo: 'descarga', activo: f < 1.05, juego: '(1/1) Persona 5 Royal', paso: 'Descargando…', fraccion: Math.min(1, f) })
        if (f >= 1.05) clearInterval(t)
      }, 400)
      return true
    },
    nube_cancelar_descarga: async () => true,
    ventana_minimizar: async () => true,
    ventana_maximizar: async () => true,
    ventana_cerrar: async () => true,
    ventana_bandeja: async () => true,
    recursos: async (completo) => {
      const ahora = Date.now() / 1000
      if (!historialRecursos.length || ahora - historialRecursos[historialRecursos.length - 1].t >= 0.9) {
        const k = historialRecursos.length
        historialRecursos.push({
          t: ahora, cpu: Math.max(0.1, 2 + 1.6 * Math.sin(k / 5) + Math.random() * 1.2),
          ram: 2.1e8 + Math.sin(k / 9) * 1.2e7 + Math.random() * 4e6,
          disco: k % 17 < 4 ? 2.4e7 * Math.random() : Math.random() * 3e4,
          red_subida: k % 23 < 5 ? 3e5 * Math.random() : 0, red_bajada: Math.random() * 2e3,
        })
        if (historialRecursos.length > 120) historialRecursos.shift()
      }
      const a = historialRecursos[historialRecursos.length - 1]
      return {
        actual: { ...a, grupos: {
          motor: { cpu: a.cpu * 0.4, ram: 8.2e7, disco: a.disco * 0.1, procesos: 1 },
          interfaz: { cpu: a.cpu * 0.6, ram: a.ram - 8.2e7, disco: 0, procesos: 5 },
          copias: { cpu: 0, ram: 0, disco: a.disco * 0.9, procesos: a.disco > 1e6 ? 1 : 0 } } },
        nucleos: 16, ram_total: 3.2e10, red_total: { enviados: 4.1e6, recibidos: 9.8e6 }, disponible: true,
        historial: completo ? historialRecursos : undefined,
      }
    },
  }
}
