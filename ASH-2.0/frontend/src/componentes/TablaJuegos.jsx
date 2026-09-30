import { memo, useMemo, useRef } from 'react'
import { ChevronRight, ChevronDown, ChevronUp, HardDriveDownload, Cloud, Check, Ghost, SearchX } from 'lucide-react'
import { Chip } from './Basicos.jsx'
import { colorTienda, partirCabecera, pasaFiltro, claveOrden } from '../util.js'

const COLUMNAS = 'grid-cols-[40px_minmax(220px,1fr)_130px_78px_78px_96px_128px]'

// Recorre el árbol aplicando filtro y orden. Devuelve la lista de filas a
// pintar (cabeceras y juegos) y los juegos visibles en orden.
export function filasVisibles(arbol, { texto, modo, orden, cerrados }) {
  const filas = []
  const visibles = []
  const filtrando = !!texto || modo !== 'Todos'
  const pintar = (nodos, nivel) => {
    let juegos = nodos.filter((n) => n.tipo === 'juego')
    if (orden) {
      juegos = [...juegos].sort((a, b) => {
        const x = claveOrden(a, orden.col), y = claveOrden(b, orden.col)
        const r = x < y ? -1 : x > y ? 1 : 0
        return orden.desc ? -r : r
      })
    }
    const cola = juegos[Symbol.iterator]()
    let cuenta = 0
    for (const n of nodos) {
      if (n.tipo === 'juego') {
        const j = cola.next().value
        if (!pasaFiltro(j, texto, modo)) continue
        filas.push({ tipo: 'juego', juego: j, nivel })
        visibles.push(j)
        cuenta++
      } else {
        const abierto = filtrando || !cerrados.has(n.clave)
        const indice = filas.length
        filas.push({ tipo: n.tipo, nodo: n, nivel, abierto, cuenta: 0 })
        const antes = filas.length
        const guardadas = abierto ? null : { filas: filas.length, visibles: visibles.length }
        const dentro = pintar(n.hijos || [], nivel + 1)
        if (guardadas) {
          // Plegado: se cuentan sus juegos pero no se pintan.
          filas.length = guardadas.filas
          visibles.length = guardadas.visibles
        }
        if (dentro === 0 && (filtrando || !(n.hijos || []).length)) {
          filas.splice(indice, filas.length - indice)
          continue
        }
        filas[indice].cuenta = dentro
        cuenta += dentro
        void antes
      }
    }
    return cuenta
  }
  pintar(arbol || [], 0)
  return { filas, visibles }
}

function Cabecera({ col, texto, orden, setOrden, className = '' }) {
  const activo = orden?.col === col
  return (
    <button onClick={() => setOrden((o) => (o?.col === col ? (o.desc ? null : { col, desc: true }) : { col, desc: false }))}
      className={`flex items-center gap-1 text-[11px] font-bold tracking-[.1em] uppercase transition
        ${activo ? 'text-naranja' : 'text-tenue hover:text-white'} ${className}`}>
      {texto}
      {activo && (orden.desc ? <ChevronDown size={13} /> : <ChevronUp size={13} />)}
    </button>
  )
}

const FilaJuego = memo(function FilaJuego({ juego, marcado, enfocado, nivel, alClic, alDoble, alMenu }) {
  const color = colorTienda(juego.tienda)
  const off = !juego.respaldable
  return (
    <div
      onMouseDown={(e) => { if (e.button === 0) alClic(e, juego) }}
      onDoubleClick={() => alDoble(juego)}
      onContextMenu={(e) => { e.preventDefault(); alMenu(e, juego) }}
      className={`fila-juego grid ${COLUMNAS} items-center h-[46px] px-3 border-b border-white/[.04] cursor-pointer
        ${marcado ? 'marcada' : ''} ${enfocado ? 'enfocada' : ''}`}>
      <div className="flex justify-center">
        {juego.respaldable
          ? <span className={`casilla ${marcado ? 'on' : ''}`}>{marcado && <Check size={13} strokeWidth={3.5} className="text-black" />}</span>
          : <Ghost size={15} className="text-tenue/50" />}
      </div>
      <div className="min-w-0 pr-3" style={{ paddingLeft: Math.max(0, nivel - 1) * 10 }}>
        <div className={`truncate text-[14px] font-semibold ${off ? 'text-tenue' : 'text-white'}`}>
          {juego.nombre}
          {juego.manual && <span className="ml-2 align-middle"><Chip color="#ff9000">manual</Chip></span>}
        </div>
        {juego.detalle && <div className="truncate text-[11.5px] text-tenue/80 font-mono">{juego.detalle}</div>}
      </div>
      <div className="min-w-0">{juego.tienda && <Chip color={color} className="max-w-full truncate">{juego.tienda}</Chip>}</div>
      <div className="text-center">
        {juego.local > 0
          ? <span className="inline-flex items-center gap-1 text-[13px] font-bold text-verde"><HardDriveDownload size={14} />{juego.local}</span>
          : <span className="text-tenue/40">—</span>}
      </div>
      <div className="text-center">
        {juego.nube > 0
          ? <span className="inline-flex items-center gap-1 text-[13px] font-bold text-azul"><Cloud size={14} />{juego.nube}</span>
          : <span className="text-tenue/40">—</span>}
      </div>
      <div className="text-right pr-4 text-[13px] font-mono text-[#c9d0e6] tabular-nums">{juego.tamano}</div>
      <div className="text-[12.5px] text-[#aeb6cf] truncate">{juego.ultimo || <span className="text-tenue/40">—</span>}</div>
    </div>
  )
})

