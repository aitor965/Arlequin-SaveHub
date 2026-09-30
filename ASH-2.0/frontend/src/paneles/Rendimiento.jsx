import { useMemo, useRef, useState } from 'react'
import { Cpu, MemoryStick, HardDrive, Network, Activity } from 'lucide-react'
import { Modal, BotonNeon } from '../componentes/Basicos.jsx'
import { formatearBytes, decimal } from '../util.js'
import { t } from '../i18n.js'

// Una métrica = una serie, un color de identidad y su formato.
export const METRICAS = [
  { id: 'cpu', texto: 'CPU', icono: Cpu, color: '#1de9d0', valor: (m) => m.cpu,
    formato: (v) => `${decimal((v ?? 0).toFixed(v >= 10 ? 0 : 1))} %` },
  { id: 'ram', texto: 'RAM', icono: MemoryStick, color: '#b06bff', valor: (m) => m.ram,
    formato: (v) => formatearBytes(v) },
  { id: 'disco', texto: 'Disco', icono: HardDrive, color: '#2ee6a0', valor: (m) => m.disco,
    formato: (v) => `${formatearBytes(v)}/s` },
  { id: 'red', texto: 'Red', icono: Network, color: '#3d9bff', valor: (m) => (m.red_subida || 0) + (m.red_bajada || 0),
    formato: (v) => `${formatearBytes(v)}/s` },
]

// Botón compacto de la barra lateral con el consumo actual de ASH.
export function WidgetRendimiento({ datos, onClick }) {
  const a = datos?.actual
  return (
    <button onClick={onClick} title={t('Recursos que está usando Arlequin SaveHub')}
      className="w-full rounded-xl px-3 py-2.5 text-left border border-white/[.07] bg-white/[.025] hover:bg-white/[.05] hover:border-turquesa/40 transition group">
      <div className="flex items-center gap-2 text-[10.5px] font-bold tracking-[.14em] uppercase text-tenue/80 mb-1.5">
        <Activity size={12} className="text-turquesa" /> {t('Rendimiento')}
        <span className="ml-auto size-1.5 rounded-full bg-turquesa shadow-[0_0_8px_#1de9d0] pulso" />
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-1">
        {METRICAS.map((m) => (
          <div key={m.id} className="flex items-center gap-1.5 min-w-0">
            <m.icono size={12} style={{ color: m.color }} className="shrink-0" />
            <span className="text-[11.5px] font-mono text-[#d6dcef] truncate tabular-nums">
              {a ? m.formato(m.valor(a)) : '—'}
            </span>
          </div>
        ))}
      </div>
    </button>
  )
}

// Gráfica de área de una serie con cursor y tooltip al pasar el ratón.
function Grafica({ serie, color, formato, tiempos }) {
  const ref = useRef(null)
  const [hover, setHover] = useState(null)
  const W = 320, H = 96
  const max = Math.max(1e-9, ...serie)
  const n = serie.length
  const puntos = serie.map((v, i) => [n > 1 ? (i / (n - 1)) * W : W, H - 4 - (v / max) * (H - 12)])
  const linea = puntos.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = n ? `${linea} L${W},${H} L0,${H} Z` : ''
  const id = `rel${color.replace('#', '')}`

  const mover = (e) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r || n < 2) return
    const i = Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1))))
    setHover(i)
  }
  const h = hover != null ? puntos[hover] : null
  const segundos = hover != null && tiempos?.length ? Math.round(tiempos[n - 1] - tiempos[hover]) : 0

  return (
    <div ref={ref} className="relative h-[78px] cursor-crosshair" onMouseMove={mover} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity=".35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="0" y1={H - 0.5} x2={W} y2={H - 0.5} stroke="rgb(255 255 255 / .1)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <line x1="0" y1="8" x2={W} y2="8" stroke="rgb(255 255 255 / .05)" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />
        {n > 1 && <path d={area} fill={`url(#${id})`} />}
        {n > 1 && <path d={linea} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
          vectorEffect="non-scaling-stroke" style={{ filter: `drop-shadow(0 0 4px ${color})` }} />}
      </svg>
      <span className="absolute left-0 top-0 text-[10px] font-mono text-tenue/80 bg-[#0d1020]/70 px-1 rounded">{t('máx {0}', formato(max))}</span>
      {n < 2 && <div className="absolute inset-0 grid place-items-center text-[12px] text-tenue">{t('Recogiendo datos…')}</div>}
      {h && (
        <>
          <div className="absolute top-0 bottom-0 w-px bg-white/30 pointer-events-none" style={{ left: `${(h[0] / W) * 100}%` }} />
          <div className="absolute size-2.5 rounded-full border-2 border-[#0d1020] pointer-events-none -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${(h[0] / W) * 100}%`, top: `${(h[1] / H) * 100}%`, background: color }} />
          <div className="absolute -top-8 px-2 py-1 rounded-lg text-[11.5px] font-semibold text-white bg-[#161a30] border border-white/10 whitespace-nowrap pointer-events-none -translate-x-1/2 shadow-lg"
            style={{ left: `${Math.min(88, Math.max(12, (h[0] / W) * 100))}%` }}>
            {formato(serie[hover])} <span className="text-tenue font-normal">· {segundos ? t('hace {0} s', segundos) : t('ahora')}</span>
          </div>
        </>
      )}
    </div>
  )
}

