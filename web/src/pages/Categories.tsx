import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CategorySwatch } from "@/components/ExpenseRow";
import { ErrorMessage, Field } from "@/components/Field";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCategories, useDeleteCategory, useSaveCategory } from "@/hooks/useApi";
import type { Category } from "@/lib/api";

const NEW_CATEGORY_COLOR = "#2a78d6";

function CategoryForm({ category, onDone }: { category: Category | null; onDone: () => void }) {
  const save = useSaveCategory();
  const [name, setName] = useState(category?.name ?? "");
  const [color, setColor] = useState(category?.color ?? NEW_CATEGORY_COLOR);

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({ id: category?.id, input: { name, color } }, { onSuccess: onDone });
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <Field id="category-name" label="Nombre">
        <Input
          id="category-name"
          required
          maxLength={60}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </Field>
      <Field id="category-color" label="Color">
        <Input
          id="category-color"
          type="color"
          className="w-16 p-1"
          value={color}
          onChange={(event) => setColor(event.target.value)}
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

export function Categories() {
  const categories = useCategories();
  const remove = useDeleteCategory();
  const [editing, setEditing] = useState<Category | null>(null);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<Category | null>(null);
  const formOpen = adding || editing !== null;

  function closeForm() {
    setAdding(false);
    setEditing(null);
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Categorías</h1>
        <Button size="sm" onClick={() => setAdding(true)}>
          <Plus aria-hidden />
          Nueva categoría
        </Button>
      </div>

      <ErrorMessage error={categories.error} />

      <Card>
        <CardContent>
          <ul className="grid grid-cols-1 gap-2">
            {categories.data?.map((category) => (
              <li key={category.id} className="flex items-center gap-3">
                <CategorySwatch color={category.color} />
                <span className="min-w-0 flex-1 truncate text-sm">{category.name}</span>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={`Editar ${category.name}`}
                  onClick={() => setEditing(category)}
                >
                  <Pencil aria-hidden />
                </Button>
                {!category.is_fallback && (
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={`Borrar ${category.name}`}
                    onClick={() => setDeleting(category)}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={(next) => !next && closeForm()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Editar categoría" : "Nueva categoría"}</DialogTitle>
          </DialogHeader>
          <CategoryForm key={editing?.id ?? "nueva"} category={editing} onDone={closeForm} />
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        title="¿Borrar esta categoría?"
        description={
          deleting ? `Los gastos de "${deleting.name}" van a pasar a la categoría Otros.` : ""
        }
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
