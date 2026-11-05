import "@/index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { BrowserRouter } from "react-router";

import { App } from "@/App";
import { ApiError } from "@/lib/api";
import { oidcConfig } from "@/lib/auth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Reintentar no arregla un pedido rechazado: solo los errores del servidor o de red.
      retry: (failures, error) =>
        failures < 2 && !(error instanceof ApiError && error.status < 500),
    },
  },
});

const root = document.getElementById("root");
if (!root) {
  throw new Error("Falta el elemento #root");
}

createRoot(root).render(
  <StrictMode>
    <AuthProvider {...oidcConfig}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProvider>
  </StrictMode>,
);
