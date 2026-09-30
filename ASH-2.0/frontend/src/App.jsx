import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Save, RotateCcw, FolderOpen, Archive, CloudUpload, Info, Stethoscope, ShieldCheck, EyeOff, Minus,
} from 'lucide-react'
import { conectar, llamar } from './api.js'
import { FILTROS, juegosDe } from './util.js'
import BarraLateral from './componentes/BarraLateral.jsx'
import Cabecera from './componentes/Cabecera.jsx'
import Tarjetas from './componentes/Tarjetas.jsx'
import TablaJuegos, { filasVisibles } from './componentes/TablaJuegos.jsx'
import BarraAcciones from './componentes/BarraAcciones.jsx'
import MenuContextual from './componentes/MenuContextual.jsx'
import { Dialogo, TextoLargo } from './componentes/Dialogos.jsx'
import { Avisos, ProgresoDescarga } from './componentes/Avisos.jsx'
import { Logo, Spinner } from './componentes/Basicos.jsx'
import PanelNube from './paneles/PanelNube.jsx'
import PanelOpciones from './paneles/PanelOpciones.jsx'
import { PanelDetalles, PanelOcultos, PanelSinLauncher, PanelDonar } from './paneles/PanelesVarios.jsx'

let bucleIniciado = false
async function iniciarBucle(manejador, alConectar) {
  if (bucleIniciado) return
  bucleIniciado = true
  const r = await conectar()
  await alConectar(r.simulada)
  for (;;) {
    const eventos = await llamar('esperar_eventos', 15)
    if (!Array.isArray(eventos)) { await new Promise((ok) => setTimeout(ok, 1000)); continue }
    for (const ev of eventos) {
      try { manejador.current?.(ev) } catch (err) { console.error('[ASH] evento', ev, err) }
    }
  }
}

function FondoAurora() {
  return (
    <div className="fondo-aurora">
      <div className="mancha m1" /><div className="mancha m2" /><div className="mancha m3" /><div className="mancha m4" />
      <div className="rejilla" />
    </div>
  )
}

function Filtros({ filtro, setFiltro, cuentas }) {
  return (
    <div className="flex items-center gap-2">
      {FILTROS.map((f) => {
        const activo = filtro === f.id
        return (
          <button key={f.id} onClick={() => setFiltro(f.id)}
            className={`h-8 px-3.5 rounded-full text-[12.5px] font-bold border transition inline-flex items-center gap-1.5
              ${activo ? 'text-white' : 'text-[#aeb6cf] border-white/[.08] bg-white/[.03] hover:text-white hover:border-white/20'}`}
            style={activo ? { background: `${f.color}2b`, borderColor: `${f.color}99`, boxShadow: `0 0 20px -6px ${f.color}` } : undefined}>
            <span className="size-1.5 rounded-full" style={{ background: f.color, boxShadow: activo ? `0 0 8px ${f.color}` : 'none' }} />
            {f.texto}
            <span className="font-mono text-[11px] opacity-70">{cuentas[f.id] ?? ''}</span>
          </button>
        )
      })}
    </div>
  )
}

