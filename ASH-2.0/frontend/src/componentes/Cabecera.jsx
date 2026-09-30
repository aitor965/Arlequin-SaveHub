import { Search, ScanLine, RefreshCw, FolderPlus, X } from 'lucide-react'
import { BotonNeon, Spinner } from './Basicos.jsx'
import { limpiarEstado, colorEstado } from '../util.js'

function Estado({ dato, titulo }) {
  if (!dato?.texto) return null
  const color = colorEstado(dato.color)
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold truncate max-w-[360px]" title={titulo ? `${titulo}: ${dato.texto}` : dato.texto}
      style={{ color }}>
      <span className="size-1.5 rounded-full shrink-0" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
      <span className="truncate">{limpiarEstado(dato.texto)}</span>
    </span>
  )
}

export default function Cabecera({ estado, busqueda, setBusqueda, acciones, refBuscar }) {
  const t = estado?.textos || {}
  const escaneando = !!estado?.escaneando
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-[26px] font-extrabold tracking-tight text-white leading-tight">
            Mis partidas
          </h1>
          <div className="flex items-center gap-x-4 gap-y-0.5 mt-1 min-w-0 flex-wrap">
            <Estado dato={t.update_status} titulo="Programa" />
            <Estado dato={t.db_stats} titulo="Base de datos" />
            <Estado dato={t.db_status} titulo="Estado" />
          </div>
        </div>

        <label className="relative flex items-center w-[300px] max-w-[26vw] shrink-0 group">
          <Search size={17} className="absolute left-3.5 z-10 pointer-events-none text-tenue group-focus-within:text-naranja transition" />
          <input ref={refBuscar} value={busqueda} onChange={(e) => setBusqueda(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Escape') setBusqueda('') }}
            placeholder="Buscar juego…  (Ctrl+F)"
            className="w-full h-11 rounded-xl pl-10 pr-9 text-[14px] text-white placeholder:text-tenue/70 outline-none cristal
              focus:border-naranja/60 focus:shadow-[0_0_0_3px_rgb(255_144_0_/_.15),0_0_30px_-8px_#ff9000] transition" />
          {busqueda && (
            <button onClick={() => setBusqueda('')} className="absolute right-3 z-10 text-tenue hover:text-white"><X size={16} /></button>
          )}
        </label>

        <BotonNeon color="#b06bff" className="h-11 px-4 text-[13.5px]" onClick={acciones.anadirCarpeta} disabled={escaneando}
          title="Añadir una carpeta de partidas a mano">
          <FolderPlus size={17} /> Añadir
        </BotonNeon>
        <BotonNeon color="#3d9bff" className="h-11 px-4 text-[13.5px] min-w-[128px]" onClick={acciones.escanear} disabled={escaneando}>
          {escaneando ? <Spinner color="#fff" /> : <ScanLine size={17} />} {escaneando ? 'Escaneando' : 'Escanear'}
        </BotonNeon>
        <BotonNeon color="#1de9d0" className="h-11 px-4 text-[13.5px]" onClick={acciones.actualizarTodo}
          title="Comprueba la base de datos y sincroniza la nube">
          <RefreshCw size={17} /> Actualizar
        </BotonNeon>
      </div>
    </header>
  )
}
