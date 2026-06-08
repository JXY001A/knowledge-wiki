import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/chat': 'http://localhost:9400',
      '/admin': 'http://localhost:9400',
    }
  },
  build: { outDir: "build"
})
