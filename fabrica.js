// Copia de src/fabrica.js de GameHub para el Hall of Fame de la web (filtro y etiqueta de OC). Si cambia allí, volver a
// copiarla (herramienta del chat de la web: hall.py). Expone window.FABRICA.ocDeFila(fila de lab_runs).
(function () {
// Datos de fábrica de procesadores y gráficas de sobremesa, para saber si una prueba de BenchHub lleva
// overclock (`ocDe`): lo que va por encima de lo que da la pieza de fábrica. Revisado a mano el 18-10-2026 (las
// especificaciones de AMD, Intel y NVIDIA). Los portátiles no se miran (casi nunca se puede tocar nada).
// Para añadir uno, una línea «Nombre como lo da Windows | dato | dato».
function normal(nombre, cpu) {
  let s = String(nombre).toLowerCase().replace(/\((r|tm)\)|®|™/g, ' ').replace(/@.*$/, '')
    .replace(/\b\d+(st|nd|rd|th) gen\b/g, ' ').replace(/core2/g, 'core 2').replace(/\b(cpu|processor)\b/g, ' ').replace(/[^a-z0-9]+/g, ' ')
  if (cpu) s = s.replace(/(\d)(k?)f\b/g, '$1$2')
  return ` ${s.trim()} `
}

// Procesador | MHz máximos de fábrica (boost/turbo con 1 núcleo) | TDP en W (AMD: el límite de consumo PPT de fábrica
// es el TDP × 1,35; con PBO se sube).
const PROCESADORES = `
AMD Ryzen 9 9950X3D | 5700 | 170
AMD Ryzen 9 9950X | 5700 | 170
AMD Ryzen 9 9900X3D | 5500 | 120
AMD Ryzen 9 9900X | 5600 | 120
AMD Ryzen 7 9850X3D | 5600 | 120
AMD Ryzen 7 9800X3D | 5200 | 120
AMD Ryzen 7 9700X | 5500 | 65
AMD Ryzen 5 9600X | 5400 | 65
AMD Ryzen 5 9600 | 5200 | 65
AMD Ryzen 9 7950X3D | 5700 | 120
AMD Ryzen 9 7950X | 5700 | 170
AMD Ryzen 9 7900X3D | 5600 | 120
AMD Ryzen 9 7900X | 5600 | 170
AMD Ryzen 9 7900 | 5400 | 65
AMD Ryzen 7 7800X3D | 5000 | 120
AMD Ryzen 7 7700X | 5400 | 105
AMD Ryzen 7 7700 | 5300 | 65
AMD Ryzen 5 7600X3D | 4700 | 65
AMD Ryzen 5 7600X | 5300 | 105
AMD Ryzen 5 7600 | 5100 | 65
AMD Ryzen 7 8700G | 5100 | 65
AMD Ryzen 5 8600G | 5000 | 65
AMD Ryzen 5 8500G | 5000 | 65
AMD Ryzen 9 5950X | 4900 | 105
AMD Ryzen 9 5900X | 4800 | 105
AMD Ryzen 9 5900XT | 4800 | 105
AMD Ryzen 7 5800X3D | 4500 | 105
AMD Ryzen 7 5800X | 4700 | 105
AMD Ryzen 7 5800XT | 4800 | 105
AMD Ryzen 7 5700X3D | 4100 | 105
AMD Ryzen 7 5700X | 4600 | 65
AMD Ryzen 7 5700G | 4600 | 65
AMD Ryzen 7 5700 | 4600 | 65
AMD Ryzen 5 5600X3D | 4400 | 105
AMD Ryzen 5 5600X | 4600 | 65
AMD Ryzen 5 5600 | 4400 | 65
AMD Ryzen 5 5600G | 4400 | 65
AMD Ryzen 5 5500 | 4200 | 65
AMD Ryzen 9 3950X | 4700 | 105
AMD Ryzen 9 3900X | 4600 | 105
AMD Ryzen 7 3800X | 4500 | 105
AMD Ryzen 7 3700X | 4400 | 65
AMD Ryzen 5 3600X | 4400 | 95
AMD Ryzen 5 3600 | 4200 | 65
AMD Ryzen 7 2700X | 4300 | 105
AMD Ryzen 5 2600X | 4200 | 95
AMD Ryzen 5 2600 | 3900 | 65
AMD Ryzen 5 1600X | 4100 | 95
AMD Ryzen 5 1600 | 3700 | 65
Intel Core Ultra 9 285K | 5700
Intel Core Ultra 7 265K | 5500
Intel Core Ultra 5 245K | 5200
Intel Core i9-14900KS | 6200
Intel Core i9-14900K | 6000
Intel Core i7-14700K | 5600
Intel Core i5-14600K | 5300
Intel Core i5-14400 | 4700
Intel Core i9-13900KS | 6000
Intel Core i9-13900K | 5800
Intel Core i7-13700K | 5400
Intel Core i5-13600K | 5100
Intel Core i5-13400 | 4600
Intel Core i9-12900KS | 5500
Intel Core i9-12900K | 5200
Intel Core i7-12700K | 5000
Intel Core i5-12600K | 4900
Intel Core i5-12400 | 4400
Intel Core i3-12100 | 4300
Intel Core i9-11900K | 5300
Intel Core i7-11700K | 5000
Intel Core i5-11600K | 4900
Intel Core i5-11400 | 4400
Intel Core i9-10900K | 5300
Intel Core i7-10700K | 5100
Intel Core i5-10600K | 4800
Intel Core i5-10400 | 4300
Intel Core i9-9900K | 5000
Intel Core i7-9700K | 4900
Intel Core i5-9600K | 4600
Intel Core i7-8700K | 4700
`

// Gráfica | velocidad de su memoria de fábrica (Gbps).
const GRAFICAS = `
NVIDIA GeForce RTX 5090 | 28
NVIDIA GeForce RTX 5080 | 30
NVIDIA GeForce RTX 5070 Ti | 28
NVIDIA GeForce RTX 5070 | 28
NVIDIA GeForce RTX 5060 Ti | 28
NVIDIA GeForce RTX 5060 | 28
NVIDIA GeForce RTX 5050 | 20
NVIDIA GeForce RTX 4090 | 21
NVIDIA GeForce RTX 4080 SUPER | 23
NVIDIA GeForce RTX 4080 | 22.4
NVIDIA GeForce RTX 4070 Ti SUPER | 21
NVIDIA GeForce RTX 4070 Ti | 21
NVIDIA GeForce RTX 4070 SUPER | 21
NVIDIA GeForce RTX 4070 | 21
NVIDIA GeForce RTX 4060 Ti | 18
NVIDIA GeForce RTX 4060 | 17
NVIDIA GeForce RTX 3090 Ti | 21
NVIDIA GeForce RTX 3090 | 19.5
NVIDIA GeForce RTX 3080 Ti | 19
NVIDIA GeForce RTX 3080 | 19
NVIDIA GeForce RTX 3070 Ti | 19
NVIDIA GeForce RTX 3070 | 14
NVIDIA GeForce RTX 3060 Ti | 14
NVIDIA GeForce RTX 3060 | 15
NVIDIA GeForce RTX 3050 | 14
NVIDIA GeForce RTX 2080 Ti | 14
NVIDIA GeForce RTX 2080 SUPER | 15.5
NVIDIA GeForce RTX 2080 | 14
NVIDIA GeForce RTX 2070 SUPER | 14
NVIDIA GeForce RTX 2070 | 14
NVIDIA GeForce RTX 2060 SUPER | 14
NVIDIA GeForce RTX 2060 | 14
NVIDIA GeForce GTX 1660 SUPER | 14
NVIDIA GeForce GTX 1660 Ti | 12
NVIDIA GeForce GTX 1660 | 8
NVIDIA GeForce GTX 1080 Ti | 11
NVIDIA GeForce GTX 1080 | 10
NVIDIA GeForce GTX 1070 | 8
NVIDIA GeForce GTX 1060 | 8
AMD Radeon RX 9070 XT | 20
AMD Radeon RX 9070 | 20
AMD Radeon RX 9060 XT | 20
AMD Radeon RX 7900 XTX | 20
AMD Radeon RX 7900 XT | 20
AMD Radeon RX 7900 GRE | 18
AMD Radeon RX 7800 XT | 19.5
AMD Radeon RX 7700 XT | 18
AMD Radeon RX 7600 XT | 18
AMD Radeon RX 7600 | 18
AMD Radeon RX 6950 XT | 18
AMD Radeon RX 6900 XT | 16
AMD Radeon RX 6800 XT | 16
AMD Radeon RX 6800 | 16
AMD Radeon RX 6750 XT | 18
AMD Radeon RX 6700 XT | 16
AMD Radeon RX 6700 | 16
AMD Radeon RX 6650 XT | 17.5
AMD Radeon RX 6600 XT | 16
AMD Radeon RX 6600 | 14
AMD Radeon RX 6500 XT | 18
AMD Radeon RX 5700 XT | 14
AMD Radeon RX 5700 | 14
AMD Radeon RX 5600 XT | 14
AMD Radeon RX 5500 XT | 14
Radeon RX 590 | 8
Radeon RX 580 | 8
Radeon RX 570 | 7
`

// Lista «nombre | datos» → función nombre → [datos] (gana el nombre más largo que encaje: «4070 Ti SUPER» antes que
// «4070 Ti»). Las de portátil no encajan con ninguna.
function tabla(texto, cpu) {
  let claves = null
  return (nombre) => {
    if (!nombre) return null
    if (!claves) {
      claves = texto.trim().split('\n').map((l) => {
        const [n, ...d] = l.split('|').map((x) => x.trim())
        return [normal(n, cpu), d.map(Number)]
      })
    }
    const n = normal(nombre, cpu)
    if (n.includes(' laptop ')) return null
    let mejor = null
    for (const [k, d] of claves) if (n.includes(k) && (!mejor || k.length > mejor[0].length)) mejor = [k, d]
    return mejor ? mejor[1] : null
  }
}
const procesador = tabla(PROCESADORES, true)
const grafica = tabla(GRAFICAS, false)

// MHz máximos y TDP de fábrica de un procesador ({ mhz, tdp }; tdp solo en AMD), o null si no está en la lista.
function procesadorDeFabrica(modelo) {
  const d = procesador(modelo)
  return d ? { mhz: d[0], tdp: d[1] || null } : null
}

// Gbps de la memoria de una gráfica de fábrica, o null.
const vramDeFabrica = (modelo) => grafica(modelo)?.[0] ?? null

// Velocidad de la VRAM en Gbps (por pin), la que se puede comparar entre marcas, a partir de los MHz que da el driver:
// NVIDIA da la mitad (GDDR5/6/6X/7: 10501 MHz = 21 Gbps); AMD, el reloj de la memoria: GDDR6 (RX 5000 en adelante) × 8
// (2505 MHz = 20 Gbps), GDDR5 (RX 400/500, R9/R7) × 4 y HBM (Vega, Radeon VII, Fury) × 2. Intel y las integradas: no se sabe.
function gbpsVram(mhz, gpu) {
  const m = Number(mhz)
  if (!(m > 0)) return null
  const n = (gpu || '').toLowerCase()
  const k = /nvidia|geforce|quadro/.test(n) ? 2 : /vega|radeon vii|fury/.test(n) ? 2 : /\brx ?\d{4}/.test(n) ? 8 : /\brx ?\d{3}\b|\br[79] \d/.test(n) ? 4 : null
  const g = k && (m * k) / 1000
  return g && g >= 1 && g <= 40 ? g : null
}

// CL de fábrica del modelo de los módulos (como `cl_de_modelo` de hw.rs): «KF560C30-32» → 30, «F4-3600C16D-32GTZN» → 16.
function clDeModelo(modelo) {
  const m = String(modelo || '').toUpperCase()
  for (let i = 1; i < m.length; i++) {
    if (m[i] !== 'C' || !/[0-9HL]/.test(m[i - 1])) continue
    const d = m.slice(i + 1).match(/^\d+/)?.[0]
    if (d?.length === 2 && +d >= 9 && +d <= 60) return +d
  }
  return null
}

const n = (x) => (typeof x === 'number' ? x : parseFloat(x))
const r1 = (x) => Math.round(x * 10) / 10

// Lo que lleva overclock en una prueba: { cpu: [...], ram: [...], gpu: [...], hay } con un motivo por cosa ({ id, datos }:
// el texto lo pone `textoOc`). Lo que no se puede leer (Curve Optimizer, undervolt) no sale.
// p = { portatil, cpu, mhz1 (MHz con 1 núcleo medidos), ppt (límite PPT en W, sensores avanzados), gpu, vramMhz,
//       ramMts, ramCl (a los que va), ramMtsFabrica, ramClFabrica (del modelo de los módulos) }
function ocDe(p) {
  const oc = { cpu: [], ram: [], gpu: [] }
  if (!p || p.portatil) return { ...oc, hay: false }
  const cpu = procesadorDeFabrica(p.cpu)
  // MHz con 1 núcleo por encima del máximo de fábrica (un 1,5 % de margen): OC manual o «boost override» de PBO.
  if (cpu && n(p.mhz1) > cpu.mhz * 1.015) oc.cpu.push({ id: 'mhz', mhz: Math.round(n(p.mhz1)), fabrica: cpu.mhz })
  // AMD: el límite de consumo (PPT) más de un 10 % por encima del de fábrica: PBO.
  if (cpu?.tdp && n(p.ppt) > cpu.tdp * 1.35 * 1.1) oc.cpu.push({ id: 'pbo', w: Math.round(n(p.ppt)), fabrica: Math.round(cpu.tdp * 1.35) })
  // RAM más rápida que la de su perfil de fábrica (XMP/EXPO), o a la misma con un CL más bajo.
  const [mts, cl, fm, fcl] = [n(p.ramMts), n(p.ramCl), n(p.ramMtsFabrica), n(p.ramClFabrica)]
  if (fm > 0 && mts > 0 && (mts > fm + 150 || (cl > 0 && fcl > 0 && cl < fcl && mts >= fm - 50))) {
    oc.ram.push({ id: 'ram', mts, cl: cl > 0 ? cl : null, fabrica: fm, cl_fabrica: fcl > 0 ? fcl : null })
  }
  // La memoria de la gráfica más de un 2 % por encima de la de fábrica (en Gbps, como la da el driver en la prueba).
  const g = gbpsVram(n(p.vramMhz), p.gpu), gf = vramDeFabrica(p.gpu)
  if (g && gf && g > gf * 1.02) oc.gpu.push({ id: 'vram', gbps: r1(g), fabrica: gf })
  return { ...oc, hay: oc.cpu.length + oc.ram.length + oc.gpu.length > 0 }
}

// WHEA: errores de hardware que Windows corrigió durante la prueba (null = no se miró: pruebas de antes de la 26.10.2.beta32).
// Una fila del Hall of Fame (en sus avisos o en sus ajustes) o una prueba tuya (sus avisos).
function wheaDe(f) {
  const w = (f?.warnings || f?.avisos || []).find((a) => a.id === 'whea')
  if (w) return n(w.n) || 0
  const s = (f?.settings || f?.ajustes || []).find(([k]) => k === 'WHEA')
  return s ? n(s[1]) || 0 : null
}

// Una prueba de BenchHub con la forma del comparador (`entradaMia` / `entradaFila`): sus datos y sus ajustes apuntados.
const ocDeEntrada = (e) => {
  const a = e?.ajustes || {}
  return ocDe({ portatil: e?.piezas?.portatil, cpu: e?.piezas?.cpu, mhz1: e?.datos?.['cpu.mhz_1'], ppt: a.PPT, gpu: e?.piezas?.gpu, vramMhz: a['VRAM MHz'],
    ramMts: a.RAM, ramCl: a['tCL-tRCD-tRP-tRAS'], ramMtsFabrica: a['RAM de fábrica'], ramClFabrica: clDeModelo(a['Módulos']) })
}

function json(t) { if (t == null || typeof t !== 'string') return t; try { return JSON.parse(t) } catch (e) { return null } }
// Una fila de lab_runs de la BD pública, como `entradaFila` de GameHub, y su OC.
function ocDeFila(f) {
  var a = {}; (json(f.settings) || []).forEach(function (x) { a[x[0]] = x[1] })
  return ocDeEntrada({ piezas: { portatil: !!f.laptop, cpu: f.cpu_model, gpu: f.gpu_model }, datos: json(f.data) || {}, ajustes: a })
}
window.FABRICA = { ocDeFila: ocDeFila }
})()
