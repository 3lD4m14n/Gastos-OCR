import { useEffect, useRef } from "react";
import { useAuth } from "react-oidc-context";
import { Navigate, Route, Routes } from "react-router";

import { Layout } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Categories } from "@/pages/Categories";
import { Dashboard } from "@/pages/Dashboard";
import { Expenses } from "@/pages/Expenses";

function FullScreenMessage({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-dvh place-content-center gap-4 p-6 text-center">{children}</main>
  );
}

export function App() {
  const auth = useAuth();
  const redirected = useRef(false);
  const mustSignIn = !auth.isLoading && !auth.isAuthenticated && !auth.error;

  useEffect(() => {
    // La pantalla de login es la de Cognito. La guarda evita un doble redirect en StrictMode.
    if (mustSignIn && !auth.activeNavigator && !redirected.current) {
      redirected.current = true;
      void auth.signinRedirect();
    }
  }, [mustSignIn, auth]);

  if (auth.error) {
    return (
      <FullScreenMessage>
        <h1 className="text-lg font-semibold">No se pudo iniciar sesión</h1>
        <p className="text-sm text-muted-foreground">Probá de nuevo en unos minutos.</p>
        <Button className="mx-auto" onClick={() => void auth.signinRedirect()}>
          Entrar
        </Button>
      </FullScreenMessage>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <FullScreenMessage>
        <p className="text-sm text-muted-foreground" role="status">
          Cargando…
        </p>
      </FullScreenMessage>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="gastos" element={<Expenses />} />
        <Route path="categorias" element={<Categories />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
