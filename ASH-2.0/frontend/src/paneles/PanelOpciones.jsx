import { useEffect, useMemo, useState } from 'react'
import { Settings, Monitor, HardDrive, Cloud, Search, Check, Ban, BookOpen, AppWindow, Save, Eye } from 'lucide-react'
import { TextoLargo } from '../componentes/Dialogos.jsx'
import { Modal, BotonNeon, BotonFantasma, Spinner } from '../componentes/Basicos.jsx'
import { llamar } from '../api.js'

const UNIDADES = ['horas', 'días', 'semanas']
const MAXIMOS = [0, 1, 2, 3, 5, 10, 15, 20]

function Interruptor({ activo, onChange, color = '#1de9d0', desactivado }) {
  return (
    <button type="button" disabled={desactivado} onClick={() => onChange(!activo)}
      className="relative h-[22px] w-[40px] rounded-full shrink-0 transition disabled:opacity-35"
      style={{
        background: activo ? color : 'rgb(255 255 255 / .1)',
        boxShadow: activo ? `0 0 16px -2px ${color}, inset 0 0 0 1px ${color}` : 'inset 0 0 0 1px rgb(255 255 255 / .12)',
      }}>
      <span className="absolute top-[3px] size-4 rounded-full bg-white shadow transition-all"
        style={{ left: activo ? 21 : 3 }} />
    </button>
  )
}

function Fila({ titulo, ayuda, children, color, activo, onChange, desactivado, sangria = false }) {
  return (
    <div className={`flex items-start gap-3 py-2.5 ${sangria ? 'pl-[52px]' : ''} ${desactivado ? 'opacity-45' : ''}`}>
      {onChange && <div className="pt-0.5"><Interruptor activo={activo} onChange={onChange} color={color} desactivado={desactivado} /></div>}
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold text-white leading-snug">{titulo}</div>
        {ayuda && <div className="text-[12px] text-tenue leading-snug mt-0.5">{ayuda}</div>}
        {children && <div className="mt-2 flex flex-wrap items-center gap-2">{children}</div>}
      </div>
    </div>
  )
}

function Tarjeta({ titulo, color, children }) {
  return (
    <section className="rounded-2xl border border-white/[.07] bg-white/[.025] px-4 py-2">
      <h3 className="text-[11px] font-bold tracking-[.14em] uppercase pt-2 pb-1" style={{ color }}>{titulo}</h3>
      <div className="divide-y divide-white/[.05]">{children}</div>
    </section>
  )
}

const claseCampo = 'h-9 rounded-lg bg-black/35 border border-white/10 px-2.5 text-[13px] text-white outline-none focus:border-turquesa/60 transition'

function Numero({ valor, onChange, min = 0, max = 100000, ancho = 'w-20', desactivado }) {
  return (
    <input type="number" min={min} max={max} value={valor} disabled={desactivado}
      onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
      onBlur={() => onChange(Math.min(max, Math.max(min, Number(valor) || min)))}
      className={`${claseCampo} ${ancho} text-center tabular-nums disabled:opacity-40`} />
  )
}

function Selector({ valor, opciones, onChange, desactivado }) {
  return (
    <select value={valor} disabled={desactivado} onChange={(e) => onChange(e.target.value)} className={`${claseCampo} pr-7 disabled:opacity-40`}>
      {opciones.map((o) => (typeof o === 'object'
        ? <option key={o.v} value={o.v}>{o.t}</option>
        : <option key={o} value={o}>{o}</option>))}
    </select>
  )
}

function BotonExcluidos({ n, onClick, desactivado }) {
  return (
    <button type="button" disabled={desactivado} onClick={onClick}
      className={`h-8 px-3 rounded-lg text-[12px] font-bold inline-flex items-center gap-1.5 border transition disabled:opacity-40
        ${n ? 'text-rojo border-rojo/40 bg-rojo/10 hover:bg-rojo/20' : 'text-tenue border-white/10 bg-white/[.03] hover:text-white'}`}>
      <Ban size={13} /> {n ? `${n} juego${n === 1 ? '' : 's'} excluido${n === 1 ? '' : 's'}` : 'Ningún juego excluido'}
    </button>
  )
}

