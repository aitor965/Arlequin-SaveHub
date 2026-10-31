// Copia de src/rendimiento.js de GameHub (la genera herramientas/textos_web_estadisticas.py): no cambiar aquí.
(function () {
// Procesadores y gráficas de mejor a peor en juegos (orden aproximado, revisado a mano el 04-10-2026).
// Lo usa Estadísticas para ordenar los modelos. Los nombres van como los da Windows (sin (R)/(TM));
// las gráficas de portátil NVIDIA llevan «Laptop GPU». Para añadir uno, ponlo en su sitio de la lista.

const PROCESADORES = `
AMD Ryzen 7 9850X3D
AMD Ryzen 7 9800X3D
AMD Ryzen 9 9950X3D2
AMD Ryzen 9 9950X3D
AMD Ryzen 9 7950X3D
AMD Ryzen 7 7800X3D
AMD Ryzen 7 7700X3D
AMD Ryzen 9 9900X3D
Intel Core Ultra 7 270K Plus
Intel Core i9-14900KS
Intel Core i9-14900K
Intel Core Ultra 9 285K
Intel Core i9-13900KS
Intel Core i7-14700K
Intel Core i9-13900K
AMD Ryzen 9 9955HX3D
AMD Ryzen 9 9950X
AMD Ryzen 7 9700X
AMD Ryzen 9 9900X
AMD Ryzen 9 7900X3D
AMD Ryzen 9 7950X
Intel Core Ultra 7 265K
AMD Ryzen 5 7600X3D
Intel Core i7-13700K
AMD Ryzen 9 7945HX3D
AMD Ryzen 9 7900X
AMD Ryzen 7 7700X
AMD Ryzen 5 9600X
Intel Core Ultra 5 250K Plus
Intel Core Ultra 9 290HX Plus
Intel Core Ultra 9 285HX
Intel Core i9-14900HX
Intel Core i9-13980HX
AMD Ryzen 9 9955HX
AMD Ryzen 7 7700
Intel Core i5-14600K
Intel Core i5-13600K
Intel Core i9-12900KS
Intel Core i9-12900K
AMD Ryzen 7 5800X3D
AMD Ryzen 9 7945HX
Intel Core Ultra 9 275HX
Intel Core i9-13950HX
AMD Ryzen 5 9600
AMD Ryzen 5 7600X
AMD Ryzen 5 7600
AMD Ryzen 5 7500F
Intel Core Ultra 5 245K
Intel Core i7-12700K
AMD Ryzen 7 5700X3D
Intel Core i7-14650HX
Intel Core i7-13700HX
Intel Core i7-13650HX
Intel Core Ultra 7 255HX
AMD Ryzen AI Max+ 395
AMD Ryzen 7 7745HX
AMD Ryzen 5 5600X3D
Intel Core i5-12600K
Intel Core i5-14400
Intel Core i5-13400
AMD Ryzen 9 5950X
AMD Ryzen 9 5900X
AMD Ryzen 7 5800X
AMD Ryzen 7 5700X
AMD Ryzen 7 8700G
AMD Ryzen 9 8945HS
AMD Ryzen 9 7940HS
AMD Ryzen AI 9 HX 370
AMD Ryzen 7 8845HS
AMD Ryzen 7 7840HS
Intel Core i9-13900H
Intel Core Ultra 9 386H
Intel Core Ultra 9 285H
Intel Core Ultra 7 265H
Intel Core Ultra 7 255H
Intel Core i7-13700H
Intel Core i9-12900H
Intel Core Ultra 9 185H
Intel Core Ultra 7 165H
Intel Core Ultra 7 155H
Intel Core i7-13620H
Intel Core i7-12700H
Intel Core i7-12650H
Intel Core i5-12400
AMD Ryzen 5 5600X
AMD Ryzen 5 8600G
AMD Ryzen 7 7735HS
AMD Ryzen 9 6900HX
AMD Ryzen 7 6800H
AMD Ryzen 5 5600
AMD Ryzen 7 8840U
AMD Ryzen 7 7840U
AMD Ryzen Z1 Extreme
AMD Ryzen AI 7 350
Intel Core Ultra 7 258V
Intel Core i5-13500H
Intel Core i5-13420H
Intel Core i5-12500H
Intel Core i5-12450H
Intel Core Ultra 5 125H
Intel Core i3-13100
Intel Core i3-12100
AMD Ryzen 9 5900HX
AMD Ryzen 7 5800H
AMD Ryzen 5 8645HS
AMD Ryzen 5 7640HS
AMD Ryzen 5 6600H
AMD Ryzen 5 7640U
Intel Core i9-11900K
Intel Core i7-11700K
Intel Core i7-11700
Intel Core i5-11600K
Intel Core i7-11800H
Intel Core i9-10900K
Intel Core i7-10700K
Intel Core i5-11400
AMD Ryzen 7 5700G
AMD Ryzen 5 5600H
AMD Ryzen 5 7430U
AMD Ryzen 7 7730U
AMD Ryzen 7 5800U
AMD Ryzen 5 5500
AMD Ryzen 5 5600G
AMD Ryzen 5 8500G
Intel Core i5-11400H
Intel Core i7-10700
Intel Core i5-10600K
Intel Core i9-9900K
Intel Xeon E-2288G
Intel Core i7-9700K
AMD Ryzen 7 3800X
AMD Ryzen 7 3700X
Intel Core i7-1360P
Intel Core i7-1255U
Intel Core i5-1335U
Intel Core i5-1235U
AMD Ryzen 5 5600U
AMD Ryzen 5 5625U
AMD Ryzen 7 5700U
AMD Ryzen 5 3600X
AMD Ryzen 5 3600
Intel Core i7-8700K
Intel Core i5-10600
Intel Core i5-10400
Intel Core i3-10100
Intel Core i7-9700
Intel Core i7-8700
Intel Xeon E-2176G
Intel Core i7-10750H
Intel Core i7-9750H
AMD Ryzen 7 4800H
AMD Ryzen 5 4600H
Intel Core i7-1165G7
Intel Core i5-1135G7
AMD Ryzen 3 3300X
Intel Core i5-9600K
AMD Ryzen 5 3500X
AMD Ryzen 5 3500
Intel Core i7-7700K
Intel Core i5-9600
Intel Core i7-8750H
Intel Core i5-9400
Intel Core i5-8600K
AMD Ryzen 7 2700X
AMD Ryzen 5 2600X
AMD Ryzen 3 3100
Intel Xeon E3-1270 v6
Intel Core i7-7700
Intel Core i5-8400
AMD Ryzen 7 2700
AMD Ryzen 5 2600
AMD Ryzen 5 1600 AF
Intel Core i5-10300H
Intel Core i7-6700K
Intel Core i3-9100
Intel Core i3-8350K
AMD Custom APU 0932
AMD Custom APU 0405
AMD Ryzen 7 1700X
AMD Ryzen 5 1600X
AMD Ryzen 7 1700
AMD Ryzen 5 1600
Intel Core i5-9300H
Intel Core i7-7700HQ
Intel Core i5-7600K
Intel Core i7-4790K
Intel Xeon E3-1245 v5
Intel Core i7-6700
Intel Core i5-7600
Intel Core i5-8300H
Intel Core i3-8100
Intel Core i5-6600K
Intel Core i5-7500
Intel Core i7-4790
Intel Core i7-7700T
Intel Core i5-6600
Intel Core i7-4770K
Intel Xeon E5-1650 v4
Intel Core i7-4770
Intel Core i7-4790S
Intel Core i7-6700HQ
Intel Core i5-7400
Intel Core i5-6500
Intel Xeon E3-1230 v3
AMD Ryzen 5 2400G
Intel Core i5-7300HQ
AMD Ryzen 5 3550H
Intel Core i5-4690K
Intel Core i5-4690
Intel Core i7-4770T
Intel Core i5-6400
Intel Core i5-4670K
Intel Core i5-4590
Intel Core i5-4670
Intel Core i7-3770K
Intel Core i7-3770
Intel Xeon E3-1230 v2
Intel Xeon E5-2680 v4
Intel Xeon E5-2670 v3
Intel Core i5-6300HQ
Intel Core i5-4570
Intel Core i3-7350K
Intel Core i5-4460
Intel Core i5-4440
Intel Core i5-4570S
Intel Core i7-2600K
Intel Core i5-3570K
Intel Core i5-3570
Intel Core i3-7100
Intel Pentium G4620
Intel Pentium G4560
AMD Athlon 3000G
AMD Athlon 200GE
Intel Core i3-6100
AMD FX-9590
AMD FX-9370
AMD FX-8370
AMD FX-8350
Intel Xeon X5675
Intel Xeon X5670
AMD FX-8320
AMD FX-8300
Intel Core i3-4170
Intel Core i3-4160
Intel Xeon X5650
AMD Athlon X4 880K
AMD A10-7890K
AMD Athlon X4 870K
AMD A10-7870K
AMD Athlon X4 860K
AMD A10-7850K
AMD FX-8150
AMD FX-6350
Intel Core i3-4130
AMD FX-6300
Intel Pentium G4500
Intel Pentium G4400
AMD Phenom II X6 1100T
AMD Phenom II X6 1090T
AMD Phenom II X6 1075T
AMD Athlon X4 840
AMD A8-7650K
AMD Athlon X4 750K
AMD A10-6800K
AMD Phenom II X6 1055T
Intel Pentium G3258
Intel Core i3-3250
Intel Core i3-3220
AMD A10-5800K
AMD A8-6600K
AMD Phenom II X4 980
AMD Phenom II X4 975
Intel Core i3-2120
AMD Phenom II X4 965
AMD A8-5600K
AMD Phenom II X4 955
Intel Pentium G3220
Intel Core 2 Extreme QX9775
Intel Core 2 Extreme QX9770
Intel Core 2 Quad Q9650
Intel Core 2 Extreme QX9650
AMD Athlon II X4 645
AMD A8-3870K
AMD Athlon II X4 640
Intel Pentium G2130
Intel Core 2 Quad Q9550
AMD Athlon II X4 635
Intel Pentium G2020
AMD Athlon II X4 630
AMD A6-3670K
Intel Core 2 Quad Q9450
Intel Core 2 Quad Q9400
Intel Celeron G1620
Intel Pentium G870
Intel Celeron G1610
Intel Pentium G860
Intel Core 2 Quad Q8400
Intel Core 2 Quad Q8300
Intel Core 2 Quad Q6600
Intel Celeron G550
Intel Celeron G540
Intel Celeron G530
Intel Core 2 Duo E8600
Intel Core 2 Duo E8500
Intel Core 2 Duo E8400
Intel Core 2 Duo E7600
Intel Core 2 Duo E7500
Intel Core 2 Duo E7400
`

const GRAFICAS = `
NVIDIA GeForce RTX 5090
NVIDIA GeForce RTX 4090
NVIDIA GeForce RTX 5080
AMD Radeon RX 7900 XTX
NVIDIA GeForce RTX 4080 Super
NVIDIA GeForce RTX 4080
NVIDIA GeForce RTX 5070 Ti
AMD Radeon RX 9070 XT
AMD Radeon RX 7900 XT
NVIDIA GeForce RTX 4070 Ti Super
NVIDIA GeForce RTX 5090 Laptop GPU
AMD Radeon RX 9070
NVIDIA GeForce RTX 3090 Ti
NVIDIA GeForce RTX 4070 Ti
NVIDIA GeForce RTX 5070
AMD Radeon RX 7900 GRE
NVIDIA GeForce RTX 4090 Laptop GPU
NVIDIA GeForce RTX 4070 Super
NVIDIA GeForce RTX 3090
AMD Radeon RX 6950 XT
NVIDIA GeForce RTX 5080 Laptop GPU
AMD Radeon RX 9070 GRE
NVIDIA GeForce RTX 3080 Ti
AMD Radeon RX 6900 XT
AMD Radeon RX 7800 XT
NVIDIA GeForce RTX 3080
AMD Radeon RX 6800 XT
NVIDIA GeForce RTX 4070
NVIDIA GeForce RTX 4080 Laptop GPU
AMD Radeon RX 9060 XT 16GB
NVIDIA GeForce RTX 5060 Ti 16GB
AMD Radeon RX 7700 XT
AMD Radeon RX 6800
NVIDIA GeForce RTX 5070 Ti Laptop GPU
NVIDIA GeForce RTX 3070 Ti
AMD Radeon RX 9060 XT 8GB
NVIDIA GeForce RTX 5060 Ti 8GB
AMD Radeon RX 6750 XT
NVIDIA GeForce RTX 4060 Ti 16GB
NVIDIA GeForce RTX 4060 Ti 8GB
NVIDIA GeForce RTX 3070
AMD Radeon 8060S
NVIDIA GeForce RTX 5060
NVIDIA GeForce RTX 2080 Ti
AMD Radeon RX 6700 XT
NVIDIA GeForce RTX 3080 Ti Laptop GPU
NVIDIA GeForce RTX 5070 Laptop GPU
AMD Radeon RX 6700
NVIDIA GeForce RTX 4070 Laptop GPU
NVIDIA GeForce RTX 3060 Ti
NVIDIA GeForce RTX 3080 Laptop GPU
AMD Radeon RX 7600 XT
AMD Radeon RX 6650 XT
NVIDIA GeForce RTX 2080 Super
Intel Arc B580
NVIDIA GeForce RTX 4060
NVIDIA GeForce RTX 5060 Laptop GPU
AMD Radeon RX 7600
NVIDIA GeForce RTX 3070 Ti Laptop GPU
NVIDIA GeForce RTX 5050
NVIDIA GeForce RTX 2080
NVIDIA GeForce RTX 4060 Laptop GPU
AMD Radeon RX 6600 XT
NVIDIA GeForce RTX 3070 Laptop GPU
AMD Radeon RX 6650M XT
Intel Arc A770
Intel Arc B570
NVIDIA GeForce RTX 2070 Super
AMD Radeon RX 5700 XT
NVIDIA GeForce RTX 3060 12GB
Intel Arc A750
AMD Radeon RX 6600
NVIDIA GeForce RTX 4050 Laptop GPU
AMD Radeon RX 6600M
NVIDIA GeForce RTX 2070
AMD Radeon RX 5700
NVIDIA GeForce RTX 2060 Super
NVIDIA GeForce RTX 3060 Laptop GPU
NVIDIA GeForce GTX 1080 Ti
AMD Radeon RX 5600 XT
NVIDIA GeForce RTX 2060
Intel Arc A580
AMD Radeon RX 5700M
NVIDIA GeForce GTX 1080
AMD Radeon RX Vega 64
NVIDIA GeForce GTX 1070 Ti
AMD Radeon RX Vega 56
NVIDIA GeForce RTX 3050
NVIDIA GeForce GTX 980 Ti
NVIDIA GeForce GTX 1660 Ti
NVIDIA GeForce GTX 1070
NVIDIA GeForce GTX 1660 Super
AMD Radeon RX 5600M
AMD Radeon RX 5500 XT
NVIDIA GeForce GTX 1660
AMD Radeon RX 590
AMD Radeon RX 590 GME
NVIDIA GeForce RTX 3050 Ti Laptop GPU
AMD Radeon RX 580
AMD Radeon RX 5500
NVIDIA GeForce GTX 1650 Super
NVIDIA GeForce RTX 3050 Laptop GPU
AMD Radeon RX 6500 XT
AMD Radeon 890M
AMD Radeon RX 580 2048SP
NVIDIA GeForce GTX 1060 6GB
NVIDIA GeForce GTX 980
AMD Radeon RX 570
AMD Radeon RX 5500M
AMD Radeon RX 6500M
AMD Radeon RX 470
NVIDIA GeForce GTX 1060 3GB
AMD Radeon R9 390
NVIDIA GeForce GTX 970
NVIDIA GeForce GTX 1650 Ti
AMD Radeon 880M
AMD Radeon RX 6400
AMD Radeon R9 290X
AMD Radeon RX 5300
NVIDIA GeForce GTX 1650
AMD Radeon R9 380X
NVIDIA GeForce GTX 780 Ti
Intel Arc A380
AMD Radeon R9 290
AMD Radeon 860M
NVIDIA GeForce GTX 980M
AMD Radeon R9 380
Intel Arc 140V
AMD Radeon 780M
NVIDIA GeForce GTX 780
Intel Arc 140T
Intel Arc A370M
NVIDIA GeForce GTX 1050 Ti
AMD Radeon R9 280X
NVIDIA GeForce GTX 960
NVIDIA GeForce GTX 770
Intel Arc 130V
AMD Radeon 680M
AMD Radeon HD 7970
AMD Radeon RX 560
AMD Custom GPU 0932
AMD Custom GPU 0405
AMD Radeon HD 7950
AMD Radeon RX 560X
NVIDIA GeForce GTX 1050
NVIDIA GeForce GTX 760
AMD Radeon R9 270X
NVIDIA GeForce GTX 950
AMD Radeon 760M
AMD Radeon RX 460
AMD Radeon R7 370
AMD Radeon R9 270
AMD Radeon HD 7870
NVIDIA GeForce GTX 660 Ti
AMD Radeon HD 7850
NVIDIA GeForce GTX 660
NVIDIA GeForce GTX 750 Ti
NVIDIA GeForce GTX 650 Ti Boost
AMD Radeon R7 260X
AMD Radeon RX 550
NVIDIA GeForce MX450
NVIDIA GeForce GTX 950M
AMD Radeon 740M
AMD Radeon R7 260
NVIDIA GeForce GTX 750
NVIDIA GeForce GTX 650 Ti
AMD Radeon HD 7770
AMD Radeon R7 250X
AMD Radeon 660M
Intel Iris Xe Graphics
NVIDIA GeForce GT 1030
AMD Radeon Vega 8
AMD Radeon HD 7750
AMD Radeon Vega 7
NVIDIA GeForce MX350
NVIDIA GeForce GTX 650
AMD Radeon Vega 6
NVIDIA GeForce 940MX
AMD Radeon R7 240
Intel UHD Graphics 770
NVIDIA GeForce 930MX
NVIDIA GeForce 920MX
AMD Radeon 610M
AMD Radeon Vega 3
Intel UHD Graphics 750
Intel UHD Graphics 730
Intel UHD Graphics 630
Intel HD Graphics 630
Intel UHD Graphics 620
Intel HD Graphics 620
Intel HD Graphics 530
AMD Radeon R7 Graphics
Intel UHD Graphics 610
Intel HD Graphics 520
Intel UHD Graphics
NVIDIA GeForce GT 740M
NVIDIA GeForce 920M
AMD Radeon R5 Graphics
NVIDIA GeForce GT 730
Intel HD Graphics 4600
NVIDIA GeForce 820M
Intel HD Graphics 4400
NVIDIA GeForce GT 710
Intel HD Graphics 4000
Intel HD Graphics 3000
Intel HD Graphics 2000
`

// «12th Gen Intel(R) Core(TM) i5-12400F» → « intel core i5 12400 » (en procesadores, la F no cuenta).
function normal(nombre, cpu) {
  let s = String(nombre).toLowerCase().replace(/\((r|tm)\)|®|™/g, ' ').replace(/@.*$/, '')
    .replace(/\b\d+(st|nd|rd|th) gen\b/g, ' ').replace(/core2/g, 'core 2').replace(/\b(cpu|processor)\b/g, ' ').replace(/[^a-z0-9]+/g, ' ')
  if (cpu) s = s.replace(/(\d)(k?)f\b/g, '$1$2')
  return ` ${s.trim()} `
}

// Devuelve una función: nombre → puesto en la lista (0 = el mejor) o null si no está.
// Gana el nombre más largo que encaje («RTX 4070 Super» antes que «RTX 4070»), y una gráfica
// de portátil solo encaja con las de portátil. «RX 9060 XT 16GB» también vale sin la memoria.
function puestos(lista, cpu) {
  let claves = null
  return (nombre) => {
    if (!claves) {
      const m = new Map()
      lista.trim().split('\n').forEach((n, i) => {
        for (const k of [normal(n, cpu), normal(n.replace(/\s*\d+GB$/i, ''), cpu)]) if (!m.has(k)) m.set(k, i)
      })
      claves = [...m.entries()]
    }
    const n = normal(nombre, cpu)
    const portatil = n.includes(' laptop ')
    let mejor = null
    for (const [k, i] of claves) {
      if (n.includes(k) && k.includes(' laptop ') === portatil && (!mejor || k.length > mejor[0].length)) mejor = [k, i]
    }
    return mejor ? mejor[1] : null
  }
}

const puestoProcesador = puestos(PROCESADORES, true)
const puestoGrafica = puestos(GRAFICAS, false)

window.RENDIMIENTO = { puestoProcesador: puestoProcesador, puestoGrafica: puestoGrafica }
})()
