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

export function toDatetimeLocalValue(iso: string | null | undefined): string {
  const d = iso ? new Date(iso) : new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