// Lista de juegos para marcar los EXCLUIDOS de un modo automático.
function SelectorExcluidos({ titulo, juegos, excluidos, alGuardar, alCerrar }) {
  const [marcados, setMarcados] = useState(new Set(excluidos))
  const [buscar, setBuscar] = useState('')
  const visibles = useMemo(() => juegos.filter((j) => j.nombre.toLowerCase().includes(buscar.trim().toLowerCase())), [juegos, buscar])
  return (
    <Modal color="#ff4d5e" icono={<Ban size={20} />} titulo={titulo} subtitulo="Los juegos marcados se excluyen de este modo. Los demás se incluyen."
      ancho="max-w-xl" alCerrar={alCerrar}
      pie={<>
        <BotonFantasma className="h-10 px-4 text-[13px]" onClick={alCerrar}>Cancelar</BotonFantasma>
        <BotonNeon color="#2ee6a0" className="h-10 px-5 text-[13.5px]" onClick={() => { alGuardar([...marcados]); alCerrar() }}>Aceptar</BotonNeon>
      </>}>
      <div className="pb-3 space-y-3">
        <div className="flex items-center gap-2">
          <label className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-tenue z-10" />
            <input autoFocus value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar…" className={`${claseCampo} w-full pl-9`} />
          </label>
          <BotonFantasma color="#ff4d5e" className="h-9 px-3 text-[12px]"
            onClick={() => setMarcados((m) => new Set([...m, ...visibles.map((j) => j.id)]))}>Excluir todos</BotonFantasma>
          <BotonFantasma color="#3d9bff" className="h-9 px-3 text-[12px]"
            onClick={() => setMarcados((m) => { const n = new Set(m); visibles.forEach((j) => n.delete(j.id)); return n })}>Ninguno</BotonFantasma>
        </div>
        <div className="space-y-1 max-h-[46vh] overflow-auto pr-1">
          {!visibles.length && <p className="text-tenue text-[13px] text-center py-6">No hay juegos.</p>}
          {visibles.map((j) => {
            const on = marcados.has(j.id)
            return (
              <button key={j.id} type="button"
                onClick={() => setMarcados((m) => { const n = new Set(m); n.has(j.id) ? n.delete(j.id) : n.add(j.id); return n })}
                className={`w-full flex items-center gap-3 rounded-lg px-3 py-2 text-left border transition
                  ${on ? 'border-rojo/50 bg-rojo/[.12]' : 'border-white/[.05] bg-white/[.02] hover:bg-white/[.05]'}`}>
                <span className={`casilla ${on ? 'on' : ''}`} style={on ? { background: '#ff4d5e', borderColor: '#ff4d5e', boxShadow: '0 0 12px -1px #ff4d5e' } : undefined}>
                  {on && <Check size={13} strokeWidth={3.5} className="text-black" />}
                </span>
                <span className={`truncate text-[13px] font-semibold ${on ? 'text-white' : 'text-[#d6dcef]'}`}>{j.nombre}</span>
              </button>
            )
          })}
        </div>
        <p className="text-[12px] text-tenue">{marcados.size} excluido{marcados.size === 1 ? '' : 's'} de {juegos.length}</p>
      </div>
    </Modal>
  )
}

const PESTANAS = [
  { id: 'general', texto: 'General', icono: Monitor, color: '#ff9000' },
  { id: 'local', texto: 'Local', icono: HardDrive, color: '#2ee6a0' },
  { id: 'nube', texto: 'Nube', icono: Cloud, color: '#3d9bff' },
]

