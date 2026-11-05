import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import type { Plugin } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

/**
 * Limita las conexiones a los orígenes exactos de este build. El encabezado de Amplify permite
 * cualquier Function URL de la Región, porque la URL de la API no se conoce al crear la app; el
 * navegador aplica ambas políticas, así que rige la más estricta.
 */
function connectSrcPolicy(): Plugin {
  return {
    name: "connect-src-policy",
    apply: "build",
    transformIndexHtml: {
      order: "pre",
      handler(html, { filename }) {
        const env = loadEnv("production", dirname(filename), "VITE_");
        const urls = [env.VITE_API_URL, env.VITE_COGNITO_AUTHORITY, env.VITE_COGNITO_DOMAIN];
        if (urls.some((url) => !url)) return html;
        const origins = urls.map((url) => new URL(url as string).origin).join(" ");
        const policy = `connect-src 'self' ${origins}`;
        return {
          html,
          tags: [
            {
              tag: "meta",
              attrs: { "http-equiv": "Content-Security-Policy", content: policy },
              injectTo: "head-prepend",
            },
          ],
        };
      },
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    connectSrcPolicy(),
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
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, strictPort: true },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"] },
});
