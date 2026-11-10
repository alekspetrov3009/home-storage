import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-сервер фронтенда: порт фиксированный, чтобы совпадать
// с CORS_ORIGINS бэкенда (по умолчанию http://localhost:5173).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
