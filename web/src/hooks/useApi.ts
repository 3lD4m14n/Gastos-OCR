import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useAuth } from "react-oidc-context";

import { createApi } from "@/lib/api";
import type { Category, ExpenseFilters, ExpenseInput } from "@/lib/api";
import { DEFAULT_TIMEZONE, todayIn } from "@/lib/format";

/** Cada 30 s, para que un gasto cargado en otro dispositivo aparezca solo (HU-02). */
const DASHBOARD_REFRESH_MS = 30_000;

export function useApi() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const { removeUser } = auth;

  return useMemo(
    () =>
      createApi(
        () => token,
        // Token rechazado: se descarta la sesión y la app vuelve al login.
        () => void removeUser(),
      ),
    [token, removeUser],
  );
}

export function useToday(): string {
  const api = useApi();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 5 * 60_000 });
  return todayIn(me.data?.timezone ?? DEFAULT_TIMEZONE);
}

export function useCategories() {
  const api = useApi();
  return useQuery({ queryKey: ["categories"], queryFn: api.categories });
}

export function useExpenses(filters: ExpenseFilters, options: { refresh?: boolean } = {}) {
  const api = useApi();
  return useQuery({
    queryKey: ["expenses", filters],
    queryFn: () => api.expenses(filters),
    placeholderData: keepPreviousData,
    refetchInterval: options.refresh ? DASHBOARD_REFRESH_MS : false,
  });
}

export function useSummary(range: { from: string; to: string }) {
  const api = useApi();
  return useQuery({
    queryKey: ["stats", range],
    queryFn: () => api.summary(range),
    placeholderData: keepPreviousData,
    refetchInterval: DASHBOARD_REFRESH_MS,
  });
}

function useInvalidate(...keys: string[]) {
  const client = useQueryClient();
  return () => Promise.all(keys.map((key) => client.invalidateQueries({ queryKey: [key] })));
}

export function useSaveExpense() {
  const api = useApi();
  const invalidate = useInvalidate("expenses", "stats");
  return useMutation({
    mutationFn: ({ id, input }: { id?: string; input: ExpenseInput }) =>
      id ? api.updateExpense(id, input) : api.createExpense(input),
    onSuccess: invalidate,
  });
}

export function useDeleteExpense() {
  const api = useApi();
  const invalidate = useInvalidate("expenses", "stats");
  return useMutation({ mutationFn: api.deleteExpense, onSuccess: invalidate });
}

export function useSaveCategory() {
  const api = useApi();
  const invalidate = useInvalidate("categories", "stats");
  return useMutation({
    mutationFn: ({ id, input }: { id?: string; input: Pick<Category, "name" | "color"> }) =>
      id ? api.updateCategory(id, input) : api.createCategory(input),
    onSuccess: invalidate,
  });
}

export function useDeleteCategory() {
  const api = useApi();
  const invalidate = useInvalidate("categories", "expenses", "stats");
  return useMutation({ mutationFn: api.deleteCategory, onSuccess: invalidate });
}
