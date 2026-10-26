/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// El servidor sirve el widget compilado bajo /widget-assets/ (ver backend/src/firmadoc/api/pages.py).
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/widget-assets/" : "/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Sin data: URIs (la CSP de la página no las permite para fuentes) ni estilos en línea.
    assetsInlineLimit: 0,
    cssCodeSplit: false,
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
  },
}));
