import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Dev setup for custom domain (e.g. Cloudflare Tunnel).
 *
 * - `VITE_PUBLIC_DOMAIN=teamwb.top` will:
 *   - allow Host header
 *   - configure HMR for https/wss typical tunnel setups
 *
 * If you don't set it, Vite behaves like usual for localhost.
 */
export default defineConfig(({ mode }) => {
  // Avoid relying on Node globals typings (`process`) in TS config.
  const env = loadEnv(mode, '.', '')
  const publicDomain = env.VITE_PUBLIC_DOMAIN?.trim()

  const isCustomDomain = Boolean(publicDomain)

  return {
    plugins: [react()],
    server: {
      host: true,
      // When serving via Cloudflare Tunnel, Host header is your public domain.
      // Vite's host-check is strict, so we disable it when a public domain is configured.
      allowedHosts: isCustomDomain ? true : undefined,
      // Your tunnel config routes `teamwb.top` to localhost:5173.
      port: 5173,
      strictPort: true,
      hmr: isCustomDomain
        ? {
            host: publicDomain!,
            protocol: 'wss',
            clientPort: 443,
          }
        : undefined,
    },
    preview: {
      host: true,
    },
  }
})


