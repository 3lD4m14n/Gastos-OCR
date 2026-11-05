const GS = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 0, useGrouping: "always" });
const COMPACT = new Intl.NumberFormat("es-PY", { notation: "compact", maximumFractionDigits: 1 });
const PERCENT = new Intl.NumberFormat("es-PY", { style: "percent", maximumFractionDigits: 0 });

/** El mayor monto que acepta la API. Entra sin perder precisión en un número de JavaScript. */
export const MAX_AMOUNT = 1_000_000_000_000_000;
export const DEFAULT_TIMEZONE = "America/Asuncion";

export function formatGs(amount: number): string {
  return `${GS.format(amount)} Gs`;
}

export function formatGrouped(amount: number): string {
  return GS.format(amount);
}

export function formatCompact(amount: number): string {
  return COMPACT.format(amount);
}

export function formatPercent(ratio: number): string {
  return PERCENT.format(ratio);
}

/** Convierte lo escrito en guaraníes enteros. Devuelve null si no hay un monto válido. */
export function parseAmount(text: string): number | null {
  const digits = text.replace(/\D/g, "");
  if (!digits) return null;
  const value = Number(digits);
  return value > 0 && value <= MAX_AMOUNT ? value : null;
}

/** Fecha de hoy en la zona indicada, como YYYY-MM-DD. */
export function todayIn(timezone: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function isoDate(year: number, monthIndex: number, day: number): string {
  // Date.UTC ajusta los desbordes de mes y de año sin depender de la zona del navegador.
  return new Date(Date.UTC(year, monthIndex, day)).toISOString().slice(0, 10);
}

export interface DateRange {
  from: string;
  to: string;
}

/** El mes de `today`, o un mes anterior con `monthsBack`. */
export function monthRange(today: string, monthsBack = 0): DateRange {
  const year = Number(today.slice(0, 4));
  const month = Number(today.slice(5, 7)) - 1 - monthsBack;
  return {
    from: isoDate(year, month, 1),
    to: monthsBack === 0 ? today : isoDate(year, month + 1, 0),
  };
}

/** "2026-11-05" como "5 nov 2026", sin correrse de día por la zona horaria del navegador. */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("es-PY", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)));
}

/** "2026-11" como "nov". */
export function formatMonth(label: string): string {
  const [year, month] = label.split("-").map(Number);
  return new Intl.DateTimeFormat("es-PY", { month: "short", timeZone: "UTC" })
    .format(new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, 1)))
    .replace(".", "");
}
