export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface User {
  id: string;
  currency: string;
  timezone: string;
}

export interface Category {
  id: string;
  name: string;
  color: string;
  icon: string | null;
  is_default: boolean;
  is_fallback: boolean;
}

export interface Expense {
  id: string;
  category_id: string;
  description: string;
  amount: number;
  spent_at: string;
  notes: string | null;
}

export interface ExpenseInput {
  category_id: string;
  description: string;
  amount: number;
  spent_at: string;
  notes: string | null;
}

export interface ExpensePage {
  items: Expense[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExpenseFilters {
  from?: string;
  to?: string;
  category_id?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface CategoryTotal {
  category_id: string;
  name: string;
  color: string;
  total: number;
}

export interface MonthTotal {
  month: string;
  total: number;
}

export interface StatsSummary {
  date_from: string;
  date_to: string;
  total: number;
  by_category: CategoryTotal[];
  by_month: MonthTotal[];
}

const BASE_URL = `${(import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "")}/api/v1`;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  params?: object;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    // El cuerpo no es JSON: se usa el mensaje genérico.
  }
  return response.status === 422
    ? "Revisá los datos ingresados"
    : "No se pudo completar la operación; probá de nuevo";
}

export function createApi(getToken: () => string | undefined, onUnauthorized: () => void) {
  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params ?? {})) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    const suffix = query.size ? `?${query}` : "";
    const response = await fetch(`${BASE_URL}${path}${suffix}`, {
      method: options.method ?? "GET",
      headers: {
        Authorization: `Bearer ${getToken() ?? ""}`,
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (response.status === 401) onUnauthorized();
    if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
    return (response.status === 204 ? undefined : await response.json()) as T;
  }

  return {
    me: () => request<User>("/users/me"),
    categories: () => request<Category[]>("/categories"),
    createCategory: (body: { name: string; color: string }) =>
      request<Category>("/categories", { method: "POST", body }),
    updateCategory: (id: string, body: { name: string; color: string }) =>
      request<Category>(`/categories/${id}`, { method: "PATCH", body }),
    deleteCategory: (id: string) => request<void>(`/categories/${id}`, { method: "DELETE" }),
    expenses: (params: ExpenseFilters) => request<ExpensePage>("/expenses", { params }),
    createExpense: (body: ExpenseInput) => request<Expense>("/expenses", { method: "POST", body }),
    updateExpense: (id: string, body: ExpenseInput) =>
      request<Expense>(`/expenses/${id}`, { method: "PATCH", body }),
    deleteExpense: (id: string) => request<void>(`/expenses/${id}`, { method: "DELETE" }),
    summary: (params: { from: string; to: string }) =>
      request<StatsSummary>("/stats/summary", { params }),
  };
}

export type Api = ReturnType<typeof createApi>;
