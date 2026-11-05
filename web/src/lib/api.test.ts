import { afterEach, describe, expect, test, vi } from "vitest";

import { ApiError, createApi } from "./api";

function respond(status: number, body?: unknown) {
  const mock = vi.fn(async () =>
    body === undefined
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => vi.unstubAllGlobals());

describe("createApi", () => {
  test("manda el token y omite los filtros vacíos", async () => {
    const fetchMock = respond(200, { items: [], total: 0, page: 1, page_size: 20 });
    await createApi(() => "abc", vi.fn()).expenses({ from: "2026-11-01", q: "", page: 2 });

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/expenses?from=2026-11-01&page=2");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer abc");
  });

  test("un 401 descarta la sesión", async () => {
    respond(401, { detail: "Sesión inválida o vencida" });
    const onUnauthorized = vi.fn();
    await expect(createApi(() => "x", onUnauthorized).me()).rejects.toThrow(ApiError);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  test("muestra el mensaje de la API", async () => {
    respond(409, { detail: "Ya tenés una categoría con ese nombre" });
    const api = createApi(() => "x", vi.fn());
    await expect(api.createCategory({ name: "a", color: "#000000" })).rejects.toThrow(
      "Ya tenés una categoría con ese nombre",
    );
  });

  test("usa un mensaje en español si el detalle no es texto", async () => {
    respond(422, { detail: [{ loc: ["body"], msg: "field required" }] });
    await expect(createApi(() => "x", vi.fn()).me()).rejects.toThrow("Revisá los datos ingresados");
  });

  test("un 204 no intenta leer JSON", async () => {
    respond(204);
    await expect(createApi(() => "x", vi.fn()).deleteExpense("1")).resolves.toBeUndefined();
  });
});
