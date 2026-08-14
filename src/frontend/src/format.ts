export function formatOdometer(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value).toLocaleString()} mi`;
}

export function formatMiles(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value).toLocaleString()} mi`;
}

export function formatGallons(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value.toFixed(3)} gal`;
}

export function formatMoney(value: number | null | undefined): string {
  if (value == null) return "—";
  return `$${value.toFixed(2)}`;
}

export function formatPricePerGallon(value: number | null | undefined): string {
  if (value == null) return "—";
  return `$${value.toFixed(3)}/gal`;
}

export function formatMpg(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value.toFixed(1)} MPG`;
}

export function formatCostPerMile(value: number | null | undefined): string {
  if (value == null) return "—";
  return `$${value.toFixed(3)}/mi`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${formatDate(iso)}, ${formatTime(iso)}`;
}

function formatDatetimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Deliberately does NOT fall back to `new Date()` when `iso` is missing --
// that used to make a fill-up whose date genuinely couldn't be read from
// the receipt look like it was correctly read as "today", with no visual
// difference from a real match. An empty field is an honest signal that
// nothing was found; the "Use current time" toggle next to the date field
// is the explicit, visible way to opt into today's date instead.
export function toDatetimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return "";
  return formatDatetimeLocal(new Date(iso));
}

export function nowDatetimeLocalValue(): string {
  return formatDatetimeLocal(new Date());
}
