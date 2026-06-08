import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Default proxy matches scripts/pycharm_start.py (--backend-port 8011).
// Override with VITE_API_TARGET=http://127.0.0.1:8000 when running uvicorn directly.
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8011',
        changeOrigin: true,
      },
    },
  },
})
