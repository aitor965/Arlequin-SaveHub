import { useEffect, useState } from 'react'
import {
  Info, FolderOpen, Archive, Cloud, EyeOff, Eye, FolderTree, Plus, Minus, Heart, Star, Save, RotateCcw,
  Stethoscope, ShieldCheck, Check, Code2, Globe,
} from 'lucide-react'
import { Modal, BotonNeon, BotonFantasma, Chip, Spinner, Logo } from '../componentes/Basicos.jsx'
import { llamar } from '../api.js'
import { colorTienda } from '../util.js'

function Dato({ etiqueta, children }) {
  if (!children) return null
  return (
    <div className="min-w-0">
      <div className="text-[10.5px] font-bold tracking-[.12em] uppercase text-tenue">{etiqueta}</div>
      <div className="text-[13px] text-white/90 break-words">{children}</div>
    </div>
  )
}

export function PanelDetalles({ id, nombre, rev, escaneando, alCerrar, acciones }) {
  const [d, setD] = useState(undefined)
  const nombreActual = d?.nombre || nombre
  // Se vuelve a pedir al cambiar la lista (p. ej. al terminar un escaneo).
  useEffect(() => { llamar('detalles', id, nombreActual).then((r) => setD((ant) => r ?? (ant ? ant : null))) }, [id, rev, escaneando]) // eslint-disable-line
  const color = colorTienda(d?.tienda)
  return (
    <Modal color="#ff9000" icono={<Info size={20} />} titulo={d?.nombre || 'Detalles'} ancho="max-w-2xl" alCerrar={alCerrar}
      subtitulo={d ? [d.tienda, d.tamano].filter(Boolean).join(' · ') : ''}
      pie={d && <>
        <BotonFantasma color="#1de9d0" className="h-10 px-3.5 text-[13px]" onClick={() => { alCerrar(); acciones.diagnostico(d.nombre) }}>
          <Stethoscope size={15} /> Diagnóstico
        </BotonFantasma>
        {d.carpeta_backup && (
          <BotonFantasma color="#2ee6a0" className="h-10 px-3.5 text-[13px]" onClick={() => llamar('verificar_copia', d.id)}>
            <ShieldCheck size={15} /> Verificar
          </BotonFantasma>
        )}
        <div className="flex-1" />
        {d.respaldable && <BotonNeon color="#2ee6a0" className="h-10 px-4 text-[13px]" onClick={() => { alCerrar(); acciones.respaldarIds([d.id]) }}><Save size={15} /> Respaldar</BotonNeon>}
        {d.respaldable && d.local > 0 && <BotonNeon color="#ff4d5e" className="h-10 px-4 text-[13px]" onClick={() => { alCerrar(); acciones.restaurarIds([d.id]) }}><RotateCcw size={15} /> Restaurar</BotonNeon>}
      </>}>
      {d === undefined && <div className="grid place-items-center py-14"><Spinner tam={26} /></div>}
      {d === null && <p className="py-8 text-center text-tenue">Este juego ya no está en la lista (quizá cambió tras un escaneo).</p>}
      {d && (
        <div className="space-y-5 pb-4">
          {(escaneando || d.escaneando) && (
            <div className="flex items-center gap-2 text-[12.5px] text-turquesa"><Spinner tam={13} /> Escaneando… los datos se actualizarán al terminar.</div>
          )}
          <div className="flex flex-wrap gap-2">
            {d.tienda && <Chip color={color}>{d.tienda}</Chip>}
            <Chip color="#2ee6a0">{d.local} cop{d.local === 1 ? 'ia' : 'ias'} local{d.local === 1 ? '' : 'es'}</Chip>
            <Chip color="#3d9bff">{d.nube} en la nube</Chip>
            {d.manual && <Chip color="#ff9000">carpeta manual</Chip>}
            {!d.respaldable && <Chip color="#8a93b2">sin ruta respaldable</Chip>}
          </div>

          <section>
            <h3 className="text-[12px] font-bold tracking-[.12em] uppercase text-naranja mb-2">Dónde guarda la partida</h3>
            {!d.rutas.length && <p className="text-[13px] text-tenue">{d.detalle || 'No hay una ruta de save local respaldable.'}</p>}
            <div className="space-y-2">
              {d.rutas.map((r) => (
                <div key={r.ruta} className="rounded-xl bg-white/[.035] border border-white/[.06] px-3.5 py-2.5 flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-[12.5px] text-white break-all select-text">{r.ruta}</div>
                    <div className="text-[11.5px] text-tenue mt-0.5">
                      {r.existe ? `${r.tamano} · modificado ${r.modificado}` : 'La carpeta no existe todavía'}
                    </div>
                  </div>
                  {r.existe && <BotonFantasma color="#ff9000" className="h-8 px-2.5 text-[12px] shrink-0" onClick={() => llamar('abrir_ruta', r.ruta)}><FolderOpen size={14} /> Abrir</BotonFantasma>}
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-[12px] font-bold tracking-[.12em] uppercase text-verde">Copias locales</h3>
              {d.carpeta_backup && <button className="text-[12px] font-semibold text-azul hover:text-white inline-flex items-center gap-1" onClick={() => llamar('abrir_ruta', d.carpeta_backup)}><Archive size={13} /> Abrir carpeta del backup</button>}
            </div>
            {!d.copias.length ? <p className="text-[13px] text-tenue">Todavía no hay ninguna copia.</p> : (
              <div className="grid gap-1.5">
                {d.copias.map((c) => (
                  <div key={c.ruta} className="flex items-center gap-2 text-[13px] text-[#d6dcef] rounded-lg px-3 py-1.5 bg-white/[.025]">
                    <span className="truncate flex-1">{c.etiqueta}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {d.copias_nube.length > 0 && (
            <section>
              <h3 className="text-[12px] font-bold tracking-[.12em] uppercase text-azul mb-2">En la nube</h3>
              <div className="grid gap-1.5">
                {d.copias_nube.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-[13px] text-[#d6dcef] rounded-lg px-3 py-1.5 bg-white/[.025]">
                    <Cloud size={14} className="text-azul" /> <span className="flex-1">{c.fecha}</span><span className="font-mono text-tenue">{c.tamano}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="grid grid-cols-2 gap-4 pt-1">
            <Dato etiqueta="Instalado en">{d.instalacion}</Dato>
            <Dato etiqueta="Cómo se detectó">{d.evidencia}</Dato>
            <Dato etiqueta="Confianza">{d.confianza}</Dato>
          </section>
        </div>
      )}
    </Modal>
  )
}

function ListaMarcable({ elementos, marcados, setMarcados, color, mono = false, vacio }) {
  if (!elementos.length) return <p className="text-[13px] text-tenue py-8 text-center">{vacio}</p>
  return (
    <div className="space-y-1.5 max-h-[48vh] overflow-auto pr-1">
      {elementos.map((e) => {
        const on = marcados.has(e)
        return (
          <button key={e} onClick={() => setMarcados((m) => { const n = new Set(m); n.has(e) ? n.delete(e) : n.add(e); return n })}
            className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left border transition
              ${on ? 'bg-white/[.07]' : 'border-white/[.06] bg-white/[.025] hover:bg-white/[.05]'}`}
            style={on ? { borderColor: `${color}80`, boxShadow: `0 0 22px -12px ${color}` } : undefined}>
            <span className={`casilla ${on ? 'on' : ''}`} style={on ? { background: color, borderColor: color, boxShadow: `0 0 12px -1px ${color}` } : undefined}>
              {on && <Check size={13} strokeWidth={3.5} className="text-black" />}
            </span>
            <span className={`truncate text-[13.5px] text-white ${mono ? 'font-mono text-[12.5px]' : 'font-semibold'}`}>{e}</span>
          </button>
        )
      })}
    </div>
  )
}

export function PanelOcultos({ alCerrar }) {
  const [lista, setLista] = useState(null)
  const [marcados, setMarcados] = useState(new Set())
  useEffect(() => { llamar('ocultos_listar').then((r) => setLista(r || [])) }, [])
  return (
    <Modal color="#ff5fb8" icono={<EyeOff size={20} />} titulo="Juegos ocultos" alCerrar={alCerrar}
      subtitulo="No aparecen en la lista. Marca los que quieras volver a mostrar."
      pie={<>
        <BotonFantasma className="h-10 px-4 text-[13px]" onClick={alCerrar}>Cerrar</BotonFantasma>
        <BotonNeon color="#ff5fb8" className="h-10 px-5 text-[13.5px]" disabled={!marcados.size}
          onClick={async () => { await llamar('ocultos_mostrar', [...marcados]); alCerrar() }}>
          <Eye size={16} /> Volver a mostrar {marcados.size ? `(${marcados.size})` : ''}
        </BotonNeon>
      </>}>
      <div className="pb-3">
        {lista === null ? <div className="grid place-items-center py-10"><Spinner /></div>
          : <ListaMarcable elementos={lista} marcados={marcados} setMarcados={setMarcados} color="#ff5fb8" vacio="No tienes ningún juego oculto." />}
      </div>
    </Modal>
  )
}

export function PanelSinLauncher({ alCerrar }) {
  const [lista, setLista] = useState(null)
  const [marcados, setMarcados] = useState(new Set())
  const [cambiado, setCambiado] = useState(false)
  useEffect(() => { llamar('sinlauncher_listar').then((r) => setLista(r || [])) }, [])
  const cerrar = () => { if (cambiado) llamar('reescanear'); alCerrar() }
  return (
    <Modal color="#b06bff" icono={<FolderTree size={20} />} titulo="Juegos sin launcher" alCerrar={cerrar} ancho="max-w-xl"
      subtitulo="Cada subcarpeta de estas rutas se trata como un posible juego (DRM-free, portables…) y se cruza con la base de datos."
      pie={<>
        <BotonFantasma color="#ff9000" className="h-10 px-4 text-[13px]" disabled={!marcados.size}
          onClick={async () => { const r = await llamar('sinlauncher_quitar', [...marcados]); setLista(r || []); setMarcados(new Set()); setCambiado(true) }}>
          <Minus size={15} /> Quitar
        </BotonFantasma>
        <BotonFantasma color="#2ee6a0" className="h-10 px-4 text-[13px]"
          onClick={async () => { const r = await llamar('sinlauncher_anadir'); if (r) { setLista(r); setCambiado(true) } }}>
          <Plus size={15} /> Añadir carpeta
        </BotonFantasma>
        <div className="flex-1" />
        <BotonNeon color="#b06bff" className="h-10 px-5 text-[13.5px]" onClick={cerrar}>{cambiado ? 'Cerrar y reescanear' : 'Cerrar'}</BotonNeon>
      </>}>
      <div className="pb-3">
        {lista === null ? <div className="grid place-items-center py-10"><Spinner /></div>
          : <ListaMarcable elementos={lista} marcados={marcados} setMarcados={setMarcados} color="#b06bff" mono vacio="Todavía no has añadido ninguna carpeta." />}
      </div>
    </Modal>
  )
}

export function PanelDonar({ alCerrar }) {
  return (
    <Modal color="#ff4d5e" icono={<Heart size={20} />} titulo="Apoya Arlequin SaveHub" alCerrar={alCerrar} ancho="max-w-md">
      <div className="pb-6 text-center">
        <div className="flex justify-center my-4"><Logo grande /></div>
        <p className="text-[14px] text-[#c3cae0] leading-relaxed">
          Arlequin es gratuito y open source. Si te resulta útil, puedes ayudarme a seguir mejorándolo y manteniendo la base de datos.
        </p>
        <div className="grid gap-3 mt-6">
          <BotonNeon color="#0070ba" className="h-12 text-[14.5px]" onClick={() => llamar('abrir_enlace', 'paypal')}><Heart size={18} /> Apoyar con PayPal</BotonNeon>
          <BotonNeon color="#8957e5" className="h-12 text-[14.5px]" onClick={() => llamar('abrir_enlace', 'sponsors')}><Star size={18} /> GitHub Sponsors</BotonNeon>
        </div>
        <div className="flex justify-center gap-4 mt-5 text-[12.5px]">
          <button className="inline-flex items-center gap-1.5 text-tenue hover:text-white" onClick={() => llamar('abrir_enlace', 'github')}><Code2 size={14} /> Código en GitHub</button>
          <button className="inline-flex items-center gap-1.5 text-tenue hover:text-white" onClick={() => llamar('abrir_enlace', 'web')}><Globe size={14} /> arlequinsavehub.com</button>
        </div>
        <p className="mt-5 text-[13px] italic text-tenue">Gracias por apoyar el proyecto ❤️</p>
      </div>
    </Modal>
  )
}
