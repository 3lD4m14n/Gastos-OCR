import { Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { CategoryBreakdown, MonthlyChart } from "@/components/charts";
import { ExpenseDialog } from "@/components/ExpenseDialog";
import { ExpenseRow } from "@/components/ExpenseRow";
import { ErrorMessage, Field } from "@/components/Field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCategories, useExpenses, useSummary, useToday } from "@/hooks/useApi";
import { formatGs, monthRange } from "@/lib/format";
import { cn } from "@/lib/utils";

type Preset = "current" | "previous" | "custom";

const PRESETS: { value: Preset; label: string }[] = [
  { value: "current", label: "Este mes" },
  { value: "previous", label: "Mes pasado" },
  { value: "custom", label: "Otro rango" },
];

export function Dashboard() {
  const today = useToday();
  const [preset, setPreset] = useState<Preset>("current");
  const [custom, setCustom] = useState(() => monthRange(today));
  const [adding, setAdding] = useState(false);

  const range = useMemo(() => {
    if (preset === "previous") return monthRange(today, 1);
    return preset === "custom" ? custom : monthRange(today);
  }, [preset, custom, today]);

  const summary = useSummary(range);
  const recent = useExpenses({ page_size: 10 }, { refresh: true });
  const categories = useCategories();
  const categoryById = new Map(categories.data?.map((c) => [c.id, c]));

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Período" className="flex gap-1">
          {PRESETS.map(({ value, label }) => (
            <Button
              key={value}
              size="sm"
              variant={preset === value ? "default" : "outline"}
              aria-pressed={preset === value}
              onClick={() => setPreset(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <Button size="sm" className="ml-auto" onClick={() => setAdding(true)}>
          <Plus aria-hidden />
          Nuevo gasto
        </Button>
      </div>

      {preset === "custom" && (
        <div className="grid grid-cols-2 gap-3">
          <Field id="range-from" label="Desde">
            <Input
              id="range-from"
              type="date"
              value={custom.from}
              max={custom.to}
              onChange={(e) => e.target.value && setCustom({ ...custom, from: e.target.value })}
            />
          </Field>
          <Field id="range-to" label="Hasta">
            <Input
              id="range-to"
              type="date"
              value={custom.to}
              min={custom.from}
              onChange={(e) => e.target.value && setCustom({ ...custom, to: e.target.value })}
            />
          </Field>
        </div>
      )}

      <ErrorMessage error={summary.error ?? recent.error} />

      <Card className={cn(summary.isPlaceholderData && "opacity-70")}>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Total del período
          </CardTitle>
        </CardHeader>
        <CardContent>
          {summary.data ? (
            <p className="text-3xl font-semibold tabular-nums">{formatGs(summary.data.total)}</p>
          ) : (
            <Skeleton className="h-9 w-48" />
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Por categoría</CardTitle>
          </CardHeader>
          <CardContent>
            {!summary.data && <Skeleton className="h-44 w-full" />}
            {summary.data?.by_category.length === 0 && (
              <p className="text-sm text-muted-foreground">No hay gastos en este período.</p>
            )}
            {!!summary.data?.by_category.length && (
              <CategoryBreakdown categories={summary.data.by_category} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Últimos 6 meses</CardTitle>
          </CardHeader>
          <CardContent>
            {summary.data ? (
              <MonthlyChart months={summary.data.by_month} />
            ) : (
              <Skeleton className="h-52 w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Últimos gastos</CardTitle>
        </CardHeader>
        <CardContent>
          {recent.data?.items.length === 0 && (
            <p className="text-sm text-muted-foreground">Todavía no cargaste ningún gasto.</p>
          )}
          <ul className="grid grid-cols-1 gap-3">
            {recent.data?.items.map((expense) => (
              <li key={expense.id}>
                <ExpenseRow expense={expense} category={categoryById.get(expense.category_id)} />
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <ExpenseDialog open={adding} expense={null} onClose={() => setAdding(false)} />
    </>
  );
}
