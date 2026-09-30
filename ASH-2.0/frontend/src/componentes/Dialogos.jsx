import { useEffect, useRef, useState } from 'react'
import { Info, AlertTriangle, XCircle, HelpCircle, PencilLine, History, Clock, Copy, Check } from 'lucide-react'
import { Modal, BotonNeon, BotonFantasma, Logo } from './Basicos.jsx'
import { llamar } from '../api.js'
import { t } from '../i18n.js'

const TIPOS = {
  info: { color: '#1de9d0', icono: Info },
  aviso: { color: '#ffd23f', icono: AlertTriangle },
  error: { color: '#ff4d5e', icono: XCircle },
  sino: { color: '#ff9000', icono: HelpCircle },
  sinocancelar: { color: '#ff9000', icono: HelpCircle },
  texto: { color: '#b06bff', icono: PencilLine },
  numero: { color: '#b06bff', icono: PencilLine },
  elegir_backup: { color: '#ff4d5e', icono: History },
}

// Algunos mensajes del motor usan viñetas y líneas en blanco: se respetan.
function Mensaje({ texto }) {
  return <div className="texto-pre text-[14px] leading-relaxed text-[#d6dcef]">{texto}</div>
}

function ElegirBackup({ d, responder }) {
  const [elegida, setElegida] = useState(null)
  const [lista, setLista] = useState(false)
  const reciente = d.opciones.find((o) => o.ruta === d.reciente) || d.opciones[0]
  return (
    <Modal color="#ff4d5e" icono={<History size={20} />} titulo={t('¿Qué copia quieres restaurar?')}
      subtitulo={t('{0} copias de seguridad de “{1}”', d.opciones.length, d.juego)} ancho="max-w-xl" alCerrar={() => responder(null)}
      pie={<>
        <BotonFantasma className="h-10 px-4 text-[13.5px]" onClick={() => responder(null)}>{t('Cancelar')}</BotonFantasma>
        {lista
          ? <BotonNeon color="#ff4d5e" className="h-10 px-5 text-[13.5px]" disabled={!elegida} onClick={() => responder(elegida)}>{t('Restaurar esta copia')}</BotonNeon>
          : <BotonNeon color="#2ee6a0" className="h-10 px-5 text-[13.5px]" onClick={() => responder(reciente?.ruta)}><Clock size={16} /> {t('La más reciente')}</BotonNeon>}
      </>}>
      {!lista ? (
        <div className="space-y-3 pb-3">
          <div className="rounded-xl border border-verde/30 bg-verde/[.07] px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-verde">{t('Recomendado')}</div>
            <div className="text-[14px] font-semibold text-white mt-0.5">{reciente?.etiqueta}</div>
          </div>
          <button onClick={() => setLista(true)} className="text-[13px] font-semibold text-azul hover:text-white transition">
            {t('Elegir otra copia de la lista →')}
          </button>
        </div>
      ) : (
        <div className="space-y-1.5 pb-3">
          {d.opciones.map((o) => (
            <button key={o.ruta} onClick={() => setElegida(o.ruta)} onDoubleClick={() => responder(o.ruta)}
              className={`w-full text-left rounded-xl px-4 py-2.5 text-[13.5px] font-semibold border transition
                ${elegida === o.ruta ? 'border-rojo/60 bg-rojo/[.12] text-white shadow-[0_0_24px_-10px_#ff4d5e]' : 'border-white/[.07] bg-white/[.03] text-[#d6dcef] hover:bg-white/[.06]'}`}>
              {o.etiqueta}
            </button>
          ))}
          <p className="text-[12px] text-tenue pt-1">{t('Antes de restaurar, ASH guarda tu partida actual como “↩️ Antes de restaurar”.')}</p>
        </div>
      )}
    </Modal>
  )
}

