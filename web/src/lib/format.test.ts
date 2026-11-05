import { describe, expect, test } from "vitest";

import { formatDate, formatGs, formatMonth, monthRange, parseAmount, todayIn } from "./format";

describe("formatGs", () => {
  test.each([
    [189400, "189.400 Gs"],
    [4500, "4.500 Gs"],
    [400, "400 Gs"],
    [0, "0 Gs"],
    [1_000_000, "1.000.000 Gs"],
  ])("%d se muestra como %s", (amount, expected) => {
    expect(formatGs(amount)).toBe(expected);
  });
});

describe("parseAmount", () => {
  test.each([
    ["189.400", 189400],
    ["4500", 4500],
    ["1.000.000 Gs", 1000000],
    ["", null],
    ["0", null],
    ["abc", null],
    ["9".repeat(17), null],
  ])("%j da %j", (text, expected) => {
    expect(parseAmount(text)).toBe(expected);
  });
});

describe("fechas", () => {
  test("hoy se calcula en Asunción, no en UTC", () => {
    expect(todayIn("America/Asuncion", new Date("2026-12-01T02:00:00Z"))).toBe("2026-11-30");
  });

  test("mes en curso termina hoy", () => {
    expect(monthRange("2026-11-05")).toEqual({ from: "2026-11-01", to: "2026-11-05" });
  });

  test("mes pasado cruza el año y termina el último día", () => {
    expect(monthRange("2026-01-15", 1)).toEqual({ from: "2025-12-01", to: "2025-12-31" });
    expect(monthRange("2024-03-31", 1)).toEqual({ from: "2024-02-01", to: "2024-02-29" });
  });

  test("formatDate no se corre de día", () => {
    expect(formatDate("2026-11-01")).toContain("1");
    expect(formatDate("2026-11-01")).toContain("nov");
  });

  test("formatMonth da el mes abreviado", () => {
    expect(formatMonth("2026-11")).toBe("nov");
  });
});
