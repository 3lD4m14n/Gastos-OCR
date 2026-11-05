import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CategorySwatch } from "@/components/ExpenseRow";
import type { CategoryTotal, MonthTotal } from "@/lib/api";
import { formatCompact, formatGs, formatMonth, formatPercent } from "@/lib/format";

const REST_COLOR = "#cbd5e1";
/** Más porciones no se distinguen: el resto se agrupa, y la lista siempre muestra todas. */
const MAX_SLICES = 5;

interface Slice {
  name: string;
  color: string;
  total: number;
}

export function toSlices(categories: CategoryTotal[]): Slice[] {
  if (categories.length <= MAX_SLICES + 1) return categories;
  const rest = categories.slice(MAX_SLICES).reduce((sum, c) => sum + c.total, 0);
  return [
    ...categories.slice(0, MAX_SLICES),
    { name: "Resto", color: REST_COLOR, total: rest },
  ];
}

function ChartTooltip({
  active,
  payload,
  title,
}: {
  active?: boolean;
  payload?: readonly { value?: unknown; name?: unknown }[];
  title?: string;
}) {
  const entry = payload?.[0];
  if (!active || !entry) return null;
  return (
    <div className="rounded-md border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-sm">
      <p className="text-muted-foreground">{title ?? String(entry.name)}</p>
      <p className="font-medium tabular-nums">{formatGs(Number(entry.value))}</p>
    </div>
  );
}

export function CategoryBreakdown({ categories }: { categories: CategoryTotal[] }) {
  const total = categories.reduce((sum, c) => sum + c.total, 0);
  const slices = toSlices(categories);
  const folded = slices.length < categories.length;
  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="mx-auto size-44" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="total"
              nameKey="name"
              innerRadius={0}
              outerRadius="100%"
              stroke="var(--card)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((slice) => (
                <Cell key={slice.name} fill={slice.color} />
              ))}
            </Pie>
            <Tooltip content={(props) => <ChartTooltip {...props} />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {folded && (
        <p className="text-xs text-muted-foreground">
          En el gráfico, el gris claro agrupa las categorías menores.
        </p>
      )}
      {/* Hace de leyenda y de vista accesible: el color nunca es la única pista. */}
      <ul className="grid grid-cols-1 gap-2">
        {categories.map((category) => (
          <li key={category.category_id} className="flex items-center gap-2 text-sm">
            <CategorySwatch color={category.color} />
            <span className="min-w-0 flex-1 truncate">{category.name}</span>
            <span className="text-xs text-muted-foreground tabular-nums">
              {formatPercent(total ? category.total / total : 0)}
            </span>
            <span className="font-medium whitespace-nowrap tabular-nums">
              {formatGs(category.total)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MonthlyChart({ months }: { months: MonthTotal[] }) {
  return (
    <>
      <div className="h-52" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={months} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="month"
              tickFormatter={formatMonth}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            />
            <YAxis
              width={44}
              tickFormatter={formatCompact}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            />
            <Tooltip
              cursor={{ fill: "var(--muted)" }}
              content={(props) => (
                <ChartTooltip {...props} title={formatMonth(String(props.label ?? ""))} />
              )}
            />
            <Bar
              dataKey="total"
              fill="var(--primary)"
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted-foreground">Ver como tabla</summary>
        <table className="mt-2 w-full">
          <thead className="sr-only">
            <tr>
              <th scope="col">Mes</th>
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {months.map((month) => (
              <tr key={month.month}>
                <td className="py-0.5 capitalize">{formatMonth(month.month)}</td>
                <td className="py-0.5 text-right tabular-nums">{formatGs(month.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
