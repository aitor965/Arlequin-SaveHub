// Puente con Python (pywebview). Fuera de la app (navegador normal, `npm run dev`)
// se usa una API simulada con datos de ejemplo para poder diseñar la interfaz.
import { crearApiSimulada } from './simulada.js'

let apiReal = null

function esperarPywebview() {
  return new Promise((resolver) => {
    let resuelto = false
    const listo = () => {
      if (!resuelto && window.pywebview?.api?.iniciar) { resuelto = true; resolver(window.pywebview.api) }
    }
    window.addEventListener('pywebviewready', listo)
    listo()
    // pywebview inyecta window.pywebview enseguida y la API un poco después.
    // Si en 1,5 s no hay ni rastro de pywebview, estamos en un navegador normal.
    const comprobar = () => {
      if (resuelto) return
      listo()
      if (resuelto) return
      if (!window.pywebview) { resuelto = true; resolver(null); return }
      setTimeout(comprobar, 100)
    }
    setTimeout(comprobar, 1500)
  })
}

// Solo en desarrollo: ?rpc=PUERTO usa el motor real arrancado con
// `python ash_web.py --pruebas PUERTO` en lugar de la API simulada.
function crearApiRpc(puerto) {
  return new Proxy({}, {
    get: (_, nombre) => async (...args) => {
      const r = await fetch(`http://127.0.0.1:${puerto}/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre, args }),
      })
      const datos = await r.json()
      if (!datos.ok) throw new Error(datos.error)
      return datos.r
    },
  })
}

let conexion = null
export function conectar() {
  const params = new URLSearchParams(window.location.search)
  const rpc = import.meta.env.DEV && params.get('rpc')
  // Solo en desarrollo: ?demo fuerza los datos de ejemplo (capturas para la web).
  if (!conexion && import.meta.env.DEV && params.has('demo')) {
    apiReal = crearApiSimulada()
    conexion = Promise.resolve({ simulada: params.get('demo') !== 'limpia' })
  }
  if (!conexion && rpc) {
    apiReal = crearApiRpc(rpc)
    conexion = Promise.resolve({ simulada: false })
  }
  if (!conexion) {
    conexion = esperarPywebview().then((api) => {
      apiReal = api || crearApiSimulada()
      return { simulada: !api }
    })
  }
  return conexion
}

// Llama a una función de Python. Nunca lanza: devuelve `defecto` si falla.
export async function llamar(nombre, ...args) {
  if (!apiReal) await conectar()
  try {
    const fn = apiReal[nombre]
    if (typeof fn !== 'function') throw new Error(`La API no tiene ${nombre}`)
    return await fn(...args)
  } catch (err) {
    console.error(`[ASH] ${nombre}:`, err)
    return undefined
  }
}
