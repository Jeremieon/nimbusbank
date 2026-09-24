import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/auth': 'http://localhost:8001',
      '/api/accounts': 'http://localhost:8002',
      '/api/transfers': 'http://localhost:8003',
      '/api/kyc': 'http://localhost:8004',
      '/api/support': 'http://localhost:8005',
    },
  },
})
