import { useEffect, useState } from "react";
import type { AdminApi } from "../../api/client";
import type { PendingItem } from "../../api/types";
import { formatDate } from "../../lib/format";
import { BTN, errorText } from "./ui";
import { EMPTY_DRAFT, type NameDraft } from "./NamesTab";

/** Convierte una consulta pendiente en un borrador del formulario (solo si es una palabra). */
export function draftFromPending(item: PendingItem): NameDraft {
  const single = item.input_name.trim().split(/\s+/).length === 1;
  return {
    ...EMPTY_DRAFT,
    display: item.input_name,
    ...(single && item.zh ? { zhText: item.zh.text, zhReading: item.zh.pinyin } : {}),
    ...(single && item.ja ? { jaText: item.ja.text, jaReading: item.ja.romaji } : {}),
  };
}

export function PendingTab({ api, onPromote }: { api: AdminApi; onPromote: (d: NameDraft) => void }) {
  const [items, setItems] = useState<PendingItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.pending().then(setItems).catch((e: unknown) => setError(errorText(e)));
  }, [api]);

  return (
    <div className="space-y-4">
      <p className="text-lg text-slate-700">
        Nombres convertidos por el algoritmo que todavía no están en el diccionario. Revísalos y
        añádelos como verificados.
      </p>
      {error && <p role="alert" className="text-lg font-semibold text-red-800">{error}</p>}
      {items?.length === 0 && <p className="text-xl">No hay conversiones pendientes de revisión.</p>}
      <ul className="space-y-2" aria-label="Pendientes">
        {items?.map((i) => (
          <li key={i.request_id} className="flex flex-wrap items-center gap-4 rounded-xl border-2 border-slate-900 p-3">
            <strong className="min-w-32 text-xl">{i.input_name}</strong>
            <span lang="zh-Hans" className="font-sc text-2xl">{i.zh?.text ?? "—"}</span>
            <span lang="ja" className="font-jp text-2xl">{i.ja?.text ?? "—"}</span>
            <span className="text-base text-slate-700">{formatDate(i.created_at)}</span>
            <button type="button" className={`${BTN} ml-auto`} onClick={() => onPromote(draftFromPending(i))}>
              Añadir al diccionario
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
