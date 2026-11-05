import { useState } from "react";
import type { FormEvent } from "react";

import { AmountInput } from "@/components/AmountInput";
import { ErrorMessage, Field, selectClassName } from "@/components/Field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCategories, useSaveExpense, useToday } from "@/hooks/useApi";
import type { Category, Expense } from "@/lib/api";

interface ExpenseFormProps {
  expense: Expense | null;
  categories: Category[];
  today: string;
  onDone: () => void;
}

export function ExpenseForm({ expense, categories, today, onDone }: ExpenseFormProps) {
  const save = useSaveExpense();
  const [amount, setAmount] = useState<number | null>(expense?.amount ?? null);
  const [description, setDescription] = useState(expense?.description ?? "");
  const [spentAt, setSpentAt] = useState(expense?.spent_at ?? today);
  const [categoryId, setCategoryId] = useState(expense?.category_id ?? categories[0]?.id ?? "");
  const [notes, setNotes] = useState(expense?.notes ?? "");
  const [missingAmount, setMissingAmount] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (amount === null) {
      setMissingAmount(true);
      return;
    }
    setMissingAmount(false);
    save.mutate(
      {
        id: expense?.id,
        input: {
          amount,
          description,
          spent_at: spentAt,
          category_id: categoryId,
          notes: notes.trim() || null,
        },
      },
      { onSuccess: onDone },
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <Field id="expense-amount" label="Monto">
        <AmountInput id="expense-amount" value={amount} onChange={setAmount} />
      </Field>
      {missingAmount && (
        <p role="alert" className="-mt-2 text-sm text-destructive">
          Ingresá un monto mayor a cero
        </p>
      )}
      <Field id="expense-description" label="Descripción">
        <Input
          id="expense-description"
          required
          maxLength={200}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field id="expense-date" label="Fecha">
          <Input
            id="expense-date"
            type="date"
            required
            value={spentAt}
            onChange={(event) => setSpentAt(event.target.value)}
          />
        </Field>
        <Field id="expense-category" label="Categoría">
          <select
            id="expense-category"
            required
            className={selectClassName}
            value={categoryId}
            onChange={(event) => setCategoryId(event.target.value)}
          >
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field id="expense-notes" label="Notas (opcional)">
        <Input
          id="expense-notes"
          maxLength={1000}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </Field>
      <ErrorMessage error={save.error} />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </DialogFooter>
    </form>
  );
}

interface ExpenseDialogProps {
  open: boolean;
  expense: Expense | null;
  onClose: () => void;
}

export function ExpenseDialog({ open, expense, onClose }: ExpenseDialogProps) {
  const categories = useCategories();
  const today = useToday();
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{expense ? "Editar gasto" : "Nuevo gasto"}</DialogTitle>
        </DialogHeader>
        {categories.data && (
          // La clave reinicia el formulario al cambiar de gasto.
          <ExpenseForm
            key={expense?.id ?? "nuevo"}
            expense={expense}
            categories={categories.data}
            today={today}
            onDone={onClose}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
