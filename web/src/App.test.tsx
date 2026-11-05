import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useAuth } from "react-oidc-context";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { App } from "./App";

vi.mock("react-oidc-context", () => ({ useAuth: vi.fn() }));

const CATEGORY = {
  id: "c1",
  name: "Limpieza",
  color: "#1baf7a",
  icon: null,
  is_default: true,
  is_fallback: false,
};
const FALLBACK = { ...CATEGORY, id: "c2", name: "Otros", is_fallback: true };
const EXPENSE = {
  id: "e1",
  category_id: "c1",
  description: "Lavandina",
  amount: 4500,
  spent_at: "2026-11-05",
  notes: null,
};
const SUMMARY = {
  date_from: "2026-11-01",
  date_to: "2026-11-30",
  total: 189400,
  by_category: [{ category_id: "c1", name: "Limpieza", color: "#1baf7a", total: 189400 }],
  by_month: [{ month: "2026-11", total: 189400 }],
};

function authState(overrides: object) {
  vi.mocked(useAuth).mockReturnValue({
    isLoading: false,
    isAuthenticated: false,
    activeNavigator: undefined,
    error: undefined,
    user: null,
    signinRedirect: vi.fn(async () => {}),
    removeUser: vi.fn(async () => {}),
    revokeTokens: vi.fn(async () => {}),
    ...overrides,
  } as unknown as ReturnType<typeof useAuth>);
}

function signedIn() {
  authState({
    isAuthenticated: true,
    user: { access_token: "token", profile: { email: "persona@example.com" } },
  });
}

function renderApp(route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const posted: unknown[] = [];

beforeEach(() => {
  posted.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, "http://api.test");
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), { status });
      if (init?.method === "POST" && url.pathname.endsWith("/expenses")) {
        posted.push(JSON.parse(String(init.body)));
        return json(EXPENSE, 201);
      }
      if (url.pathname.endsWith("/users/me")) {
        return json({ id: "a", currency: "PYG", timezone: "America/Asuncion" });
      }
      if (url.pathname.endsWith("/categories")) return json([CATEGORY, FALLBACK]);
      if (url.pathname.endsWith("/stats/summary")) return json(SUMMARY);
      if (url.pathname.endsWith("/expenses")) {
        return json({ items: [EXPENSE], total: 1, page: 1, page_size: 20 });
      }
      return json({ detail: "no encontrado" }, 404);
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("sesión", () => {
  test("sin sesión redirige al login de Cognito una sola vez", async () => {
    const signinRedirect = vi.fn(async () => {});
    authState({ signinRedirect });
    renderApp();
    await waitFor(() => expect(signinRedirect).toHaveBeenCalledOnce());
  });

  test("mientras carga no redirige", () => {
    const signinRedirect = vi.fn(async () => {});
    authState({ isLoading: true, signinRedirect });
    renderApp();
    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.getByRole("status").textContent).toBe("Cargando…");
  });

  test("con error no entra en bucle y ofrece reintentar", () => {
    const signinRedirect = vi.fn(async () => {});
    authState({ error: new Error("redirect_mismatch"), signinRedirect });
    renderApp();
    expect(signinRedirect).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeTruthy();
    // El detalle técnico no se muestra al usuario.
    expect(screen.queryByText(/redirect_mismatch/)).toBeNull();
  });
});

describe("con sesión", () => {
  test("el dashboard muestra el total en guaraníes y los últimos gastos", async () => {
    signedIn();
    renderApp();
    expect(await screen.findAllByText("189.400 Gs")).not.toHaveLength(0);
    expect(await screen.findByText("Lavandina")).toBeTruthy();
    expect(screen.getByText("4.500 Gs")).toBeTruthy();
  });

  test("carga un gasto y manda el monto como entero", async () => {
    signedIn();
    renderApp("/gastos");
    fireEvent.click(await screen.findByRole("button", { name: "Nuevo gasto" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Monto"), { target: { value: "25.500" } });
    fireEvent.change(within(dialog).getByLabelText("Descripción"), {
      target: { value: "Detergente" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({
      amount: 25500,
      description: "Detergente",
      category_id: "c1",
      notes: null,
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  test("no guarda sin monto", async () => {
    signedIn();
    renderApp("/gastos");
    fireEvent.click(await screen.findByRole("button", { name: "Nuevo gasto" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Descripción"), { target: { value: "x" } });
    fireEvent.submit(within(dialog).getByRole("button", { name: "Guardar" }).closest("form")!);
    expect(await within(dialog).findByRole("alert")).toBeTruthy();
    expect(posted).toHaveLength(0);
  });

  test("Otros no se puede borrar desde la pantalla", async () => {
    signedIn();
    renderApp("/categorias");
    expect(await screen.findByRole("button", { name: "Borrar Limpieza" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Borrar Otros" })).toBeNull();
    expect(screen.getByRole("button", { name: "Editar Otros" })).toBeTruthy();
  });
});
