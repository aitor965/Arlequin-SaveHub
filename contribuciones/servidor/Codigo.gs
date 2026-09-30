/**
 * Arlequin SaveHub — receptor de "Ayuda a mejorar Arlequin".
 *
 * Google Apps Script vinculado a una hoja de cálculo de la cuenta del
 * proyecto. Recibe los envíos anónimos del programa (rutas aprendidas y
 * juegos sin ruta), los valida y los guarda como filas. Una GitHub Action
 * (contribuciones.yml) los descarga una vez al día con una clave secreta,
 * los coteja con ArlequinGameDB y sube el informe al repositorio.
 *
 * Instalación: ver contribuciones/servidor/INSTRUCCIONES.md
 */

const HOJA = 'Envios';
const CABECERA = ['fecha', 'instalacion', 'app', 'tipo', 'juego', 'launcher', 'id_tienda', 'plantilla', 'origen', 'estado', 'en_bd'];
const MAX_ELEMENTOS = 300;
const MAX_ENVIOS_POR_HORA = 6;       // por instalación
// Hardware de cada equipo (una fila por instalación, se sobrescribe si cambia).
const HOJA_HW = 'Hardware';
const CAMPOS_HW = ['cpu_marca', 'cpu_modelo', 'cpu_nucleos', 'cpu_hilos', 'gpu_marca', 'gpu_modelo', 'gpu_vram_gb', 'gpu_w', 'gpus',
                   'ram_gb', 'ram_tipo', 'ram_mts', 'ram_cl', 'ram_marca', 'ram_modelo', 'ram_modulos', 'so', 'so_build',
                   'nvme_n', 'nvme_gb', 'ssd_n', 'ssd_gb', 'hdd_n', 'hdd_gb', 'steam_deck', 'portatil', 'pantalla', 'pantalla_hz', 'pantallas',
                   'pantalla_modelo', 'pantalla_pulgadas', 'pantalla_panel', 'monitores', 'teclado', 'raton', 'red_tipo', 'red_enlace_mbps',
                   'red_bajada_mbps', 'red_subida_mbps', 'red_ping_ms', 'pais', 'memoria_virtual_gb', 'memoria_virtual_auto'];
const CABECERA_HW = ['fecha', 'instalacion', 'app'].concat(CAMPOS_HW);
// Resumen de cada partida con FPS medidos (una fila por partida).
const HOJA_PARTIDAS = 'Partidas';
const CAMPOS_PARTIDA = ['juego', 'launcher', 'id_tienda', 'dia', 'minutos', 'fps_media', 'fps_mediana', 'fps_1_bajo', 'tirones',
                        'generacion', 'motor', 'calidad', 'calidad_media', 'resolucion', 'pantalla', 'escalado', 'escala_render',
                        'limite_fps', 'vsync', 'trazado_rayos', 'cpu', 'gpu', 'vram_gb', 'gpu_w', 'ram_gb', 'ram_mts', 'pantalla_hz', 'so',
                        'monitor', 'gpu_uso_pct', 'cuello', 'ram_max_pct', 'virtual_max_pct', 'vram_max_gb', 'ram_total_gb',
                        'memoria_virtual_gb'];
const CABECERA_PARTIDAS = ['fecha', 'instalacion', 'app'].concat(CAMPOS_PARTIDA);
const MAX_PARTIDAS = 50;
const COMODINES = /^<(home|root|base|winAppData|winLocalAppData|winDocuments|winPublic|winProgramData|winDir|osUserName|storeUserId)>/;

function hoja_() {
  const libro = SpreadsheetApp.getActive();
  let hoja = libro.getSheetByName(HOJA);
  if (!hoja) {
    hoja = libro.insertSheet(HOJA);
    hoja.appendRow(CABECERA);
    hoja.setFrozenRows(1);
  }
  return hoja;
}

function hojaHw_() {
  const libro = SpreadsheetApp.getActive();
  let hoja = libro.getSheetByName(HOJA_HW);
  if (!hoja) {
    hoja = libro.insertSheet(HOJA_HW);
    hoja.appendRow(CABECERA_HW);
    hoja.setFrozenRows(1);
  }
  return hoja;
}

// Guarda (o actualiza) el hardware de una instalación.
function guardarHw_(fecha, instalacion, app, hw) {
  if (!hw || typeof hw !== 'object') return false;
  const fila = [fecha, instalacion, app].concat(CAMPOS_HW.map(function (c) {
    const v = hw[c];
    if (typeof v === 'boolean') return v ? 'si' : 'no';
    if (typeof v === 'number') return isFinite(v) ? v : '';
    if (v && typeof v === 'object') return texto_(JSON.stringify(v), 1000);
    return texto_(v, 120);
  }));
  const cerrojo = LockService.getScriptLock();
  cerrojo.waitLock(10000);
  try {
    const hoja = hojaHw_();
    const encontrada = hoja.getRange('B:B').createTextFinder(instalacion).matchEntireCell(true).findNext();
    const n = encontrada ? encontrada.getRow() : hoja.getLastRow() + 1;
    hoja.getRange(n, 1, 1, CABECERA_HW.length).setValues([fila]);
  } finally {
    cerrojo.releaseLock();
  }
  return true;
}

