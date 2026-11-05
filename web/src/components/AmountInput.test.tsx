import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test, vi } from "vitest";

import { AmountInput } from "./AmountInput";

function Harness({ onChange }: { onChange: (value: number | null) => void }) {
  const [value, setValue] = useState<number | null>(null);
  return (
    <>
      <label htmlFor="monto">Monto</label>
      <AmountInput
        id="monto"
        value={value}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
      />
    </>
  );
}

function type(text: string) {
  fireEvent.change(screen.getByLabelText("Monto"), { target: { value: text } });
}

test("formatea con separador de miles y entrega un entero", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  type("189400");
  expect(onChange).toHaveBeenLastCalledWith(189400);
  expect(screen.getByLabelText<HTMLInputElement>("Monto").value).toBe("189.400");
});

test("descarta decimales y letras como dígitos sueltos", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  type("12a");
  expect(onChange).toHaveBeenLastCalledWith(12);
});

test("vacío o cero no es un monto", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  type("0");
  expect(onChange).toHaveBeenLastCalledWith(null);
});

test("ignora un dígito que supera el máximo", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  type("1000000000000000");
  type("10000000000000000");
  expect(onChange).toHaveBeenLastCalledWith(1_000_000_000_000_000);
});