export default function PanelOpciones({ alCerrar, abrirNube }) {
  const [o, setO] = useState(null)
  const [pestana, setPestana] = useState('general')
  const [selector, setSelector] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [vistaPrevia, setVistaPrevia] = useState(null)
  useEffect(() => { llamar('opciones_cargar').then((r) => setO(r || null)) }, [])
  const cambiar = (clave) => (valor) => setO((a) => ({ ...a, [clave]: valor }))
  const n = (modo) => o?.excluidos?.[modo]?.length || 0
  const abrirSelector = (modo, titulo) => setSelector({ modo, titulo })

  const guardar = async () => {
    setGuardando(true); setError('')
    const r = await llamar('opciones_guardar', o)
    setGuardando(false)
    if (r?.ok) alCerrar()
    else setError(r?.error || 'No se pudieron guardar las opciones.')
  }

  const maximos = (actual) => {
    const lista = MAXIMOS.includes(actual) ? MAXIMOS : [...MAXIMOS, actual]
    return lista.map((v) => ({ v, t: v === 0 ? 'Sin límite' : String(v) }))
  }

  return (
    <>
      <Modal color="#ff9000" icono={<Settings size={20} />} titulo="Opciones" subtitulo="Los cambios se aplican al pulsar Guardar."
        ancho="max-w-3xl" alCerrar={alCerrar} cerrarConFondo={false}
        pie={<>
          <BotonFantasma color="#b06bff" className="h-10 px-3.5 text-[12.5px]" onClick={() => llamar('instrucciones_avanzadas')}>
            <BookOpen size={15} /> Instrucciones avanzadas
          </BotonFantasma>
          <BotonFantasma className="h-10 px-3.5 text-[12.5px]" title="Abre la ventana de opciones de la versión 1.1.x"
            onClick={() => { llamar('opciones_clasicas'); alCerrar() }}>
            <AppWindow size={15} /> Ventana clásica
          </BotonFantasma>
          <div className="flex-1" />
          {error && <span className="text-rojo text-[12.5px] mr-2">{error}</span>}
          <BotonFantasma className="h-10 px-4 text-[13px]" onClick={alCerrar}>Cancelar</BotonFantasma>
          <BotonNeon color="#2ee6a0" className="h-10 px-6 text-[13.5px]" disabled={!o || guardando} onClick={guardar}>
            {guardando ? <Spinner color="#fff" /> : <Save size={16} />} Guardar
          </BotonNeon>
        </>}>
        {!o ? <div className="grid place-items-center py-20"><Spinner tam={28} /></div> : (
          <div className="pb-4">
            <div className="flex gap-2 mb-4 sticky top-0 z-10 py-1 bg-[#12162b]/95 backdrop-blur rounded-xl">
              {PESTANAS.map((p) => {
                const activa = pestana === p.id
                return (
                  <button key={p.id} onClick={() => setPestana(p.id)}
                    className={`flex-1 h-10 rounded-xl inline-flex items-center justify-center gap-2 text-[13.5px] font-bold border transition
                      ${activa ? 'text-white' : 'text-tenue border-white/[.06] hover:text-white'}`}
                    style={activa ? { background: `${p.color}22`, borderColor: `${p.color}88`, boxShadow: `0 0 24px -8px ${p.color}` } : undefined}>
                    <p.icono size={16} style={{ color: p.color }} /> {p.texto}
                  </button>
                )
              })}
            </div>

            {pestana === 'general' && (
              <div className="grid gap-3">
                <Tarjeta titulo="Inicio" color="#ff9000">
                  <Fila titulo="Abrir Arlequin SaveHub con Windows" color="#ff9000" activo={o.iniciar_windows}
                    onChange={(v) => setO((a) => ({ ...a, iniciar_windows: v, iniciar_minimizado: v ? a.iniciar_minimizado : false }))} />
                  <Fila titulo="Abrir minimizado cuando inicie Windows" ayuda="Arranca directamente en la bandeja del sistema."
                    color="#ff9000" activo={o.iniciar_minimizado} onChange={cambiar('iniciar_minimizado')} desactivado={!o.iniciar_windows} />
                  <Fila titulo="Ocultar en la bandeja del sistema al minimizar" color="#ff9000"
                    activo={o.minimizar_en_bandeja} onChange={cambiar('minimizar_en_bandeja')} />
                  <Fila titulo="Comprobar si hay una versión nueva al iniciar" color="#ff9000"
                    ayuda="En esta beta las actualizaciones del programa se instalan a mano."
                    activo={o.comprobar_actualizaciones} onChange={cambiar('comprobar_actualizaciones')} />
                  <Fila titulo="Avisos de tareas automáticas" ayuda="Cuándo avisar al terminar un respaldo o una subida automática.">
                    <Selector valor={o.avisos_automaticos} opciones={o.avisos_opciones} onChange={cambiar('avisos_automaticos')} />
                  </Fila>
                </Tarjeta>
                <Tarjeta titulo="Lista y rendimiento" color="#ffd23f">
                  <Fila titulo="Mostrar juegos instalados sin save conocido" color="#ffd23f" activo={o.mostrar_sin_datos} onChange={cambiar('mostrar_sin_datos')} />
                  <Fila titulo="Mostrar juegos a la espera de su primer uso" color="#ffd23f" activo={o.mostrar_previstos} onChange={cambiar('mostrar_previstos')} />
                  <Fila titulo="Mostrar juegos 100% online" ayuda="Su progreso se guarda en el servidor." color="#ffd23f" activo={o.mostrar_online} onChange={cambiar('mostrar_online')} />
                  <Fila titulo="Aplazar el cálculo SHA-256 hasta que el PC esté inactivo" color="#ffd23f"
                    ayuda="Lo usan los backups locales y la nube." activo={o.hash_solo_idle} onChange={cambiar('hash_solo_idle')}>
                    <span className="text-[12.5px] text-tenue">Esperar</span>
                    <Numero valor={o.hash_idle_min} min={1} max={120} onChange={cambiar('hash_idle_min')} desactivado={!o.hash_solo_idle} />
                    <span className="text-[12.5px] text-tenue">min de inactividad</span>
                  </Fila>
                </Tarjeta>
                <Tarjeta titulo="Ayuda a mejorar Arlequin" color="#ff5fb8">
                  <Fila titulo="Compartir las rutas de guardado que aprende ASH" color="#ff5fb8"
                    ayuda="Envía de forma anónima las carpetas de partidas que ASH encuentra (o que añades a mano) para juegos que la base de datos aún no conoce, y qué juegos instalados no tienen ruta. Se comparan con las de otros usuarios para mejorar ArlequinGameDB. Nunca se envían tus partidas ni tu nombre de usuario."
                    activo={o.contribuir} onChange={cambiar('contribuir')}>
                    <BotonFantasma color="#ff5fb8" className="h-8 px-3 text-[12px]"
                      onClick={async () => setVistaPrevia(await llamar('contribuir_vista_previa') || 'No disponible.')}>
                      <Eye size={14} /> Ver qué se enviaría
                    </BotonFantasma>
                    {o.contribuir_estado?.ultimo_envio && (
                      <span className="text-[12px] text-tenue">Último envío: {o.contribuir_estado.ultimo_envio}</span>
                    )}
                  </Fila>
                </Tarjeta>
              </div>
            )}

            {pestana === 'local' && (
              <div className="grid gap-3">
                <Tarjeta titulo="Respaldos automáticos" color="#2ee6a0">
                  <Fila titulo="Hacer un respaldo periódico" color="#2ee6a0" activo={o.local_periodico} onChange={cambiar('local_periodico')}>
                    <span className="text-[12.5px] text-tenue">Cada</span>
                    <Numero valor={o.local_valor} min={1} max={10000} onChange={cambiar('local_valor')} desactivado={!o.local_periodico} />
                    <Selector valor={o.local_unidad} opciones={UNIDADES} onChange={cambiar('local_unidad')} desactivado={!o.local_periodico} />
                    <BotonExcluidos n={n('local_periodico')} desactivado={!o.local_periodico}
                      onClick={() => abrirSelector('local_periodico', 'Excluir del respaldo periódico')} />
                  </Fila>
                  <Fila titulo="Solo si el PC está inactivo" ayuda="Si estás usando el PC, el respaldo periódico se aplaza."
                    color="#2ee6a0" activo={o.local_solo_idle} onChange={cambiar('local_solo_idle')} desactivado={!o.local_periodico} sangria />
                  <Fila titulo="Respaldar los juegos cuando se cierren" color="#2ee6a0" activo={o.local_cierre} onChange={cambiar('local_cierre')}
                    ayuda="Actúa al detectar ABIERTO → CERRADO. Si detecta un crash, protege el último backup válido y no copia el save sospechoso.">
                    <BotonExcluidos n={n('local_cierre')} desactivado={!o.local_cierre}
                      onClick={() => abrirSelector('local_cierre', 'Excluir del respaldo al cerrar el juego')} />
                  </Fila>
                </Tarjeta>
                <Tarjeta titulo="Copias" color="#1de9d0">
                  <Fila titulo="Máximo de copias por juego" ayuda="Sin límite = conservar todas las copias históricas.">
                    <Selector valor={o.max_backups} opciones={maximos(o.max_backups)} onChange={(v) => cambiar('max_backups')(Number(v))} />
                  </Fila>
                  <Fila titulo="Guardar lo que había antes de restaurar" ayuda="Crea la copia “↩️ Antes de restaurar” para poder deshacer."
                    color="#1de9d0" activo={o.copia_antes_restaurar} onChange={cambiar('copia_antes_restaurar')} />
                  <Fila titulo="Comprobar la integridad de las copias cada semana" ayuda="Se hace con el PC inactivo; solo avisa si encuentra problemas."
                    color="#1de9d0" activo={o.verificacion_semanal} onChange={cambiar('verificacion_semanal')} />
                  <Fila titulo="No copiar estos archivos o carpetas"
                    ayuda="Separados por ; — ejemplo: *.log; *.tmp; ShaderCache; Crashes. Ocupan menos, pero al restaurar no se recuperan.">
                    <input value={o.patrones_exclusion} onChange={(e) => cambiar('patrones_exclusion')(e.target.value)}
                      placeholder="*.log; *.tmp; ShaderCache" className={`${claseCampo} w-full font-mono`} />
                  </Fila>
                </Tarjeta>
              </div>
            )}

            {pestana === 'nube' && (
              <div className="grid gap-3">
                {!o.nube_conectada && (
                  <div className="rounded-xl border border-azul/30 bg-azul/10 px-4 py-3 flex items-center gap-3">
                    <Cloud size={18} className="text-azul shrink-0" />
                    <span className="text-[13px] text-[#d6dcef] flex-1">No hay ninguna nube conectada: estas opciones se aplicarán cuando conectes una.</span>
                    <BotonFantasma color="#3d9bff" className="h-8 px-3 text-[12px]" onClick={() => { alCerrar(); abrirNube() }}>Conectar</BotonFantasma>
                  </div>
                )}
                <Tarjeta titulo="Subidas automáticas" color="#3d9bff">
                  <Fila titulo="Subir periódicamente" color="#3d9bff" activo={o.nube_periodica} onChange={cambiar('nube_periodica')}>
                    <span className="text-[12.5px] text-tenue">Cada</span>
                    <Numero valor={o.nube_valor} min={1} max={10000} onChange={cambiar('nube_valor')} desactivado={!o.nube_periodica} />
                    <Selector valor={o.nube_unidad} opciones={UNIDADES} onChange={cambiar('nube_unidad')} desactivado={!o.nube_periodica} />
                    <BotonExcluidos n={n('nube_periodico')} desactivado={!o.nube_periodica}
                      onClick={() => abrirSelector('nube_periodico', 'Excluir de la subida periódica')} />
                  </Fila>
                  <Fila titulo="Subir al cerrar el juego" color="#3d9bff" activo={o.nube_cierre} onChange={cambiar('nube_cierre')}>
                    <BotonExcluidos n={n('nube_cierre')} desactivado={!o.nube_cierre}
                      onClick={() => abrirSelector('nube_cierre', 'Excluir de la subida al cerrar el juego')} />
                  </Fila>
                  <Fila titulo="Máximo de copias por juego en la nube">
                    <Selector valor={o.max_copias_nube} opciones={maximos(o.max_copias_nube)} onChange={(v) => cambiar('max_copias_nube')(Number(v))} />
                  </Fila>
                </Tarjeta>
                <Tarjeta titulo="Red y compresión" color="#b06bff">
                  <Fila titulo="Límite de velocidad de subida" ayuda="0 = sin límite.">
                    <Numero valor={o.limite_subida} min={0} max={1048576} ancho="w-28" onChange={cambiar('limite_subida')} />
                    <span className="text-[12.5px] text-tenue">KB/s</span>
                  </Fila>
                  <Fila titulo="No subir con conexiones de uso medido" color="#b06bff" activo={o.no_red_medida} onChange={cambiar('no_red_medida')} />
                  <Fila titulo="Compresión ZIP" ayuda="Rápido = menos CPU · Máximo = menos tamaño.">
                    <Selector valor={o.compresion} opciones={['Rápido', 'Equilibrado', 'Máximo']} onChange={cambiar('compresion')} />
                  </Fila>
                </Tarjeta>
                <Tarjeta titulo="Protección" color="#ff5fb8">
                  <Fila titulo="Bloquear la subida si el tamaño cambia demasiado" color="#ff5fb8"
                    ayuda="Respecto a la copia anterior: evita subir un save que parece dañado."
                    activo={o.anti_corrupcion} onChange={cambiar('anti_corrupcion')}>
                    <span className="text-[12.5px] text-tenue">Más de</span>
                    <Numero valor={o.anti_corrupcion_pct} min={1} max={500} onChange={cambiar('anti_corrupcion_pct')} desactivado={!o.anti_corrupcion} />
                    <span className="text-[12.5px] text-tenue">%</span>
                  </Fila>
                  <Fila titulo="No subir a la nube mientras OBS esté abierto" color="#ff5fb8"
                    ayuda="Grabando o transmitiendo: no gasta red ni disco durante la sesión."
                    activo={o.obs_pause} onChange={cambiar('obs_pause')} />
                </Tarjeta>
              </div>
            )}
          </div>
        )}
      </Modal>
      {vistaPrevia && <TextoLargo titulo="Lo que se enviaría" texto={vistaPrevia} alCerrar={() => setVistaPrevia(null)} />}
      {selector && o && (
        <SelectorExcluidos titulo={selector.titulo} juegos={o.juegos} excluidos={o.excluidos[selector.modo] || []}
          alCerrar={() => setSelector(null)}
          alGuardar={(lista) => setO((a) => ({ ...a, excluidos: { ...a.excluidos, [selector.modo]: lista } }))} />
      )}
    </>
  )
}
