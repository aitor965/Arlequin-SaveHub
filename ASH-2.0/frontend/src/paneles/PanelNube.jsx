import { useEffect, useMemo, useState } from 'react'
import { Cloud, CloudUpload, CloudDownload, RefreshCw, LogOut, ArrowLeft, Search, Check, Info } from 'lucide-react'
import { Modal, BotonNeon, BotonFantasma, Spinner, Chip } from '../componentes/Basicos.jsx'
import { llamar } from '../api.js'
import { formatearBytes } from '../util.js'
import { t } from '../i18n.js'

function Conectar({ nube }) {
  const [conectando, setConectando] = useState('')
  return (
    <div className="pb-4">
      <p className="text-[14px] text-[#c3cae0] leading-relaxed">
        {t('Conecta una cuenta para guardar tus backups en la nube. ASH solo puede ver y modificar los archivos que crea él mismo.')}
      </p>
      <div className="grid gap-3 mt-5">
        {(nube.proveedores || []).map((p) => (
          <button key={p.clave} disabled={!p.configurado || !!conectando}
            onClick={async () => { setConectando(p.clave); await llamar('nube_conectar', p.clave); setTimeout(() => setConectando(''), 60000) }}
            className="group relative flex items-center gap-4 rounded-2xl px-5 py-4 text-left border transition disabled:opacity-50"
            style={{ borderColor: `${p.color}55`, background: `linear-gradient(90deg, ${p.color}22, transparent)` }}>
            <span className="grid place-items-center size-11 rounded-xl text-white" style={{ background: p.color, boxShadow: `0 0 24px -4px ${p.color}` }}>
              <Cloud size={22} />
            </span>
            <div className="flex-1">
              <div className="text-[15px] font-bold text-white">{p.nombre}</div>
              <div className="text-[12px] text-tenue">{conectando === p.clave ? t('Esperando al inicio de sesión en tu navegador…') : t('Iniciar sesión en el navegador')}</div>
            </div>
            {conectando === p.clave ? <Spinner color={p.color} /> : <span className="text-[13px] font-bold transition group-hover:translate-x-1" style={{ color: p.color }}>{t('Conectar →')}</span>}
          </button>
        ))}
      </div>
      <p className="text-[12px] text-tenue mt-4">{t('Se abrirá la página oficial de inicio de sesión en tu navegador. Solo se puede tener una nube conectada a la vez.')}</p>
    </div>
  )
}

