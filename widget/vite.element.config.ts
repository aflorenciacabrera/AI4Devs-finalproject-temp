import { defineConfig } from "vite";

// Segunda compilación: el Web Component <firmadoc-widget> como un único widget.js autocontenido.
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: false, // conserva la SPA compilada por la primera pasada
    sourcemap: false,
    lib: {
      entry: "src/embed/widgetElement.ts",
      formats: ["iife"],
      name: "FirmadocWidget",
      fileName: () => "widget.js",
    },
  },
});
