import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  root: fileURLToPath(new URL('./extension', import.meta.url)),
  base: './',
  plugins: [react()],
  build: { outDir: '../dist-extension', emptyOutDir: true, rollupOptions: { input: fileURLToPath(new URL('./extension/sidepanel.html', import.meta.url)) } },
})