function hojaPartidas_() {
  const libro = SpreadsheetApp.getActive();
  let hoja = libro.getSheetByName(HOJA_PARTIDAS);
  if (!hoja) {
    hoja = libro.insertSheet(HOJA_PARTIDAS);
    hoja.appendRow(CABECERA_PARTIDAS);
    hoja.setFrozenRows(1);
  }
  return hoja;
}

function valor_(v) {
  if (typeof v === 'boolean') return v ? 'si' : 'no';
  if (typeof v === 'number') return isFinite(v) ? v : '';
  return texto_(v, 120);
}

function guardarPartidas_(fecha, instalacion, app, partidas) {
  if (!Array.isArray(partidas) || !partidas.length) return 0;
  const filas = partidas.slice(0, MAX_PARTIDAS).filter(function (p) {
    return p && typeof p === 'object' && typeof p.fps_media === 'number' && p.fps_media > 0 && p.fps_media < 2000;
  }).map(function (p) {
    return [fecha, instalacion, app].concat(CAMPOS_PARTIDA.map(function (c) { return valor_(p[c]); }));
  });
  if (filas.length) {
    const hoja = hojaPartidas_();
    hoja.getRange(hoja.getLastRow() + 1, 1, filas.length, CABECERA_PARTIDAS.length).setValues(filas);
  }
  return filas.length;
}

function respuesta_(datos) {
  return ContentService.createTextOutput(JSON.stringify(datos)).setMimeType(ContentService.MimeType.JSON);
}

function texto_(valor, max) {
  return String(valor == null ? '' : valor).replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, max || 200);
}

function doPost(e) {
  try {
    const datos = JSON.parse(e.postData.contents);
    if (!datos || datos.version !== 1) return respuesta_({ ok: false, error: 'versión no admitida' });
    const instalacion = texto_(datos.instalacion, 64);
    if (!/^[0-9a-f]{32}$/.test(instalacion)) return respuesta_({ ok: false, error: 'instalación no válida' });

    // Límite de envíos por instalación, para que nadie llene la hoja.
    const cache = CacheService.getScriptCache();
    const clave = 'envios_' + instalacion;
    const envios = Number(cache.get(clave) || 0);
    if (envios >= MAX_ENVIOS_POR_HORA) return respuesta_({ ok: false, error: 'demasiados envíos' });
    cache.put(clave, String(envios + 1), 3600);

    const fecha = new Date();
    const app = texto_(datos.app, 30);
    const filas = [];
    (Array.isArray(datos.rutas) ? datos.rutas : []).slice(0, MAX_ELEMENTOS).forEach(function (r) {
      const plantilla = texto_(r.plantilla, 300).replace(/\\/g, '/');
      // Solo plantillas con comodín: nunca rutas absolutas del equipo.
      if (!COMODINES.test(plantilla) || /[a-z]:\//i.test(plantilla)) return;
      filas.push([fecha, instalacion, app, 'ruta', texto_(r.juego), texto_(r.launcher, 40), texto_(r.id_tienda, 40),
                  plantilla, texto_(r.origen, 20), '', '']);
    });
    (Array.isArray(datos.sin_ruta) ? datos.sin_ruta : []).slice(0, MAX_ELEMENTOS).forEach(function (j) {
      filas.push([fecha, instalacion, app, 'sin_ruta', texto_(j.juego), texto_(j.launcher, 40), texto_(j.id_tienda, 40),
                  '', '', texto_(j.estado, 40), j.en_bd ? 'si' : 'no']);
    });
    if (filas.length) {
      const hoja = hoja_();
      hoja.getRange(hoja.getLastRow() + 1, 1, filas.length, CABECERA.length).setValues(filas);
    }
    const hw = guardarHw_(fecha, instalacion, app, datos.hw);
    const partidas = guardarPartidas_(fecha, instalacion, app, datos.partidas);
    return respuesta_({ ok: true, guardadas: filas.length, hw: hw, partidas: partidas });
  } catch (err) {
    return respuesta_({ ok: false, error: 'petición no válida' });
  }
}

// Solo para la GitHub Action: devuelve todas las filas si la clave coincide
// con la propiedad CLAVE del script (Configuración del proyecto -> Propiedades).
function doGet(e) {
  const clave = PropertiesService.getScriptProperties().getProperty('CLAVE');
  if (!clave || !e || !e.parameter || e.parameter.clave !== clave) {
    return respuesta_({ ok: false, error: 'no autorizado' });
  }
  const hoja = e.parameter.hoja === 'hardware' ? hojaHw_() : e.parameter.hoja === 'partidas' ? hojaPartidas_() : hoja_();
  const valores = hoja.getDataRange().getValues();
  const cabecera = valores.shift();
  const filas = valores.map(function (fila) {
    const o = {};
    cabecera.forEach(function (c, i) { o[c] = fila[i] instanceof Date ? fila[i].toISOString() : fila[i]; });
    return o;
  });
  return respuesta_({ ok: true, filas: filas });
}
