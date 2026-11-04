import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "./App";

test("muestra el título de la app en español", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Gestor de gastos" })).toBeTruthy();
});
