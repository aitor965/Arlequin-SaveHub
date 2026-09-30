import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// La interfaz se compila en ../web, que es la carpeta que abre ash_web.py.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
  build: {
    outDir: '../web',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
})
