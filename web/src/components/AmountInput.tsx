import { Input } from "@/components/ui/input";
import { MAX_AMOUNT, formatGrouped } from "@/lib/format";

interface AmountInputProps {
  id: string;
  value: number | null;
  onChange: (value: number | null) => void;
  required?: boolean;
}

/** Monto en guaraníes: solo enteros, con separador de miles mientras se escribe. */
export function AmountInput({ id, value, onChange, required }: AmountInputProps) {
  return (
    <div className="relative">
      <Input
        id={id}
        inputMode="numeric"
        autoComplete="off"
        required={required}
        className="pr-10 tabular-nums"
        value={value === null ? "" : formatGrouped(value)}
        onChange={(event) => {
          const digits = event.target.value.replace(/\D/g, "");
          if (!digits) {
            onChange(null);
            return;
          }
          const next = Number(digits);
          // Un dígito de más se ignora, en lugar de redondear el monto en silencio.
          if (next <= MAX_AMOUNT) onChange(next > 0 ? next : null);
        }}
      />
      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">
        Gs
      </span>
    </div>
  );
}
