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
    return respuesta_({ ok: true, guardadas: filas.length });
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
  const valores = hoja_().getDataRange().getValues();
  const cabecera = valores.shift();
  const filas = valores.map(function (fila) {
    const o = {};
    cabecera.forEach(function (c, i) { o[c] = fila[i] instanceof Date ? fila[i].toISOString() : fila[i]; });
    return o;
  });
  return respuesta_({ ok: true, filas: filas });
}
