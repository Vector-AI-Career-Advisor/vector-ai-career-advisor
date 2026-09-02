declare const process: { cwd: () => string }

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_GOOGLE_CLIENT_ID': JSON.stringify(env.VITE_GOOGLE_CLIENT_ID || ''),
    },
    server: {
      port: 5173,
      proxy: {
        '/auth':         { target: 'http://localhost:8000', changeOrigin: true },
        '/profile':      { target: 'http://localhost:8000', changeOrigin: true },
        '/jobs':         { target: 'http://localhost:8000', changeOrigin: true },
        '/resumes':      { target: 'http://localhost:8000', changeOrigin: true },
        '/applications': { target: 'http://localhost:8000', changeOrigin: true },
        '/agents':       { target: 'http://localhost:8000', changeOrigin: true },
      },
    },
  }
})
