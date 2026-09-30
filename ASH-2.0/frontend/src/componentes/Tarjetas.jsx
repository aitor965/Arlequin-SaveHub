import { useMemo } from 'react'
import { Gamepad2, ShieldCheck, Cloud, HardDrive, CloudOff } from 'lucide-react'
import { Anillo, BotonFantasma } from './Basicos.jsx'
import { juegosDe, colorTienda, formatearBytes, fechaRelativa } from '../util.js'
import { t } from '../i18n.js'

function Tarjeta({ color, icono: Icono, titulo, children, destacada = false, onClick }) {
  return (
    <div onClick={onClick}
      className={`relative cristal rounded-2xl p-4 overflow-hidden flex flex-col min-h-[132px] ${destacada ? 'borde-arlequin' : ''}
        ${onClick ? 'cursor-pointer hover:-translate-y-0.5 transition' : ''}`}>
      <div className="absolute -right-10 -top-10 size-32 rounded-full blur-3xl opacity-25 pointer-events-none" style={{ background: color }} />
      <div className="flex items-center justify-between relative">
        <span className="text-[11px] font-bold tracking-[.12em] uppercase text-tenue">{t(titulo)}</span>
        <span className="grid place-items-center size-8 rounded-lg" style={{ background: `${color}22`, color, boxShadow: `0 0 18px -6px ${color}` }}>
          <Icono size={16} strokeWidth={2.3} />
        </span>
      </div>
      <div className="relative flex-1 flex">{children}</div>
    </div>
  )
}