function Descargar({ volver, cerrar }) {
  const [datos, setDatos] = useState(null)
  const [marcados, setMarcados] = useState({})   // idx -> id de copia
  const [buscar, setBuscar] = useState('')
  useEffect(() => { llamar('nube_lista_descarga').then((r) => setDatos(r || { ok: false, error: t('Sin respuesta'), filas: [] })) }, [])
  const filas = useMemo(() => (datos?.filas || []).filter((f) => f.juego.toLowerCase().includes(buscar.trim().toLowerCase())), [datos, buscar])
  const elegidos = Object.keys(marcados)
  const total = elegidos.reduce((s, idx) => {
    const f = datos.filas[idx]; const c = f.copias.find((x) => x.id === marcados[idx])
    return s + (c?.size ?? f.size)
  }, 0)
  const alternar = (f) => setMarcados((m) => {
    const n = { ...m }
    if (n[f.idx] !== undefined) delete n[f.idx]
    else n[f.idx] = f.copias[0]?.id
    return n
  })
  const estados = { igual: [t('Igual que la local'), '#8a93b2'], distinta: [t('Distinta a la local'), '#ffd23f'], no_local: [t('No está en este PC'), '#2ee6a0'] }

  return (
    <div className="pb-3 flex flex-col gap-3 min-h-[380px]">
      <div className="flex items-center gap-2">
        <BotonFantasma className="h-9 px-3 text-[12.5px]" onClick={volver}><ArrowLeft size={15} /> {t('Volver')}</BotonFantasma>
        <label className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-tenue z-10" />
          <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder={t('Buscar…')}
            className="w-full h-9 rounded-lg pl-9 pr-3 text-[13px] text-white bg-black/30 border border-white/10 outline-none focus:border-azul/60" />
        </label>
        <BotonFantasma color="#1de9d0" className="h-9 px-3 text-[12.5px]"
          onClick={() => setMarcados(Object.fromEntries(filas.map((f) => [f.idx, f.copias[0]?.id])))}>{t('Marcar todo')}</BotonFantasma>
        <BotonFantasma className="h-9 px-3 text-[12.5px]" onClick={() => setMarcados({})}>{t('Ninguno')}</BotonFantasma>
      </div>
      {!datos && <div className="grid place-items-center py-16"><Spinner tam={28} color="#3d9bff" /></div>}
      {datos && !datos.ok && <p className="text-rojo text-[13px]">{t('No se pudo cargar la lista: {0}', datos.error)}</p>}
      {datos?.ok && !datos.filas.length && <p className="text-amarillo text-[13px] py-8 text-center">{t('No hay backups en la nube todavía.')}</p>}
      <div className="space-y-1.5 max-h-[46vh] overflow-auto pr-1">
        {filas.map((f) => {
          const on = marcados[f.idx] !== undefined
          const [txt, col] = estados[f.estado] || ['', '#8a93b2']
          return (
            <div key={f.idx} onClick={() => alternar(f)}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 cursor-pointer border transition
                ${on ? 'border-azul/50 bg-azul/[.1]' : 'border-white/[.06] bg-white/[.025] hover:bg-white/[.05]'}`}>
              <span className={`casilla ${on ? 'on' : ''}`} style={on ? { background: '#3d9bff', borderColor: '#3d9bff', boxShadow: '0 0 12px -1px #3d9bff' } : undefined}>
                {on && <Check size={13} strokeWidth={3.5} className="text-black" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-semibold text-white truncate">{f.juego}</div>
                <div className="text-[11.5px] text-tenue">{f.tamano} · {f.copias.length > 1 ? t('{0} copias', f.copias.length) : t('1 copia')}</div>
              </div>
              {f.copias.length > 1 && on ? (
                <select value={marcados[f.idx]} onClick={(e) => e.stopPropagation()}
                  onChange={(e) => setMarcados((m) => ({ ...m, [f.idx]: e.target.value }))}
                  className="h-8 rounded-lg bg-black/40 border border-white/10 text-[12px] text-white px-2 outline-none">
                  {f.copias.map((c, i) => <option key={c.id} value={c.id}>{c.fecha}{i === 0 ? ` ${t('(última)')}` : ''} · {c.tamano}</option>)}
                </select>
              ) : <span className="text-[12px] text-[#c3cae0] font-mono">{f.fecha}</span>}
              <Chip color={col}>{txt}</Chip>
            </div>
          )
        })}
      </div>
      <div className="flex items-center gap-3 pt-1">
        <p className="text-[12px] text-tenue flex-1">
          {t('Se guardan en tu carpeta de backups. Si ya tienes una copia local de ese juego, no se borra: pasa a copia histórica con fecha.')}
        </p>
        <BotonNeon color="#2ee6a0" className="h-10 px-5 text-[13.5px] shrink-0" disabled={!elegidos.length}
          onClick={async () => {
            const ok = await llamar('nube_descargar', elegidos.map((idx) => ({ idx: Number(idx), copia: marcados[idx] })))
            if (ok) cerrar()
          }}>
          <CloudDownload size={17} /> {t('Descargar')} {elegidos.length ? `(${elegidos.length} · ${formatearBytes(total)})` : ''}
        </BotonNeon>
      </div>
    </div>
  )
}

export default function PanelNube({ estado, alCerrar }) {
  const nube = estado?.nube || {}
  const [vista, setVista] = useState('estado')
  const [espacio, setEspacio] = useState(nube.espacio || '')
  const [sinc, setSinc] = useState({ texto: t('Estado de la nube disponible'), ok: true, cargando: false })

  useEffect(() => {
    if (!nube.conectada) return
    llamar('nube_espacio').then((texto) => { if (texto) setEspacio(texto) })
    llamar('nube_preparar')
    setSinc({ texto: t('Sincronizando con {0}…', nube.nombre), ok: true, cargando: true })
    llamar('nube_sincronizar', false).then((r) => setSinc({ texto: r?.texto || t('Sin respuesta'), ok: !!r?.ok, cargando: false }))
  }, [nube.conectada, nube.nombre])

  const cerrar = () => { llamar('nube_cerrar_panel'); alCerrar() }
  const color = nube.conectada ? (nube.color || '#3d9bff') : '#3d9bff'

  return (
    <Modal color={color} icono={<Cloud size={20} />} alCerrar={cerrar} ancho={vista === 'descargar' ? 'max-w-3xl' : 'max-w-xl'}
      titulo={vista === 'descargar' ? t('Descargar backups de {0}', nube.nombre) : t('Nube')}
      subtitulo={vista === 'descargar' ? t('Marca los juegos a descargar. Se verifica cada copia antes de guardarla.') : nube.conectada ? t('Conectado a {0}', nube.nombre) : t('Sin conectar')}>
      {!nube.conectada ? <Conectar nube={nube} /> : vista === 'descargar' ? <Descargar volver={() => setVista('estado')} cerrar={alCerrar} /> : (
        <div className="pb-4 space-y-4">
          <div className="relative rounded-2xl p-4 border overflow-hidden" style={{ borderColor: `${color}44`, background: `linear-gradient(135deg, ${color}1c, transparent 70%)` }}>
            <div className="absolute -right-8 -top-8 size-28 rounded-full blur-2xl opacity-40" style={{ background: color }} />
            <div className="relative flex items-start gap-4">
              <span className="grid place-items-center size-12 rounded-xl text-white shrink-0" style={{ background: color, boxShadow: `0 0 28px -4px ${color}` }}>
                <Cloud size={24} />
              </span>
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="text-[16px] font-bold text-white">{nube.nombre}</div>
                <div className="text-[13px] text-[#c3cae0] truncate">{nube.cuenta || t('Cuenta desconocida')}</div>
                <div className="text-[12.5px] text-tenue">{t('Última subida:')} <b className="text-white/85">{nube.ultima_subida || t('Nunca')}</b></div>
                <div className="text-[12.5px] text-tenue">{espacio || t('Consultando espacio…')}</div>
              </div>
              <BotonFantasma color="#ff4d5e" className="h-8 px-2.5 text-[12px]" onClick={() => llamar('nube_desconectar')}>
                <LogOut size={14} /> {t('Desconectar')}
              </BotonFantasma>
            </div>
            <div className={`relative mt-3 inline-flex items-center gap-2 text-[12.5px] font-semibold ${sinc.ok ? 'text-verde' : 'text-amarillo'}`}>
              {sinc.cargando ? <Spinner tam={13} color="#ffd23f" /> : <span className="size-1.5 rounded-full bg-current shadow-[0_0_8px_currentColor]" />}
              {sinc.texto}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <button onClick={() => { llamar('nube_subir_todo'); alCerrar() }}
              className="group rounded-2xl p-4 text-left border border-azul/30 bg-azul/[.08] hover:bg-azul/[.15] hover:shadow-[0_0_30px_-10px_#3d9bff] transition">
              <CloudUpload size={22} className="text-azul" />
              <div className="mt-2 text-[14px] font-bold text-white">{t('Subir ahora')}</div>
              <div className="text-[11.5px] text-tenue">{t('Las copias locales que falten o hayan cambiado')}</div>
            </button>
            <button onClick={() => setVista('descargar')}
              className="group rounded-2xl p-4 text-left border border-verde/30 bg-verde/[.07] hover:bg-verde/[.14] hover:shadow-[0_0_30px_-10px_#2ee6a0] transition">
              <CloudDownload size={22} className="text-verde" />
              <div className="mt-2 text-[14px] font-bold text-white">{t('Descargar')}</div>
              <div className="text-[11.5px] text-tenue">{t('Traer copias de la nube a este PC')}</div>
            </button>
            <button disabled={sinc.cargando}
              onClick={async () => {
                setSinc({ texto: t('Sincronizando con {0}…', nube.nombre), ok: true, cargando: true })
                const r = await llamar('nube_sincronizar', true)
                setSinc({ texto: r?.texto || t('Sin respuesta'), ok: !!r?.ok, cargando: false })
              }}
              className="group rounded-2xl p-4 text-left border border-morado/30 bg-morado/[.08] hover:bg-morado/[.15] hover:shadow-[0_0_30px_-10px_#b06bff] transition disabled:opacity-50">
              <RefreshCw size={22} className={`text-morado ${sinc.cargando ? 'animate-spin' : ''}`} />
              <div className="mt-2 text-[14px] font-bold text-white">{t('Sincronizar')}</div>
              <div className="text-[11.5px] text-tenue">{t('Actualizar qué copias hay en la nube')}</div>
            </button>
          </div>
          <p className="flex items-center gap-2 text-[12px] text-tenue">
            <Info size={14} className="shrink-0" /> {t('Las subidas automáticas y los límites se configuran en Opciones → Nube.')}
          </p>
        </div>
      )}
    </Modal>
  )
}