function Pregunta({ d, responder }) {
  const tipo = TIPOS[d.clase] || TIPOS.info
  const Icono = tipo.icono
  const [valor, setValor] = useState(d.valor ?? '')
  const refInput = useRef(null)
  const refBoton = useRef(null)
  useEffect(() => {
    const temporizador = setTimeout(() => (refInput.current || refBoton.current)?.focus(), 60)
    return () => clearTimeout(temporizador)
  }, [])

  const esPregunta = d.clase === 'sino' || d.clase === 'sinocancelar'
  const esEntrada = d.clase === 'texto' || d.clase === 'numero'
  const cancelar = () => responder(esPregunta ? (d.clase === 'sinocancelar' ? null : false) : esEntrada ? null : 'ok')

  let pie
  if (esPregunta) {
    pie = <>
      {d.clase === 'sinocancelar' && <BotonFantasma className="h-10 px-4 text-[13.5px]" onClick={() => responder(null)}>{t('Cancelar')}</BotonFantasma>}
      <BotonFantasma color="#ff4d5e" className="h-10 px-5 text-[13.5px]" onClick={() => responder(false)}>{t(d.no || 'No')}</BotonFantasma>
      <BotonNeon ref={refBoton} color="#2ee6a0" className="h-10 px-6 text-[13.5px]" onClick={() => responder(true)}>{t(d.si || 'Sí')}</BotonNeon>
    </>
  } else if (esEntrada) {
    pie = <>
      <BotonFantasma className="h-10 px-4 text-[13.5px]" onClick={() => responder(null)}>{t('Cancelar')}</BotonFantasma>
      <BotonNeon color="#b06bff" className="h-10 px-6 text-[13.5px]" onClick={() => responder(d.clase === 'numero' ? Number(valor) : valor)}>{t('Aceptar')}</BotonNeon>
    </>
  } else {
    pie = <BotonNeon color={tipo.color} className="h-10 px-7 text-[13.5px]" onClick={() => responder('ok')}>{t('Aceptar')}</BotonNeon>
  }

  return (
    <Modal color={tipo.color} icono={<Icono size={20} />} titulo={d.titulo || 'Arlequin SaveHub'}
      alCerrar={cancelar} cerrarConFondo={!esPregunta && !esEntrada} pie={pie} ancho={d.mensaje?.length > 500 ? 'max-w-2xl' : 'max-w-lg'}>
      <div className="pb-3">
        <Mensaje texto={d.mensaje} />
        {esEntrada && (
          <input ref={refInput} value={valor} type={d.clase === 'numero' ? 'number' : 'text'}
            onChange={(e) => setValor(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') responder(d.clase === 'numero' ? Number(valor) : valor) }}
            className="mt-4 w-full h-11 rounded-xl px-3.5 text-[14px] text-white bg-black/30 border border-white/10 outline-none
              focus:border-morado/70 focus:shadow-[0_0_0_3px_rgb(176_107_255_/_.18)] transition" />
        )}
      </div>
    </Modal>
  )
}

function Bienvenida({ d, responder }) {
  const [ubicacion, setUbicacion] = useState('predeterminada')
  const [contribuir, setContribuir] = useState(true)
  const Opcion = ({ valor, titulo, detalle }) => {
    const on = ubicacion === valor
    return (
      <button type="button" onClick={() => setUbicacion(valor)}
        className={`w-full text-left rounded-xl px-4 py-3 border transition flex items-start gap-3
          ${on ? 'border-naranja/60 bg-naranja/[.1] shadow-[0_0_24px_-12px_#ff9000]' : 'border-white/[.07] bg-white/[.03] hover:bg-white/[.06]'}`}>
        <span className="mt-1 size-4 rounded-full border-2 grid place-items-center shrink-0" style={{ borderColor: on ? '#ff9000' : 'rgb(255 255 255 / .3)' }}>
          {on && <span className="size-2 rounded-full bg-naranja" />}
        </span>
        <span className="min-w-0">
          <span className="block text-[13.5px] font-semibold text-white">{titulo}</span>
          {detalle && <span className="block text-[12px] text-tenue font-mono break-all">{detalle}</span>}
        </span>
      </button>
    )
  }
  return (
    <Modal color="#ff9000" ancho="max-w-xl" cerrarConFondo={false}
      pie={<BotonNeon color="#2ee6a0" className="h-11 px-7 text-[14px]"
        onClick={() => responder({ ubicacion, contribuir })}>{t('Empezar')}</BotonNeon>}>
      <div className="pt-6 pb-4 space-y-5">
        <div className="text-center space-y-3">
          <div className="flex justify-center"><Logo grande /></div>
          <p className="text-[14px] text-[#c3cae0]">{t('Bienvenido. Arlequin SaveHub localiza, respalda y restaura las partidas guardadas de tus juegos.')}</p>
        </div>
        {d.necesita_ruta && (
          <section className="space-y-2">
            <h3 className="text-[11px] font-bold tracking-[.14em] uppercase text-naranja">{t('¿Dónde guardamos tus copias?')}</h3>
            <Opcion valor="predeterminada" titulo={t('En el Escritorio (recomendado)')} detalle={d.ruta_predeterminada} />
            <Opcion valor="otra" titulo={t('Elegir otra carpeta…')} />
          </section>
        )}
        <button type="button" onClick={() => setContribuir((v) => !v)}
          className={`w-full text-left rounded-xl px-4 py-3 border transition flex items-start gap-3
            ${contribuir ? 'border-rosa/50 bg-rosa/[.08]' : 'border-white/[.07] bg-white/[.03]'}`}>
          <span className={`casilla mt-0.5 ${contribuir ? 'on' : ''}`}
            style={contribuir ? { background: '#ff5fb8', borderColor: '#ff5fb8', boxShadow: '0 0 12px -1px #ff5fb8' } : undefined}>
            {contribuir && <Check size={13} strokeWidth={3.5} className="text-black" />}
          </span>
          <span className="min-w-0">
            <span className="block text-[13.5px] font-semibold text-white">{t('Ayudar a mejorar Arlequin de forma anónima')}</span>
            <span className="block text-[12px] text-tenue leading-snug mt-0.5">
              {t('Comparte las rutas de guardado que ASH descubre para juegos que la base de datos aún no conoce. Nunca tus partidas ni tu nombre de usuario. Puedes cambiarlo cuando quieras en Opciones.')}
            </span>
          </span>
        </button>
        <p className="text-center">
          <button type="button" className="text-[12.5px] font-semibold text-azul hover:text-white transition"
            onClick={() => llamar('abrir_enlace', 'privacidad')}>{t('¿Qué se envía exactamente?')}</button>
        </p>
      </div>
    </Modal>
  )
}

export function Dialogo({ d, responder }) {
  // Enter acepta en avisos simples.
  useEffect(() => {
    if (!['info', 'aviso', 'error'].includes(d.clase)) return
    const tecla = (e) => { if (e.key === 'Enter') responder('ok') }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [d, responder])
  if (d.clase === 'elegir_backup') return <ElegirBackup d={d} responder={responder} />
  if (d.clase === 'bienvenida') return <Bienvenida d={d} responder={responder} />
  return <Pregunta key={d.id} d={d} responder={responder} />
}

export function TextoLargo({ titulo, texto, alCerrar }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = async () => {
    try { await navigator.clipboard.writeText(texto); setCopiado(true); setTimeout(() => setCopiado(false), 1500) } catch { /* sin portapapeles */ }
  }
  return (
    <Modal color="#1de9d0" icono={<Info size={20} />} titulo={titulo} ancho="max-w-3xl" alCerrar={alCerrar}
      pie={<>
        <BotonFantasma color="#1de9d0" className="h-10 px-4 text-[13px]" onClick={copiar}>
          {copiado ? <Check size={15} /> : <Copy size={15} />} {copiado ? t('Copiado') : t('Copiar')}
        </BotonFantasma>
        <BotonNeon color="#1de9d0" className="h-10 px-6 text-[13.5px]" onClick={alCerrar}>{t('Cerrar')}</BotonNeon>
      </>}>
      <pre className="texto-pre font-mono text-[12.5px] leading-relaxed text-[#cfd6ee] pb-4 select-text">{texto}</pre>
    </Modal>
  )
}
