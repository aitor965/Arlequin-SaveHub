// Arlequin GameHub: la AppImage de Linux pesa más de 25 MB (lo máximo de un archivo en Cloudflare), así que está
// partida en descargas/linux/000, 001… y este Worker la entrega entera. Solo corre en /descargas/*.AppImage
// (run_worker_first de wrangler.jsonc); lo demás son archivos estáticos. Los trozos y descargas/linux.json los pone
// herramientas/publicar_linux_web.py del repo de GameHub.
export default {
  async fetch(peticion, env) {
    if (peticion.method !== 'GET' && peticion.method !== 'HEAD') return new Response(null, { status: 405 })
    const url = new URL(peticion.url)
    const datos = await env.ASSETS.fetch(new URL('/descargas/linux.json', url))
    if (!datos.ok) return env.ASSETS.fetch(peticion)
    const linux = await datos.json()
    const nombre = decodeURIComponent(url.pathname.split('/').pop())
    // Con nombre fijo (el botón de la web) o con el de la versión; otro .AppImage, el 404 de siempre.
    if (nombre !== linux.nombre && nombre !== 'Arlequin-GameHub-Linux.AppImage') return env.ASSETS.fetch(peticion)

    const total = linux.size
    let desde = 0
    let hasta = total - 1
    let parcial = false
    // Solo un tramo (bytes=a-b, a-, -n): lo que piden los navegadores y gestores para seguir una descarga.
    const rango = /^bytes=(\d*)-(\d*)$/.exec(peticion.headers.get('Range') || '')
    if (rango && (rango[1] || rango[2])) {
      if (rango[1]) {
        desde = Number(rango[1])
        if (rango[2]) hasta = Math.min(Number(rango[2]), total - 1)
      } else {
        desde = Math.max(total - Number(rango[2]), 0)
      }
      if (desde > hasta || desde >= total) {
        return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${total}` } })
      }
      parcial = true
    }
    const cabeceras = {
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${linux.nombre}"`,
      'Content-Length': String(hasta - desde + 1),
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'public, max-age=300',
      'ETag': `"${linux.sha256 || linux.nombre}"`,
    }
    if (parcial) cabeceras['Content-Range'] = `bytes ${desde}-${hasta}/${total}`
    if (peticion.method === 'HEAD') return new Response(null, { status: parcial ? 206 : 200, headers: cabeceras })

    // Con FixedLengthStream Cloudflare manda Content-Length (el navegador sabe cuánto falta); con otro stream, no.
    const { readable, writable } = new FixedLengthStream(hasta - desde + 1)
    const enviar = async () => {
      let inicio = 0
      for (let i = 0; i < linux.partes.length; i++) {
        const tam = linux.partes[i]
        const fin = inicio + tam - 1
        if (fin >= desde && inicio <= hasta) {
          const parte = await env.ASSETS.fetch(new URL(`/descargas/linux/${String(i).padStart(3, '0')}`, url))
          if (!parte.ok) throw new Error(`falta el trozo ${i}`)
          if (desde <= inicio && fin <= hasta) {
            // Trozo entero: lo pasa Cloudflare sin que el Worker toque los bytes (no gasta CPU).
            await parte.body.pipeTo(writable, { preventClose: true })
          } else {
            await copiar(parte.body, writable, Math.max(desde - inicio, 0), Math.min(hasta, fin) - inicio + 1)
          }
        }
        inicio += tam
      }
    }
    enviar().then(() => writable.close(), (e) => writable.abort(e))
    return new Response(readable, { status: parcial ? 206 : 200, headers: cabeceras })
  },
}

// Del trozo, solo los bytes [saltar, hasta) (el primero o el último de un tramo).
async function copiar(cuerpo, destino, saltar, hasta) {
  const lector = cuerpo.getReader()
  const escritor = destino.getWriter()
  let pos = 0
  try {
    while (pos < hasta) {
      const { done, value } = await lector.read()
      if (done) break
      const a = Math.max(saltar - pos, 0)
      const b = Math.min(value.length, hasta - pos)
      if (b > a) await escritor.write(value.subarray(a, b))
      pos += value.length
    }
  } finally {
    escritor.releaseLock()
    lector.cancel().catch(() => {})
  }
}
