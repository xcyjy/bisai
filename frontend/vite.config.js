import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 把 /api 代理到后端，免去跨域配置
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
