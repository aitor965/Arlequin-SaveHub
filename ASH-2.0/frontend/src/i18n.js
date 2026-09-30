// Traducciones de la interfaz. El texto en español es la clave: t('Texto')
// devuelve su traducción al idioma activo (o el propio texto si falta).
// t('Hola {0}', nombre) sustituye {0}, {1}...
import en from './idiomas/en.js'

const TABLAS = { en }
let idioma = 'es'

export function setIdioma(nuevo) {
  idioma = nuevo === 'en' ? 'en' : 'es'
  document.documentElement.lang = idioma
}

export function getIdioma() {
  return idioma
}

export function t(texto, ...args) {
  let s = idioma === 'es' ? texto : (TABLAS[idioma]?.[texto] ?? texto)
  if (args.length) s = s.replace(/\{(\d+)\}/g, (m, n) => (args[n] ?? m))
  return s
}

// Cabeceras y textos que llegan del motor en español (grupos de la tabla,
// tiendas, detalle de cada juego): se traducen por partes.
const DETALLES = [
  [/^confianza alta$/i, 'confianza alta'], [/^confianza media$/i, 'confianza media'], [/^confianza baja$/i, 'confianza baja'],
]
export function tDetalle(texto) {
  if (idioma === 'es' || !texto) return texto
  return String(texto).split(' · ').map((parte) => {
    const p = parte.trim()
    const m = p.match(/^se creará en: (.*)$/)
    if (m) return t('se creará en: {0}', m[1])
    for (const [re, clave] of DETALLES) if (re.test(p)) return t(clave)
    return t(p)
  }).join(' · ')
}
