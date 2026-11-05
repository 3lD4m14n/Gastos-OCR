import { expect, test } from "vitest";

import { toSlices } from "./charts";

const category = (index: number, total: number) => ({
  category_id: `c${index}`,
  name: `Categoría ${index}`,
  color: "#000000",
  total,
});

test("hasta seis categorías se muestran sin agrupar", () => {
  const categories = [60, 50, 40, 30, 20, 10].map((total, i) => category(i, total));
  expect(toSlices(categories)).toEqual(categories);
});

test("con más de seis, agrupa el resto sin perder el total", () => {
  const categories = [70, 60, 50, 40, 30, 20, 10].map((total, i) => category(i, total));
  const slices = toSlices(categories);
  expect(slices).toHaveLength(6);
  expect(slices.at(-1)).toMatchObject({ name: "Resto", total: 30 });
  expect(slices.reduce((sum, slice) => sum + slice.total, 0)).toBe(280);
});
