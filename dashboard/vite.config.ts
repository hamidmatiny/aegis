import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api/audit": {
        target: "http://localhost:8084",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/audit/, ""),
      },
      "/api/policy": {
        target: "http://localhost:8081",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/policy/, ""),
      },
      "/api/agent-gate": {
        target: "http://localhost:8083",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/agent-gate/, ""),
      },
      "/api/redteam": {
        target: "http://localhost:8092",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/redteam/, ""),
      },
    },
  },
});