function FilaGrupo({ fila, alPlegar }) {
  const { icono, nombre, extra } = partirCabecera(fila.nodo.texto)
  const seccion = fila.tipo === 'seccion'
  const color = seccion ? '#1de9d0' : colorTienda(nombre)
  return (
    <button onClick={() => alPlegar(fila.nodo.clave, fila.abierto)}
      className={`w-full flex items-center gap-2.5 px-3 text-left transition sticky z-[1]
        ${seccion ? 'h-[40px] mt-2 bg-[#0b0e1d]/95 border-y border-turquesa/15' : 'h-[36px] bg-[#0d1122]/90 border-b border-white/[.05] hover:bg-white/[.04]'}`}
      style={{ top: 38 }}>
      <span className="text-tenue">{fila.abierto ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
      {icono && <span className="text-[15px]">{icono}</span>}
      <span className={`font-bold tracking-wide truncate ${seccion ? 'text-[12.5px] text-turquesa uppercase' : 'text-[13px]'}`}
        style={seccion ? undefined : { color }}>{nombre}</span>
      {extra && <span className="text-[11.5px] text-tenue truncate">· {extra}</span>}
      <span className="ml-1 rounded-full px-2 py-[1px] text-[11px] font-bold font-mono"
        style={{ background: `${color}1f`, color }}>{fila.cuenta}</span>
    </button>
  )
}

export default function TablaJuegos({
  filas, visibles, seleccion, setSeleccion, enfocado, setEnfocado, orden, setOrden,
  plegar, alDetalles, alMenu, escaneando, cargando, busqueda,
}) {
  const ultimoClic = useRef(null)
  const indicePorId = useMemo(() => new Map(visibles.map((j, i) => [j.id, i])), [visibles])

  const alClic = (e, juego) => {
    setEnfocado(juego.id)
    if (!juego.respaldable) return
    if (e.shiftKey && ultimoClic.current && indicePorId.has(ultimoClic.current)) {
      const a = indicePorId.get(ultimoClic.current), b = indicePorId.get(juego.id)
      const [ini, fin] = a < b ? [a, b] : [b, a]
      setSeleccion((s) => {
        const n = new Set(s)
        for (let i = ini; i <= fin; i++) if (visibles[i].respaldable) n.add(visibles[i].id)
        return n
      })
    } else {
      setSeleccion((s) => {
        const n = new Set(s)
        n.has(juego.id) ? n.delete(juego.id) : n.add(juego.id)
        return n
      })
    }
    ultimoClic.current = juego.id
  }
  const alDoble = (juego) => {
    // El primer clic del doble clic ya cambió la marca: se deja como estaba.
    if (juego.respaldable) setSeleccion((s) => { const n = new Set(s); n.has(juego.id) ? n.delete(juego.id) : n.add(juego.id); return n })
    alDetalles(juego.id)
  }
  const alMenuFila = (e, juego) => {
    setEnfocado(juego.id)
    if (juego.respaldable && !seleccion.has(juego.id)) setSeleccion(new Set([juego.id]))
    alMenu(e, juego)
  }

  return (
    <div className="relative cristal rounded-2xl overflow-hidden flex flex-col min-h-0 flex-1">
      {escaneando && <div className="linea-escaneo z-10" />}
      <div className="overflow-auto flex-1 min-h-0 relative">
        <div className={`grid ${COLUMNAS} items-center h-[38px] px-3 sticky top-0 z-[2] bg-[#0a0d1b]/95 backdrop-blur border-b border-white/[.07]`}>
          <span />
          <Cabecera col="nombre" texto="Juego" orden={orden} setOrden={setOrden} />
          <Cabecera col="tienda" texto="Tienda" orden={orden} setOrden={setOrden} />
          <Cabecera col="local" texto="Local" orden={orden} setOrden={setOrden} className="justify-center" />
          <Cabecera col="nube" texto="Nube" orden={orden} setOrden={setOrden} className="justify-center" />
          <Cabecera col="tamano" texto="Tamaño" orden={orden} setOrden={setOrden} className="justify-end pr-4" />
          <Cabecera col="ultimo" texto="Último backup" orden={orden} setOrden={setOrden} />
        </div>
        {filas.map((fila) => (fila.tipo === 'juego'
          ? <FilaJuego key={fila.juego.id} juego={fila.juego} nivel={fila.nivel} marcado={seleccion.has(fila.juego.id)}
            enfocado={enfocado === fila.juego.id} alClic={alClic} alDoble={alDoble} alMenu={alMenuFila} />
          : <FilaGrupo key={fila.nodo.clave} fila={fila} alPlegar={plegar} />))}
        {!filas.length && (
          <div className="grid place-items-center py-20 text-center text-tenue">
            {cargando || escaneando ? (
              <div className="flex flex-col items-center gap-3">
                <div className="size-12 rounded-full border-2 border-turquesa/20 border-t-turquesa animate-spin shadow-[0_0_24px_-4px_#1de9d0]" />
                <p className="text-[14px]">Buscando tus juegos…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <SearchX size={36} className="text-tenue/50" />
                <p className="text-[14px]">{busqueda ? `Ningún juego coincide con “${busqueda}”.` : 'No hay juegos que mostrar con este filtro.'}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
