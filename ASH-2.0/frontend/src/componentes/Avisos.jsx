import { useEffect } from 'react'
import { CheckCircle2, XCircle, X, CloudDownload } from 'lucide-react'
import { BotonFantasma } from './Basicos.jsx'

function Aviso({ aviso, quitar }) {
  useEffect(() => {
    const t = setTimeout(() => quitar(aviso.id), aviso.error ? 9000 : 6000)
    return () => clearTimeout(t)
  }, [aviso, quitar])
  const color = aviso.error ? '#ff4d5e' : '#2ee6a0'
  const Icono = aviso.error ? XCircle : CheckCircle2
  return (
    <div className="cristal-fuerte aparecer-derecha w-[360px] rounded-2xl p-3.5 pr-9 relative overflow-hidden"
      style={{ boxShadow: `0 0 0 1px ${color}40, 0 20px 50px -15px #000, 0 0 40px -20px ${color}` }}>
      <div className="absolute left-0 top-0 bottom-0 w-1" style={{ background: color, boxShadow: `0 0 12px ${color}` }} />
      <div className="flex gap-3">
        <Icono size={20} style={{ color }} className="shrink-0 mt-0.5" />
        <div className="min-w-0">
          <div className="text-[13.5px] font-bold text-white">{aviso.titulo}</div>
          <div className="text-[12.5px] text-[#c3cae0] texto-pre mt-0.5">{aviso.texto}</div>
        </div>
      </div>
      <button onClick={() => quitar(aviso.id)} className="absolute right-2.5 top-2.5 text-tenue hover:text-white"><X size={15} /></button>
    </div>
  )
}

export function Avisos({ avisos, quitar }) {
  return (
    <div className="fixed right-5 bottom-5 z-[70] flex flex-col gap-2.5 items-end pointer-events-none">
      {avisos.map((a) => <div key={a.id} className="pointer-events-auto"><Aviso aviso={a} quitar={quitar} /></div>)}
    </div>
  )
}

export function ProgresoDescarga({ progreso, cancelar }) {
  if (!progreso?.activo) return null
  const f = progreso.fraccion
  return (
    <div className="fixed left-1/2 -translate-x-1/2 bottom-6 z-[65] w-[520px] cristal-fuerte rounded-2xl p-4 aparecer"
      style={{ boxShadow: '0 0 0 1px #3d9bff55, 0 20px 60px -15px #000, 0 0 50px -20px #3d9bff' }}>
      <div className="flex items-center gap-3">
        <span className="grid place-items-center size-10 rounded-xl bg-azul/20 text-azul shadow-[0_0_20px_-6px_#3d9bff]">
          <CloudDownload size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[13.5px] font-bold text-white truncate">{progreso.juego || 'Descargando de la nube'}</div>
          <div className="text-[12px] text-tenue truncate">{progreso.paso}{f != null ? ` · ${Math.round(f * 100)}%` : ''}</div>
        </div>
        <BotonFantasma color="#ff4d5e" className="h-9 px-3 text-[12.5px]" onClick={cancelar}>Cancelar</BotonFantasma>
      </div>
      <div className={`mt-3 h-2 rounded-full bg-white/[.06] overflow-hidden ${f == null ? 'barra-indeterminada' : ''}`} style={{ '--c': '#3d9bff' }}>
        {f != null && (
          <div className="h-full rounded-full relative overflow-hidden transition-[width] duration-300"
            style={{ width: `${f * 100}%`, background: 'linear-gradient(90deg, #3d9bff, #b06bff)', boxShadow: '0 0 14px #3d9bff' }}>
            <div className="absolute inset-0 destello" />
          </div>
        )}
      </div>
    </div>
  )
}
