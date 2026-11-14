import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8998',
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'AstroVitals',
        short_name: 'AstroVitals',
        theme_color: '#040B16',
        background_color: '#040B16',
        display: 'standalone',
      },
    }),
  ],
})