import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Overridable so the proxy still works when the frontend runs in its own
// Docker container: "localhost" there means the frontend container, not
// the backend one. docker-compose.yml sets this to http://backend:8000.
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
const wsTarget = apiTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
    },
  },
  optimizeDeps: {
    include: ['monaco-editor'],
  },
  worker: {
    format: 'es',
  },
})
