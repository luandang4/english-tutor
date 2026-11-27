import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Dev: Vite on :5173 proxies API + WebSocket to FastAPI on :8000.
// Prod: `npm run build` -> dist/, served by FastAPI.
export default defineConfig({
  plugins: [
    react(),
    // Installable app (PWA). The service worker only caches the app shell (built JS / CSS / icons); API,
    // WebSocket and audio always go to the network. New builds wait for the learner to tap "Tải lại".
    VitePWA({
      registerType: 'prompt',
      injectRegister: false,
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'English Tutor',
        short_name: 'English Tutor',
        description: 'Gia sư tiếng Anh AI: hội thoại với Emma, từ vựng, ngữ pháp, viết, ôn thẻ.',
        lang: 'vi',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#0e0a1a',
        theme_color: '#0e0a1a',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
