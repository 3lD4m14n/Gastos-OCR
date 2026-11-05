import type { Category, Expense } from "@/lib/api";
import { formatDate, formatGs } from "@/lib/format";

export function CategorySwatch({ color }: { color?: string }) {
  return (
    <span
      aria-hidden
      className="inline-block size-3 shrink-0 rounded-full"
      style={{ backgroundColor: color ?? "var(--muted-foreground)" }}
    />
  );
}

export function ExpenseRow({ expense, category }: { expense: Expense; category?: Category }) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <CategorySwatch color={category?.color} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{expense.description}</p>
        <p className="truncate text-xs text-muted-foreground">
          {formatDate(expense.spent_at)} · {category?.name ?? "Sin categoría"}
        </p>
      </div>
      <span className="text-sm font-medium whitespace-nowrap tabular-nums">
        {formatGs(expense.amount)}
      </span>
    </div>
  );
}
