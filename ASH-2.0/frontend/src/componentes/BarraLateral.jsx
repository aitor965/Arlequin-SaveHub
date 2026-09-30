import {
  Gamepad2, Cloud, EyeOff, FolderTree, ShieldCheck, Stethoscope, BarChart3, BookOpen, Settings, Heart, FileText,
} from 'lucide-react'
import { Logo } from './Basicos.jsx'

function Entrada({ icono: Icono, texto, color, activo, onClick, extra, title }) {
  return (
    <button onClick={onClick} title={title}
      className={`group relative w-full flex items-center gap-3 rounded-xl px-3 py-[7px] text-[13.5px] font-semibold transition
        ${activo ? 'text-white' : 'text-[#aeb6cf] hover:text-white hover:bg-white/[.04]'}`}
      style={activo ? {
        background: `linear-gradient(90deg, ${color}38, ${color}0a)`,
        boxShadow: `inset 0 0 0 1px ${color}55, 0 0 26px -10px ${color}`,
      } : undefined}>
      {activo && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full" style={{ background: color, boxShadow: `0 0 10px ${color}` }} />}
      <span className="grid place-items-center size-[30px] rounded-lg transition"
        style={{ background: `${color}${activo ? '30' : '14'}`, color }}>
        <Icono size={17} strokeWidth={2.2} />
      </span>
      <span className="flex-1 text-left truncate">{texto}</span>
      {extra}
    </button>
  )
}

export default function BarraLateral({ estado, abrirPanel, acciones }) {
  const nube = estado?.nube || {}
  return (
    <aside className="relative z-10 w-[236px] shrink-0 h-full flex flex-col cristal border-y-0 border-l-0 rounded-none">
      <div className="px-5 pt-5 pb-4">
        <Logo />
        <div className="mt-2 flex items-center gap-2 text-[11px] font-mono text-tenue">
          <span className="size-1.5 rounded-full bg-verde shadow-[0_0_8px_#2ee6a0] pulso" />
          v{estado?.version || '2.0'}
        </div>
      </div>

      <nav className="flex-1 overflow-auto px-3 space-y-1">
        <p className="px-3 pt-1 pb-2 text-[10.5px] font-bold tracking-[.14em] text-tenue/70 uppercase">Principal</p>
        <Entrada icono={Gamepad2} texto="Mis partidas" color="#ff9000" activo />
        <Entrada icono={Cloud} texto="Nube" color={nube.conectada ? (nube.color || '#3d9bff') : '#3d9bff'}
          onClick={() => abrirPanel('nube')}
          extra={nube.conectada
            ? <span className="size-2 rounded-full bg-verde shadow-[0_0_8px_#2ee6a0]" title={`Conectado a ${nube.nombre}`} />
            : <span className="text-[10px] text-tenue">Conectar</span>} />

        <p className="px-3 pt-3 pb-1.5 text-[10.5px] font-bold tracking-[.14em] text-tenue/70 uppercase">Gestionar</p>
        <Entrada icono={EyeOff} texto="Juegos ocultos" color="#ff5fb8" onClick={() => abrirPanel('ocultos')}
          extra={estado?.ocultos ? <span className="text-[11px] font-mono text-tenue">{estado.ocultos}</span> : null} />
        <Entrada icono={FolderTree} texto="Juegos sin launcher" color="#b06bff" onClick={() => abrirPanel('sinlauncher')} />
        <Entrada icono={ShieldCheck} texto="Verificar copias" color="#2ee6a0" onClick={acciones.verificarTodas} />
        <Entrada icono={Stethoscope} texto="Diagnóstico" color="#1de9d0" onClick={() => acciones.diagnostico()} />
        <Entrada icono={BarChart3} texto="Estadísticas BD" color="#ffd23f" onClick={acciones.estadisticas} />

        <p className="px-3 pt-3 pb-1.5 text-[10.5px] font-bold tracking-[.14em] text-tenue/70 uppercase">Ayuda</p>
        <Entrada icono={BookOpen} texto="Instrucciones" color="#3d9bff" onClick={acciones.instrucciones} />
        <Entrada icono={FileText} texto="Registro (log)" color="#8a93b2" onClick={acciones.abrirLog} />
      </nav>

      <div className="p-3 space-y-1 border-t border-white/5">
        <Entrada icono={Settings} texto="Opciones" color="#aeb6cf" onClick={acciones.opciones} />
        <Entrada icono={Heart} texto="Apoyar el proyecto" color="#ff4d5e" onClick={() => abrirPanel('donar')} />
        <p className="px-3 pt-1 text-[11px] text-tenue italic">by aitor965</p>
      </div>
    </aside>
  )
}
