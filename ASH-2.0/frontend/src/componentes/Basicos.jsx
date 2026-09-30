// Piezas pequeñas reutilizables: logo, anillo de progreso, botones, modal.
import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

export function Logo({ grande = false }) {
  const tam = grande ? 'text-[26px]' : 'text-[19px]'
  return (
    <div className={`flex items-baseline font-extrabold tracking-tight ${tam} leading-none select-none`}>
      <span className="text-[#ff3b3b] brillo-texto">Arlequin</span>
      <span className="text-white ml-[0.28em]">Save</span>
      <span className="ml-[0.18em] rounded-[0.32em] bg-naranja px-[0.22em] py-[0.08em] text-black shadow-[0_0_22px_-4px_#ff9000]">Hub</span>
    </div>
  )
}

// Anillo con brillo de neón. `valor` entre 0 y 1.
export function Anillo({ valor = 0, color = '#ff9000', color2, tam = 92, grosor = 9, children }) {
  const r = (tam - grosor) / 2
  const c = 2 * Math.PI * r
  const v = Math.max(0, Math.min(1, Number(valor) || 0))
  const id = `g${color.replace('#', '')}${(color2 || '').replace('#', '')}${tam}`
  return (
    <div className="relative shrink-0" style={{ width: tam, height: tam }}>
      <svg width={tam} height={tam} className="-rotate-90" style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} />
            <stop offset="100%" stopColor={color2 || color} />
          </linearGradient>
        </defs>
        <circle cx={tam / 2} cy={tam / 2} r={r} fill="none" stroke="rgb(255 255 255 / .07)" strokeWidth={grosor} />
        <circle
          cx={tam / 2} cy={tam / 2} r={r} fill="none" stroke={`url(#${id})`} strokeWidth={grosor}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v)}
          className="anillo-brillo" style={{ '--c': color, transition: 'stroke-dashoffset 1.1s cubic-bezier(.2,.8,.2,1)' }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  )
}

export function BotonNeon({ color = '#ff9000', className = '', children, ...props }) {
  return (
    <button className={`boton-neon ${className}`} style={{ '--c': color }} {...props}>{children}</button>
  )
}

export function BotonFantasma({ color = '#8a93b2', className = '', children, ...props }) {
  return (
    <button className={`boton-fantasma ${className}`} style={{ '--c': color }} {...props}>{children}</button>
  )
}

export function Chip({ color = '#8a93b2', children, className = '', title }) {
  return <span className={`chip ${className}`} style={{ '--c': color }} title={title}>{children}</span>
}

// Pila de modales abiertos: Escape solo cierra el de arriba.
const pilaModales = []

// Ventana modal (diálogos y paneles centrados).
export function Modal({ abierto = true, alCerrar, ancho = 'max-w-lg', color = '#ff9000', icono, titulo, subtitulo,
  children, pie, cerrarConFondo = true }) {
  const refCerrar = useRef(alCerrar)
  refCerrar.current = alCerrar
  useEffect(() => {
    if (!abierto) return
    const yo = {}
    pilaModales.push(yo)
    const tecla = (e) => {
      if (e.key === 'Escape' && pilaModales[pilaModales.length - 1] === yo && refCerrar.current) {
        e.stopPropagation()
        refCerrar.current()
      }
    }
    window.addEventListener('keydown', tecla)
    return () => {
      window.removeEventListener('keydown', tecla)
      pilaModales.splice(pilaModales.indexOf(yo), 1)
    }
  }, [abierto])
  if (!abierto) return null
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-6 fundido"
      style={{ background: 'radial-gradient(ellipse at center, rgb(7 8 15 / .55), rgb(7 8 15 / .85))', backdropFilter: 'blur(3px)' }}
      onMouseDown={(e) => { if (cerrarConFondo && e.target === e.currentTarget && alCerrar) alCerrar() }}>
      <div className={`cristal-fuerte aparecer w-full ${ancho} rounded-3xl overflow-hidden flex flex-col max-h-[88vh]`}
        style={{ boxShadow: `0 0 0 1px ${color}33, 0 30px 90px -20px #000, 0 0 60px -30px ${color}` }}>
        <div className="h-[3px] shrink-0" style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />
        {(titulo || icono) && (
          <div className="flex items-start gap-3 px-6 pt-5 pb-3 shrink-0">
            {icono && (
              <div className="grid place-items-center size-10 rounded-xl shrink-0"
                style={{ background: `${color}22`, color, boxShadow: `0 0 24px -6px ${color}` }}>{icono}</div>
            )}
            <div className="min-w-0 flex-1">
              <h2 className="text-[17px] font-bold text-white leading-tight">{titulo}</h2>
              {subtitulo && <p className="text-[13px] text-tenue mt-1">{subtitulo}</p>}
            </div>
            {alCerrar && (
              <button onClick={alCerrar} className="text-tenue hover:text-white p-1 rounded-lg hover:bg-white/5 transition">
                <X size={18} />
              </button>
            )}
          </div>
        )}
        <div className="px-6 pb-2 overflow-auto min-h-0 flex-1">{children}</div>
        {pie && <div className="px-6 py-4 flex items-center justify-end gap-2 shrink-0 border-t border-white/5 bg-black/10">{pie}</div>}
      </div>
    </div>
  )
}

export function Spinner({ tam = 16, color = '#1de9d0' }) {
  return (
    <svg width={tam} height={tam} viewBox="0 0 24 24" className="animate-spin shrink-0">
      <circle cx="12" cy="12" r="9" fill="none" stroke="rgb(255 255 255 / .12)" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
    </svg>
  )
}
