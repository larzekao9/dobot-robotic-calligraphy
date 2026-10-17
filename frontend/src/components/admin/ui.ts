export const BTN =
  "min-h-12 rounded-xl border-4 border-slate-900 px-4 text-lg font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400 disabled:opacity-50";
export const PRIMARY = `${BTN} bg-indigo-800 text-white`;
export const FIELD = "min-h-12 rounded-xl border-4 border-slate-900 px-3 text-lg";
export const LABEL = "block space-y-1 text-base font-semibold";

export const errorText = (e: unknown, fallback = "Ocurrió un error inesperado."): string =>
  e instanceof Error ? e.message : fallback;
