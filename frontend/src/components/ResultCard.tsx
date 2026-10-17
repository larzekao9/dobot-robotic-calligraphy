import type { ReactNode } from "react";
import type { Source } from "../api/types";

export function SourceBadge({ source, verified }: { source: Source; verified?: boolean }) {
  const label = verified
    ? "Verificado"
    : source === "dictionary"
      ? "Diccionario"
      : "Sugerencia automática · pendiente de revisión";
  const tone = verified
    ? "bg-emerald-100 text-emerald-900"
    : source === "dictionary"
      ? "bg-sky-100 text-sky-900"
      : "bg-amber-100 text-amber-900";
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-base font-semibold ${tone}`}>
      {label}
    </span>
  );
}

export interface CardActions {
  onView?: () => void;
  onPrepare?: () => void;
  busy?: boolean;
}

interface Props extends CardActions {
  title: string;
  children: ReactNode;
}

const ACTION =
  "min-h-14 rounded-xl border-4 border-slate-900 px-5 text-xl font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400 disabled:border-slate-400 disabled:text-slate-600";

/** Tarjeta con título y las acciones sobre el resultado mostrado. */
export function ResultCard({ title, children, onView, onPrepare, busy }: Props) {
  return (
    <section
      aria-label={title}
      className="space-y-4 rounded-2xl border-4 border-slate-900 bg-white p-6"
    >
      <h2 className="text-2xl font-bold">{title}</h2>
      {children}
      <div className="flex flex-wrap gap-3 pt-2">
        <button type="button" disabled={!onView} onClick={onView} className={ACTION}>
          Ver trazos
        </button>
        <button
          type="button"
          disabled={!onPrepare || busy}
          onClick={onPrepare}
          className={`${ACTION} bg-indigo-800 text-white disabled:bg-white`}
        >
          {busy ? "Preparando…" : "Preparar para escribir"}
        </button>
      </div>
    </section>
  );
}
