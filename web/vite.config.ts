import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/v1': 'http://127.0.0.1:8080',
      '/api': 'http://127.0.0.1:8080',
      '/health': 'http://127.0.0.1:8080',
    },
  },
  preview: {
    port: 4173,
    host: true,
  },
});
