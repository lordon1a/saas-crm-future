import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: '/static/react/',
  server: {
    port: 3000,
    host: true
  },
  build: {
    outDir: '../../sadas/static/react',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'workflow-app.js',
        chunkFileNames: 'workflow-chunks.js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) return 'workflow-app.css'
          return assetInfo.name || 'asset'
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    }
  }
})
