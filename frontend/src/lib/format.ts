export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return s ? `${m} min ${s} s` : `${m} min`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}
