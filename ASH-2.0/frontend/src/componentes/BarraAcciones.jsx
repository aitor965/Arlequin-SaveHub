import { Save, RotateCcw, CloudUpload, EyeOff, CheckSquare, Square, FolderOpen, FolderCog } from 'lucide-react'
import { BotonNeon, BotonFantasma, Spinner } from './Basicos.jsx'
import { formatearBytes } from '../util.js'

export default function BarraAcciones({ estado, seleccionados, todosMarcados, alternarTodos, acciones }) {
  const n = seleccionados.length
  const escaneando = !!estado?.escaneando
  const hayCopia = seleccionados.some((j) => j.local > 0)
  const nube = estado?.nube || {}
  const tarea = estado?.tarea
  return (
    <div className="flex flex-col gap-2.5">
      <div className="cristal rounded-2xl px-3 py-2.5 flex items-center gap-2.5">
        <BotonFantasma color="#b06bff" className="h-11 px-3.5 text-[13px] whitespace-nowrap shrink-0" onClick={alternarTodos} disabled={escaneando}>
          {todosMarcados ? <Square size={16} /> : <CheckSquare size={16} />}
          {todosMarcados ? 'Deseleccionar' : 'Seleccionar todos'}
        </BotonFantasma>
        <div className="px-2 min-w-0 shrink">
          <div className={`text-[13.5px] font-bold ${n ? 'text-amarillo' : 'text-tenue'}`}>
            {n ? `${n} juego${n === 1 ? '' : 's'} seleccionado${n === 1 ? '' : 's'}` : 'Ningún juego seleccionado'}
          </div>
          <div className="text-[11px] text-tenue truncate">clic: marcar · doble clic: detalles · clic derecho: más</div>
        </div>
        <div className="flex-1" />
        <BotonFantasma color="#ff9000" className="h-11 px-4 text-[13.5px] whitespace-nowrap" disabled={!n || escaneando} onClick={acciones.ocultar}>
          <EyeOff size={17} /> Ocultar
        </BotonFantasma>
        <BotonFantasma color="#3d9bff" className="h-11 px-4 text-[13.5px]" disabled={!n || escaneando || !hayCopia}
          onClick={acciones.subirNube} title={nube.conectada ? `Subir a ${nube.nombre}` : 'Conecta una nube primero'}>
          <CloudUpload size={17} /> Subir
        </BotonFantasma>
        <BotonNeon color="#2ee6a0" className="h-11 px-6 text-[14.5px] min-w-[150px] whitespace-nowrap" disabled={!n || escaneando} onClick={acciones.respaldar}>
          <Save size={18} /> Respaldar
        </BotonNeon>
        <BotonNeon color="#ff4d5e" className="h-11 px-6 text-[14.5px] min-w-[150px] whitespace-nowrap" disabled={!n || escaneando || !hayCopia} onClick={acciones.restaurar}>
          <RotateCcw size={18} /> Restaurar
        </BotonNeon>
      </div>

      <div className="flex items-center gap-3 px-1 text-[12px] text-tenue min-h-[22px]">
        <FolderOpen size={14} className="text-naranja shrink-0" />
        <span className="truncate font-mono" title={estado?.ruta_backups}>{estado?.ruta_backups}</span>
        {estado?.disco && (
          <span className="shrink-0 text-[11.5px] font-semibold text-[#c3cae0]" title="Espacio libre en el disco de la carpeta de backups">
            · {formatearBytes(estado.disco.libre)} libres en {estado.disco.unidad}
          </span>
        )}
        <button onClick={acciones.abrirBackups} className="font-semibold text-azul hover:text-white transition shrink-0">Abrir</button>
        <button onClick={acciones.cambiarBackups} className="font-semibold text-turquesa hover:text-white transition shrink-0 inline-flex items-center gap-1">
          <FolderCog size={13} /> Cambiar
        </button>
        <div className="flex-1" />
        {tarea && (
          <span className="inline-flex items-center gap-2 text-turquesa font-semibold shrink-0 aparecer">
            <Spinner tam={14} /> {tarea}
          </span>
        )}
        {!tarea && estado?.textos?.launchers?.texto && (
          <span className="truncate max-w-[55%] text-right" title={estado.textos.launchers.texto}>{estado.textos.launchers.texto}</span>
        )}
      </div>
    </div>
  )
}
