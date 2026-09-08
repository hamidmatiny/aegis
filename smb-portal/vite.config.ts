import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const base = process.env.VITE_BASE_PATH || "/";

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      "/api/smb": {
        target: "http://127.0.0.1:8093",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/smb/, ""),
      },
      "/v1/chat/completions": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
      "/agent-gate/decide": {
        target: "http://127.0.0.1:8083",
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/agent-gate\/decide\/([^/]+)$/, "/v1/approvals/$1/decide"),
      },
      "/agent-gate": {
        target: "http://127.0.0.1:8083",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agent-gate/, "/v1"),
      },
    },
  },
});
