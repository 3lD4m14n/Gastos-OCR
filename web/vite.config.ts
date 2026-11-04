import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Gestor de gastos",
        short_name: "Gastos",
        description: "Registrá tus gastos y escaneá tickets de supermercado.",
        lang: "es",
        start_url: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#0f766e",
        // Provisional: los íconos PNG definitivos son de la Fase 3.
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
      },
    }),
  ],
  server: { port: 5173, strictPort: true },
  test: { environment: "jsdom" },
});
