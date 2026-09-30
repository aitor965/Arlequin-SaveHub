import { useEffect, useLayoutEffect, useRef, useState } from 'react'

// Menú flotante en la posición del ratón. `elementos`: [{texto, icono, color, onClick, desactivado} | '-']
export default function MenuContextual({ x, y, titulo, elementos, alCerrar }) {
  const ref = useRef(null)
  const [pos, setPos] = useState({ left: x, top: y })

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setPos({
      left: Math.min(x, window.innerWidth - r.width - 8),
      top: Math.min(y, window.innerHeight - r.height - 8),
    })
  }, [x, y])

  useEffect(() => {
    const fuera = (e) => { if (ref.current && !ref.current.contains(e.target)) alCerrar() }
    const tecla = (e) => { if (e.key === 'Escape') alCerrar() }
    window.addEventListener('mousedown', fuera)
    window.addEventListener('keydown', tecla)
    window.addEventListener('resize', alCerrar)
    return () => {
      window.removeEventListener('mousedown', fuera)
      window.removeEventListener('keydown', tecla)
      window.removeEventListener('resize', alCerrar)
    }
  }, [alCerrar])

  return (
    <div ref={ref} className="fixed z-[60] min-w-[250px] max-w-[340px] cristal-fuerte rounded-2xl p-1.5 aparecer"
      style={{ left: pos.left, top: pos.top }} onContextMenu={(e) => e.preventDefault()}>
      {titulo && <div className="px-3 pt-2 pb-2 text-[12px] font-bold text-naranja truncate border-b border-white/5 mb-1">{titulo}</div>}
      {elementos.map((el, i) => (el === '-'
        ? <div key={i} className="my-1 h-px bg-white/[.06]" />
        : (
          <button key={i} disabled={el.desactivado}
            onClick={() => { alCerrar(); el.onClick?.() }}
            className="w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#d6dcef] text-left transition
              enabled:hover:text-white disabled:opacity-35 disabled:cursor-not-allowed group"
            style={{ '--c': el.color || '#8a93b2' }}
            onMouseEnter={(e) => { if (!el.desactivado) e.currentTarget.style.background = `${el.color || '#8a93b2'}1f` }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '' }}>
            {el.icono && <el.icono size={16} style={{ color: el.color }} />}
            <span className="truncate">{el.texto}</span>
          </button>
        )))}
    </div>
  )
}
