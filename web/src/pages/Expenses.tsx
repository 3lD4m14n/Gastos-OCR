import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ExpenseDialog } from "@/components/ExpenseDialog";
import { ExpenseRow } from "@/components/ExpenseRow";
import { ErrorMessage, Field, selectClassName } from "@/components/Field";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCategories, useDeleteExpense, useExpenses } from "@/hooks/useApi";
import type { Expense } from "@/lib/api";

const SEARCH_DELAY_MS = 300;

export function Expenses() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<Expense | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search);
      setPage(1);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const expenses = useExpenses({ from, to, category_id: categoryId, q, page });
  const categories = useCategories();
  const remove = useDeleteExpense();
  const categoryById = new Map(categories.data?.map((c) => [c.id, c]));
  const data = expenses.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Gastos</h1>
        <Button size="sm" onClick={() => setAdding(true)}>
          <Plus aria-hidden />
          Nuevo gasto
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field id="filter-search" label="Buscar" className="col-span-2 md:col-span-1">
          <Input
            id="filter-search"
            type="search"
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </Field>
        <Field id="filter-category" label="Categoría" className="col-span-2 md:col-span-1">
          <select
            id="filter-category"
            className={selectClassName}
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            {categories.data?.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </Field>
        <Field id="filter-from" label="Desde">
          <Input
            id="filter-from"
            type="date"
            value={from}
            onChange={(event) => {
              setFrom(event.target.value);
              setPage(1);
            }}
          />
        </Field>
        <Field id="filter-to" label="Hasta">
          <Input
            id="filter-to"
            type="date"
            value={to}
            onChange={(event) => {
              setTo(event.target.value);
              setPage(1);
            }}
          />
        </Field>
      </div>

      <ErrorMessage error={expenses.error} />

      <Card>
        <CardContent>
          {data?.items.length === 0 && (
            <p className="text-sm text-muted-foreground">No hay gastos con estos filtros.</p>
          )}
          <ul className="grid grid-cols-1 gap-3">
            {data?.items.map((expense) => (
              <li key={expense.id} className="flex items-center gap-1">
                <ExpenseRow expense={expense} category={categoryById.get(expense.category_id)} />
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={`Editar ${expense.description}`}
                  onClick={() => setEditing(expense)}
                >
                  <Pencil aria-hidden />
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={`Borrar ${expense.description}`}
                  onClick={() => setDeleting(expense)}
                >
                  <Trash2 aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {pages > 1 && (
        <nav aria-label="Páginas" className="flex items-center justify-center gap-3">
          <Button
            size="icon-sm"
            variant="outline"
            aria-label="Página anterior"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft aria-hidden />
          </Button>
          <span className="text-sm text-muted-foreground">
            Página {page} de {pages}
          </span>
          <Button
            size="icon-sm"
            variant="outline"
            aria-label="Página siguiente"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            <ChevronRight aria-hidden />
          </Button>
        </nav>
      )}

      <ExpenseDialog
        open={adding || editing !== null}
        expense={editing}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="¿Borrar este gasto?"
        description={deleting ? `Se va a borrar "${deleting.description}".` : ""}
        pending={remove.isPending}
        error={remove.error}
        onCancel={() => {
          remove.reset();
          setDeleting(null);
        }}
        onConfirm={() => {
          if (deleting) remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) });
        }}
      />
    </>
  );
}
