import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// SPA build → core/templates/static/dist for Starlette to serve.
// In dev, proxy /api, /auth, /dashboard, /static to the running Python server.
export default defineConfig({
  plugins: [react()],
  base: "/static/dist/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../core/templates/static/dist"),
    emptyOutDir: true,
    sourcemap: true,
    assetsDir: "assets",
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/dashboard": "http://localhost:8000",
      "/static": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/oauth": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
