// Utilidades de la interfaz.

export const COLORES = {
  naranja: '#ff9000', rojo: '#ff4d5e', verde: '#2ee6a0', azul: '#3d9bff',
  morado: '#b06bff', turquesa: '#1de9d0', amarillo: '#ffd23f', rosa: '#ff5fb8', gris: '#8a93b2',
}

// Color de cada tienda (chip de la columna "Tienda").
const COLOR_TIENDA = [
  [/steam/i, '#3d9bff'], [/epic/i, '#c9ccd6'], [/gog/i, '#b06bff'], [/ubisoft/i, '#1de9d0'],
  [/battle|blizzard/i, '#4fc3ff'], [/ea\b|origin/i, '#ff4d5e'], [/amazon/i, '#ffd23f'],
  [/xbox|microsoft/i, '#2ee6a0'], [/manual/i, '#ff9000'], [/desinstal/i, '#8a93b2'], [/sin launcher/i, '#ff5fb8'],
]
export function colorTienda(tienda) {
  for (const [re, color] of COLOR_TIENDA) if (re.test(tienda || '')) return color
  return '#8a93b2'
}

// "📂 STEAM (ruta prevista)" -> { icono: '📂', nombre: 'Steam', extra: 'ruta prevista' }
export function partirCabecera(texto) {
  let t = String(texto || '').trim()
  let icono = ''
  const m = t.match(/^(\p{Extended_Pictographic}[\u{FE0F}\u{200D}\p{Extended_Pictographic}\u{E0020}-\u{E007F}]*)\s*/u)
  if (m) { icono = m[1]; t = t.slice(m[0].length) }
  let extra = ''
  const p = t.match(/\s*\(([^)]*)\)\s*$/)
  if (p) { extra = p[1]; t = t.slice(0, p.index) }
  return { icono, nombre: capitalizar(t), extra }
}

export function capitalizar(t) {
  return String(t || '').toLowerCase().split(/\s+/).map((p, i) => {
    if (/^(ea|gog|pc|drm|bd|ps\d?)$/i.test(p)) return p.toUpperCase()
    if (i > 0 && /^(de|del|la|el|en|y|a|sin|con|para|por)$/.test(p)) return p
    return p.charAt(0).toUpperCase() + p.slice(1)
  }).join(' ')
}

export function formatearBytes(n) {
  n = Number(n) || 0
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (Math.abs(n) >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return i === 0 ? `${Math.round(n)} B` : `${n.toFixed(n >= 100 ? 0 : 1).replace('.', ',')} ${u[i]}`
}

export function fechaRelativa(ts) {
  if (!ts) return ''
  const fecha = new Date(ts * 1000)
  const hoy = new Date()
  const dias = Math.round((new Date(hoy.toDateString()) - new Date(fecha.toDateString())) / 86400000)
  const hora = fecha.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
  if (dias === 0) return `hoy ${hora}`
  if (dias === 1) return `ayer ${hora}`
  if (dias < 7) return `hace ${dias} días`
  return fecha.toLocaleDateString('es-ES')
}

// Todos los juegos del árbol, en orden.
export function juegosDe(arbol) {
  const salida = []
  const recorrer = (nodos) => {
    for (const n of nodos || []) {
      if (n.tipo === 'juego') salida.push(n)
      else recorrer(n.hijos)
    }
  }
  recorrer(arbol)
  return salida
}

export const FILTROS = [
  { id: 'Todos', texto: 'Todos', color: COLORES.naranja },
  { id: 'Con copia local', texto: 'Con copia', color: COLORES.verde },
  { id: 'Sin copia local', texto: 'Sin copia', color: COLORES.rojo },
  { id: 'En la nube', texto: 'En la nube', color: COLORES.azul },
  { id: 'Sin subir a la nube', texto: 'Sin subir', color: COLORES.morado },
]

export function pasaFiltro(juego, texto, modo) {
  if (texto && !juego.nombre.toLowerCase().includes(texto)) return false
  switch (modo) {
    case 'Con copia local': return juego.local > 0
    case 'Sin copia local': return juego.local === 0 && juego.respaldable
    case 'En la nube': return juego.nube > 0
    case 'Sin subir a la nube': return juego.local > 0 && juego.nube === 0
    default: return true
  }
}

export function claveOrden(juego, columna) {
  switch (columna) {
    case 'nombre': return juego.nombre.toLocaleLowerCase('es')
    case 'local': case 'nube': return juego[columna]
    case 'tamano': return juego.tamano_bytes
    case 'ultimo': return juego.ultimo_ts
    case 'tienda': return (juego.tienda || '').toLowerCase()
    default: return 0
  }
}

// Quita emojis sueltos del principio de un texto de estado del motor.
export function limpiarEstado(texto) {
  return String(texto || '').replace(/^[\p{Extended_Pictographic}\u{FE0F}\s]+/u, '').trim()
}

export function colorEstado(color) {
  const mapa = {
    '#2ecc71': COLORES.verde, '#27ae60': COLORES.verde, '#e74c3c': COLORES.rojo, '#c0392b': COLORES.rojo,
    '#3498db': COLORES.azul, '#f1c40f': COLORES.amarillo, '#f39c12': COLORES.naranja, '#e67e22': COLORES.naranja,
    '#95a5a6': COLORES.gris, '#bdc3c7': '#aeb6cf', white: '#e8ecf6', '#ecf0f1': '#e8ecf6', '#1abc9c': COLORES.turquesa,
  }
  return mapa[String(color || '').toLowerCase()] || color || COLORES.gris
}
