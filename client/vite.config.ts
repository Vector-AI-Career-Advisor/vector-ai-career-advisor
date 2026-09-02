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
      proxy: Object.fromEntries(
        ['/auth', '/profile', '/jobs', '/resumes', '/applications', '/agents'].map(prefix => [
          prefix,
          {
            target: 'http://localhost:8000',
            changeOrigin: true,
            // Several of these prefixes (e.g. /jobs, /auth/callback) are also
            // client-side routes. Let full-page navigations fall through to the
            // SPA instead of being proxied to the API (which would 401).
            bypass(req: { headers: Record<string, string | undefined> }) {
              if (req.headers.accept?.includes('text/html')) return '/index.html'
            },
          },
        ]),
      ),
    },
  }
})