export default function Tarjetas({ tabla, estado, abrirPanel, setFiltro }) {
  const d = useMemo(() => {
    const todos = juegosDe(tabla?.arbol)
    const juegos = todos.filter((j) => j.respaldable)
    const conCopia = juegos.filter((j) => j.local > 0)
    const enNube = juegos.filter((j) => j.nube > 0)
    const porTienda = {}
    for (const j of juegos) porTienda[j.tienda || 'Otros'] = (porTienda[j.tienda || 'Otros'] || 0) + 1
    const tiendas = Object.entries(porTienda).sort((a, b) => b[1] - a[1])
    const bytes = juegos.reduce((s, j) => s + (j.tamano_bytes || 0), 0)
    const ultimo = Math.max(0, ...todos.map((j) => j.ultimo_ts || 0))
    return { total: juegos.length, conCopia: conCopia.length, enNube: enNube.length, tiendas, bytes, ultimo,
      subidas: conCopia.filter((j) => j.nube > 0).length,
      sinSubir: conCopia.filter((j) => j.nube === 0).length }
  }, [tabla])

  const nube = estado?.nube || {}
  const colorNube = nube.color || '#3d9bff'
  const pctCopia = d.total ? d.conCopia / d.total : 0
  const pctNube = d.conCopia ? d.subidas / d.conCopia : 0

  // Disco de la carpeta de backups: verde con espacio de sobra, amarillo
  // por debajo del 20 % libre y rojo por debajo del 10 %.
  const disco = estado?.disco
  const pctUsado = disco?.total ? Math.min(1, disco.usado / disco.total) : 0
  const pctLibre = 1 - pctUsado
  const colorDisco = pctLibre < 0.1 ? '#ff4d5e' : pctLibre < 0.2 ? '#ffd23f' : '#2ee6a0'

  return (
    <div className="grid grid-cols-4 gap-4">
      <Tarjeta color="#ff9000" icono={Gamepad2} titulo="Partidas detectadas" destacada>
        <div className="flex flex-col justify-end w-full mt-2">
          <div className="text-[38px] font-extrabold leading-none text-white brillo-texto tabular-nums">{d.total}</div>
          <div className="mt-3 flex h-2 w-full overflow-hidden rounded-full bg-white/5">
            {d.tiendas.map(([ti, n]) => (
              <div key={ti} title={`${t(ti)}: ${n}`} style={{ width: `${(n / Math.max(1, d.total)) * 100}%`, background: colorTienda(ti), boxShadow: `0 0 10px ${colorTienda(ti)}` }} />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-tenue">
            {d.tiendas.slice(0, 4).map(([ti, n]) => (
              <span key={ti} className="inline-flex items-center gap-1">
                <span className="size-1.5 rounded-full" style={{ background: colorTienda(ti) }} />{t(ti)} <b className="text-white/80">{n}</b>
              </span>
            ))}
          </div>
        </div>
      </Tarjeta>

      <Tarjeta color="#2ee6a0" icono={ShieldCheck} titulo="Protegidas" onClick={() => setFiltro('Sin copia local')}>
        <div className="flex items-center gap-4 w-full mt-1">
          <Anillo valor={pctCopia} color="#2ee6a0" color2="#1de9d0" tam={84} grosor={8}>
            <span className="text-[17px] font-extrabold text-white tabular-nums">{Math.round(pctCopia * 100)}%</span>
          </Anillo>
          <div className="min-w-0">
            <div className="text-[22px] font-extrabold text-white tabular-nums">{d.conCopia}<span className="text-tenue text-[15px] font-bold">/{d.total}</span></div>
            <div className="text-[12px] text-tenue leading-snug">{t('con copia local')}</div>
            {d.total - d.conCopia > 0 && (
              <div className="text-[11.5px] mt-1 font-semibold text-rojo">{t('{0} sin proteger', d.total - d.conCopia)}</div>
            )}
          </div>
        </div>
      </Tarjeta>

      <Tarjeta color={nube.conectada ? colorNube : '#8a93b2'} icono={nube.conectada ? Cloud : CloudOff} titulo="En la nube"
        onClick={() => abrirPanel('nube')}>
        {nube.conectada ? (
          <div className="flex items-center gap-4 w-full mt-1">
            <Anillo valor={pctNube} color={colorNube} color2="#b06bff" tam={84} grosor={8}>
              <span className="text-[17px] font-extrabold text-white tabular-nums">{Math.round(pctNube * 100)}%</span>
            </Anillo>
            <div className="min-w-0">
              <div className="text-[15px] font-bold truncate" style={{ color: colorNube }}>{nube.nombre}</div>
              <div className="text-[12px] text-tenue truncate">{t('{0} juegos subidos', d.enNube)}</div>
              {d.sinSubir > 0
                ? <div className="text-[11.5px] mt-1 font-semibold text-morado">{t('{0} sin subir', d.sinSubir)}</div>
                : <div className="text-[11.5px] mt-1 font-semibold text-verde">{t('Todo al día')}</div>}
            </div>
          </div>
        ) : (
          <div className="flex flex-col justify-end gap-2 w-full">
            <p className="text-[12.5px] text-tenue leading-snug">{t('Guarda tus copias en Google Drive, OneDrive o Dropbox.')}</p>
            <BotonFantasma color="#3d9bff" className="h-8 text-[12.5px] w-fit px-3">{t('Conectar una nube')}</BotonFantasma>
          </div>
        )}
      </Tarjeta>

      <Tarjeta color="#b06bff" icono={HardDrive} titulo="Tus partidas ocupan" onClick={() => setFiltro('Todos')}>
        <div className="flex flex-col justify-end w-full">
          <div className="flex items-end justify-between gap-2">
            <div className="text-[26px] font-extrabold leading-none text-white tabular-nums">{formatearBytes(d.bytes)}</div>
            <div className="text-[11.5px] text-tenue text-right leading-tight">
              {t('Último backup')}<br /><b className="text-white/90">{d.ultimo ? fechaRelativa(d.ultimo) : t('ninguno')}</b>
            </div>
          </div>
          {disco && (
            <div className="mt-3" title={t('Disco de la carpeta de backups ({0}): {1} libres de {2}', disco.unidad, formatearBytes(disco.libre), formatearBytes(disco.total))}>
              <div className="flex justify-between text-[11.5px] mb-1">
                <span className="text-tenue">{t('Disco {0} · de {1}', disco.unidad, formatearBytes(disco.total))}</span>
                <span className="font-bold" style={{ color: colorDisco }}>{t('{0} libres', formatearBytes(disco.libre))}</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/[.07] overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${pctUsado * 100}%`, background: `linear-gradient(90deg, #b06bff, ${colorDisco})`, boxShadow: `0 0 10px ${colorDisco}` }} />
              </div>
            </div>
          )}
        </div>
      </Tarjeta>
    </div>
  )
}