export default function App() {
  const [conectado, setConectado] = useState(false)
  const [simulada, setSimulada] = useState(false)
  const [estado, setEstado] = useState(null)
  const [tabla, setTabla] = useState({ arbol: [], cerrados: [], rev: -1 })
  const [cargandoTabla, setCargandoTabla] = useState(true)
  const [seleccion, setSeleccion] = useState(new Set())
  const [enfocado, setEnfocado] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [filtro, setFiltro] = useState('Todos')
  const [orden, setOrden] = useState(null)
  const [cerrados, setCerrados] = useState(new Set())
  const [dialogos, setDialogos] = useState([])
  const [textos, setTextos] = useState([])
  const [avisos, setAvisos] = useState([])
  const [panel, setPanel] = useState(null)          // {tipo, id?}
  const [menu, setMenu] = useState(null)
  const [descarga, setDescarga] = useState(null)
  const refBuscar = useRef(null)
  const temporizadores = useRef({})

  // ---- carga de datos -----------------------------------------------------------
  const cargarEstado = useCallback(async () => {
    const e = await llamar('estado')
    if (e) setEstado(e)
  }, [])

  const cargarTabla = useCallback(async () => {
    const t = await llamar('tabla')
    if (!t) return
    setTabla(t)
    setCerrados(new Set(t.cerrados || []))
    setCargandoTabla(false)
    // Los identificadores de fila cambian cuando cambian sus copias: se
    // conserva la selección buscando el mismo juego por su nombre.
    const juegos = juegosDe(t.arbol)
    const porId = new Set(juegos.map((j) => j.id))
    const porNombre = new Map(juegos.map((j) => [j.nombre, j.id]))
    const remapear = (id, anteriores) => {
      if (porId.has(id)) return id
      const viejo = anteriores.find((j) => j.id === id)
      return viejo ? porNombre.get(viejo.nombre) : undefined
    }
    setSeleccion((s) => {
      if (!s.size) return s
      const anteriores = juegosDe(tablaRef.current?.arbol)
      const n = new Set()
      for (const id of s) { const nuevo = remapear(id, anteriores); if (nuevo) n.add(nuevo) }
      return n
    })
    setEnfocado((f) => (f ? remapear(f, juegosDe(tablaRef.current?.arbol)) ?? null : f))
    tablaRef.current = t
  }, [])
  const tablaRef = useRef(null)

  const programar = useCallback((clave, fn, ms) => {
    if (temporizadores.current[clave]) return
    temporizadores.current[clave] = setTimeout(() => { temporizadores.current[clave] = null; fn() }, ms)
  }, [])

  const quitarAviso = useCallback((id) => setAvisos((a) => a.filter((x) => x.id !== id)), [])
  const avisar = useCallback((titulo, texto, error = false) => {
    setAvisos((a) => [...a.slice(-4), { id: Math.random().toString(36).slice(2), titulo, texto, error }])
  }, [])

  // ---- bucle de eventos de Python -------------------------------------------------
  // Un único bucle para toda la vida de la página; siempre entrega los eventos
  // al manejador más reciente (React puede montar el efecto dos veces).
  const manejador = useRef(null)
  manejador.current = (ev) => {
    switch (ev.tipo) {
      case 'estado': programar('estado', cargarEstado, 120); break
      case 'tabla': programar('tabla', cargarTabla, 250); break
      case 'listo': cargarEstado(); cargarTabla(); break
      case 'dialogo': setDialogos((d) => (d.some((x) => x.id === ev.id) ? d : [...d, ev])); break
      case 'texto': setTextos((t) => [...t, ev]); break
      case 'toast': avisar(ev.titulo, ev.texto, ev.error); break
      case 'abrir': setPanel({ tipo: ev.panel, id: ev.id }); break
      case 'descarga': setDescarga(ev.activo ? { ...ev } : null); break
      default: break
    }
  }
  useEffect(() => {
    iniciarBucle(manejador, async (simuladaR) => {
      setSimulada(simuladaR)
      setConectado(true)
      await llamar('iniciar')
      cargarEstado()
      cargarTabla()
    })
    const respaldo = setInterval(() => { cargarEstado() }, 5000)
    return () => clearInterval(respaldo)
  }, [cargarEstado, cargarTabla])

  // ---- derivados --------------------------------------------------------------------
  const texto = busqueda.trim().toLowerCase()
  const { filas, visibles } = useMemo(
    () => filasVisibles(tabla.arbol, { texto, modo: filtro, orden, cerrados }),
    [tabla, texto, filtro, orden, cerrados])
  const todos = useMemo(() => juegosDe(tabla.arbol), [tabla])
  const porId = useMemo(() => new Map(todos.map((j) => [j.id, j])), [todos])
  const seleccionados = useMemo(() => [...seleccion].map((id) => porId.get(id)).filter(Boolean), [seleccion, porId])
  const respaldablesVisibles = visibles.filter((j) => j.respaldable)
  const todosMarcados = respaldablesVisibles.length > 0 && respaldablesVisibles.every((j) => seleccion.has(j.id))
  const cuentas = useMemo(() => {
    const c = {}
    for (const f of FILTROS) c[f.id] = filasVisibles(tabla.arbol, { texto, modo: f.id, orden: null, cerrados: new Set() }).visibles.length
    return c
  }, [tabla, texto])

  // ---- acciones --------------------------------------------------------------------
  const ids = () => seleccionados.filter((j) => j.respaldable).map((j) => j.id)
  const acciones = {
    escanear: () => llamar('escanear'),
    actualizarTodo: () => llamar('actualizar_todo'),
    anadirCarpeta: () => llamar('anadir_carpeta'),
    respaldarIds: (lista) => { llamar('respaldar', lista); setSeleccion(new Set()) },
    restaurarIds: (lista) => llamar('restaurar', lista),
    respaldar: () => acciones.respaldarIds(ids()),
    restaurar: () => acciones.restaurarIds(seleccionados.filter((j) => j.local > 0).map((j) => j.id)),
    subirNube: () => llamar('subir_a_nube', seleccionados.filter((j) => j.local > 0).map((j) => j.id)),
    ocultar: () => llamar('ocultar', seleccionados.map((j) => j.id)),
    quitarManual: () => llamar('quitar_manual', seleccionados.map((j) => j.id)),
    verificarTodas: () => llamar('verificar_todas'),
    diagnostico: (nombre) => llamar('diagnostico', nombre || null),
    estadisticas: () => llamar('estadisticas_bd'),
    instrucciones: () => llamar('instrucciones'),
    opciones: () => setPanel({ tipo: 'opciones' }),
    abrirLog: () => llamar('abrir_log'),
    abrirBackups: () => llamar('abrir_carpeta_backups'),
    cambiarBackups: () => llamar('cambiar_carpeta_backups'),
  }

  const alternarTodos = () => {
    setSeleccion((s) => {
      const n = new Set(s)
      if (todosMarcados) respaldablesVisibles.forEach((j) => n.delete(j.id))
      else respaldablesVisibles.forEach((j) => n.add(j.id))
      return n
    })
  }

  const plegar = (clave, abierto) => {
    setCerrados((c) => { const n = new Set(c); abierto ? n.add(clave) : n.delete(clave); return n })
    llamar('plegar', clave, abierto)
  }

  const responder = useCallback((d, valor) => {
    setDialogos((lista) => lista.filter((x) => x.id !== d.id))
    llamar('responder', d.id, valor)
  }, [])

  const abrirMenu = (e, juego) => {
    const n = seleccion.has(juego.id) ? Math.max(1, seleccion.size) : 1
    const varios = n > 1 ? ` (${n} juegos)` : ''
    const nube = estado?.nube || {}
    const lista = seleccion.has(juego.id) && seleccion.size ? [...seleccion] : [juego.id]
    const conCopia = lista.filter((id) => (porId.get(id)?.local || 0) > 0)
    setMenu({
      x: e.clientX, y: e.clientY, titulo: juego.nombre,
      elementos: [
        { texto: `Respaldar${varios}`, icono: Save, color: '#2ee6a0', desactivado: !juego.respaldable || estado?.escaneando,
          onClick: () => acciones.respaldarIds(lista) },
        { texto: `Restaurar…${varios}`, icono: RotateCcw, color: '#ff4d5e', desactivado: !conCopia.length || estado?.escaneando,
          onClick: () => acciones.restaurarIds(conCopia) },
        '-',
        { texto: 'Abrir carpeta del save', icono: FolderOpen, color: '#ff9000', desactivado: !juego.respaldable,
          onClick: () => llamar('abrir_carpeta_save', juego.id) },
        { texto: 'Abrir carpeta del backup', icono: Archive, color: '#ffd23f', desactivado: !juego.local,
          onClick: () => llamar('abrir_carpeta_backup', juego.id) },
        { texto: nube.conectada ? `Subir a ${nube.nombre}${varios}` : 'Subir a la nube (no conectada)', icono: CloudUpload, color: '#3d9bff',
          desactivado: !nube.conectada || !conCopia.length, onClick: () => llamar('subir_a_nube', conCopia) },
        '-',
        { texto: 'Detalles', icono: Info, color: '#1de9d0', onClick: () => setPanel({ tipo: 'detalles', id: juego.id }) },
        { texto: 'Diagnóstico', icono: Stethoscope, color: '#1de9d0', onClick: () => acciones.diagnostico(juego.nombre) },
        { texto: 'Verificar la copia', icono: ShieldCheck, color: '#2ee6a0', desactivado: !juego.local,
          onClick: () => llamar('verificar_copia', juego.id) },
        '-',
        ...(juego.manual ? [{ texto: 'Quitar carpeta manual', icono: Minus, color: '#ff9000',
          onClick: () => llamar('quitar_manual', lista) }] : []),
        { texto: `Ocultar${varios}`, icono: EyeOff, color: '#ff5fb8', onClick: () => llamar('ocultar', lista) },
      ],
    })
  }

  // Atajos de teclado
  useEffect(() => {
    const tecla = (e) => {
      if (dialogos.length || panel || textos.length) return
      const enCampo = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)
      if (e.ctrlKey && e.key.toLowerCase() === 'f') { e.preventDefault(); refBuscar.current?.focus(); refBuscar.current?.select() }
      else if (e.ctrlKey && e.key.toLowerCase() === 'a' && !enCampo) { e.preventDefault(); alternarTodos() }
      else if (e.key === 'F5') { e.preventDefault(); acciones.escanear() }
      else if (e.key === 'Escape' && !enCampo) setSeleccion(new Set())
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  })

  // Sin menú contextual del navegador fuera de la tabla.
  useEffect(() => {
    const bloquear = (e) => { if (!['INPUT', 'TEXTAREA'].includes(e.target.tagName)) e.preventDefault() }
    window.addEventListener('contextmenu', bloquear)
    return () => window.removeEventListener('contextmenu', bloquear)
  }, [])

  if (!conectado || !estado) {
    return (
      <div className="h-full grid place-items-center relative">
        <FondoAurora />
        <div className="relative flex flex-col items-center gap-5 aparecer">
          <Logo grande />
          <div className="flex items-center gap-3 text-tenue text-[13px]"><Spinner /> Arrancando el motor…</div>
          {/* Los diálogos del arranque (permisos, primera ejecución) también se ven aquí. */}
          {dialogos[0] && <Dialogo d={dialogos[0]} responder={(v) => responder(dialogos[0], v)} />}
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex relative">
      <FondoAurora />
      <BarraLateral estado={estado} abrirPanel={(tipo) => setPanel({ tipo })} acciones={acciones} />

      <main className="relative z-10 flex-1 min-w-0 flex flex-col gap-4 px-6 pt-5 pb-4">
        {simulada && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 chip" style={{ '--c': '#ffd23f' }}>
            Modo demostración · datos de ejemplo
          </div>
        )}
        <Cabecera estado={estado} busqueda={busqueda} setBusqueda={setBusqueda} acciones={acciones} refBuscar={refBuscar} />
        <Tarjetas tabla={tabla} estado={estado} abrirPanel={(tipo) => setPanel({ tipo })} setFiltro={setFiltro} />
        <div className="flex items-center justify-between gap-3">
          <Filtros filtro={filtro} setFiltro={setFiltro} cuentas={cuentas} />
          <span className="text-[12px] text-tenue">
            {estado?.textos?.partidas?.texto}
            {estado?.ultimo_escaneo_s ? ` · escaneo en ${Number(estado.ultimo_escaneo_s).toFixed(1).replace('.', ',')} s` : ''}
          </span>
        </div>
        <TablaJuegos filas={filas} visibles={visibles} seleccion={seleccion} setSeleccion={setSeleccion}
          enfocado={enfocado} setEnfocado={setEnfocado} orden={orden} setOrden={setOrden} plegar={plegar}
          alDetalles={(id) => setPanel({ tipo: 'detalles', id })} alMenu={abrirMenu}
          escaneando={estado?.escaneando} cargando={cargandoTabla} busqueda={busqueda} />
        <BarraAcciones estado={estado} seleccionados={seleccionados} todosMarcados={todosMarcados}
          alternarTodos={alternarTodos} acciones={acciones} />
      </main>

      {menu && <MenuContextual {...menu} alCerrar={() => setMenu(null)} />}

      {panel?.tipo === 'nube' && <PanelNube estado={estado} alCerrar={() => setPanel(null)} />}
      {panel?.tipo === 'detalles' && <PanelDetalles id={panel.id} nombre={porId.get(panel.id)?.nombre} rev={tabla.rev}
        escaneando={estado?.escaneando} alCerrar={() => setPanel(null)} acciones={acciones} />}
      {panel?.tipo === 'ocultos' && <PanelOcultos alCerrar={() => setPanel(null)} />}
      {panel?.tipo === 'sinlauncher' && <PanelSinLauncher alCerrar={() => setPanel(null)} />}
      {panel?.tipo === 'donar' && <PanelDonar alCerrar={() => setPanel(null)} />}
      {panel?.tipo === 'opciones' && <PanelOpciones alCerrar={() => setPanel(null)} abrirNube={() => setPanel({ tipo: 'nube' })} />}

      {textos[0] && <TextoLargo titulo={textos[0].titulo} texto={textos[0].texto} alCerrar={() => setTextos((t) => t.slice(1))} />}
      {dialogos[0] && <Dialogo d={dialogos[0]} responder={(v) => responder(dialogos[0], v)} />}

      <ProgresoDescarga progreso={descarga} cancelar={() => llamar('nube_cancelar_descarga')} />
      <Avisos avisos={avisos} quitar={quitarAviso} />
    </div>
  )
}