const GRUPOS = [
  { id: 'motor', texto: 'Motor (ASH)' },
  { id: 'interfaz', texto: 'Interfaz (WebView2)' },
  { id: 'copias', texto: 'Copias (robocopy)' },
]

export function PanelRendimiento({ datos, alCerrar }) {
  const historial = useMemo(() => datos?.historial || [], [datos])
  const a = datos?.actual
  const tiempos = historial.map((m) => m.t)

  const detalle = (m) => {
    const serie = historial.map(m.valor)
    const media = serie.length ? serie.reduce((s, v) => s + v, 0) / serie.length : 0
    const maximo = serie.length ? Math.max(...serie) : 0
    return { serie, media, maximo }
  }

  const extra = {
    cpu: a ? t('{0} núcleos · 100 % = todos a tope', datos.nucleos) : '',
    ram: a && datos.ram_total ? t('{0} % de {1}', decimal(((a.ram / datos.ram_total) * 100).toFixed(1)), formatearBytes(datos.ram_total)) : '',
    disco: t('Lectura + escritura (incluye las copias con robocopy)'),
    red: a ? `↑ ${formatearBytes(a.red_subida)}/s · ↓ ${formatearBytes(a.red_bajada)}/s · ${t('total {0}', formatearBytes((datos.red_total?.enviados || 0) + (datos.red_total?.recibidos || 0)))}` : '',
  }

  return (
    <Modal color="#1de9d0" icono={<Activity size={20} />} titulo={t('Rendimiento de Arlequin SaveHub')} ancho="max-w-4xl" alCerrar={alCerrar}
      subtitulo={t('Lo que está usando ASH ahora mismo (el motor, la interfaz y las copias). Últimos 2 minutos.')}
      pie={<BotonNeon color="#1de9d0" className="h-10 px-6 text-[13.5px]" onClick={alCerrar}>{t('Cerrar')}</BotonNeon>}>
      {!datos?.disponible ? (
        <p className="py-10 text-center text-tenue">{t('La medición de recursos solo está disponible en Windows.')}</p>
      ) : (
        <div className="pb-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {METRICAS.map((m) => {
              const d = detalle(m)
              return (
                <section key={m.id} className="rounded-2xl border border-white/[.07] bg-white/[.025] p-4 relative overflow-hidden">
                  <div className="absolute -right-8 -top-8 size-24 rounded-full blur-2xl opacity-25 pointer-events-none" style={{ background: m.color }} />
                  <div className="flex items-start justify-between relative">
                    <div>
                      <div className="flex items-center gap-2 text-[11px] font-bold tracking-[.12em] uppercase text-tenue">
                        <m.icono size={14} style={{ color: m.color }} /> {t(m.texto)}
                      </div>
                      <div className="text-[28px] font-extrabold text-white tabular-nums leading-tight mt-1">
                        {a ? m.formato(m.valor(a)) : '—'}
                      </div>
                    </div>
                    <div className="text-right text-[11.5px] text-tenue leading-relaxed tabular-nums">
                      <div>{t('media')} <b className="text-white/85">{m.formato(d.media)}</b></div>
                      <div>{t('pico')} <b className="text-white/85">{m.formato(d.maximo)}</b></div>
                    </div>
                  </div>
                  <div className="mt-3 relative">
                    <Grafica serie={d.serie} color={m.color} formato={m.formato} tiempos={tiempos} />
                  </div>
                  <p className="mt-2 text-[11.5px] text-tenue relative">{extra[m.id]}</p>
                </section>
              )
            })}
          </div>

          {a?.grupos && (
            <section className="rounded-2xl border border-white/[.07] bg-white/[.025] p-4">
              <h3 className="text-[11px] font-bold tracking-[.12em] uppercase text-tenue mb-2">{t('Por parte del programa')}</h3>
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-tenue text-[11px] uppercase tracking-wider">
                    <th className="text-left font-semibold py-1">{t('Parte')}</th>
                    <th className="text-right font-semibold">{t('Procesos')}</th>
                    <th className="text-right font-semibold">CPU</th>
                    <th className="text-right font-semibold">RAM</th>
                    <th className="text-right font-semibold">{t('Disco')}</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {GRUPOS.map((g) => {
                    const v = a.grupos[g.id] || {}
                    const activo = (v.procesos || 0) > 0
                    return (
                      <tr key={g.id} className={`border-t border-white/[.05] ${activo ? 'text-[#d6dcef]' : 'text-tenue/60'}`}>
                        <td className="py-1.5">{t(g.texto)}</td>
                        <td className="text-right">{v.procesos || 0}</td>
                        <td className="text-right">{METRICAS[0].formato(v.cpu || 0)}</td>
                        <td className="text-right">{formatearBytes(v.ram || 0)}</td>
                        <td className="text-right">{formatearBytes(v.disco || 0)}/s</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="text-[11.5px] text-tenue mt-2">{t('La red se mide solo en el motor: es donde están la nube y las descargas de la base de datos.')}</p>
            </section>
          )}
        </div>
      )}
    </Modal>
  )
}
