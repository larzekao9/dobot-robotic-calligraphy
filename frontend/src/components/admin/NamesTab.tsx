import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { AdminApi } from "../../api/client";
import type { Gender, NameIn, NameOut, Page, TranslitIn } from "../../api/types";
import { BTN, errorText, FIELD, LABEL, PRIMARY } from "./ui";

export interface NameDraft {
  display: string;
  gender: Gender;
  zhText: string;
  zhReading: string;
  jaText: string;
  jaReading: string;
}

export const EMPTY_DRAFT: NameDraft = {
  display: "",
  gender: "u",
  zhText: "",
  zhReading: "",
  jaText: "",
  jaReading: "",
};

function toBody(d: NameDraft): NameIn | string {
  const transliterations: TranslitIn[] = [];
  if (d.zhText.trim() && d.zhReading.trim()) {
    transliterations.push({ script: "zh", text: d.zhText.trim(), reading: d.zhReading.trim(), rank: 1 });
  }
  if (d.jaText.trim() && d.jaReading.trim()) {
    transliterations.push({ script: "ja", text: d.jaText.trim(), reading: d.jaReading.trim(), rank: 1 });
  }
  if (!d.display.trim()) return "Escribe el nombre.";
  if (!transliterations.length) return "Completa al menos una transliteración (texto y lectura).";
  return { display_name: d.display.trim(), gender: d.gender, verified: true, transliterations };
}

function toDraft(n: NameOut): NameDraft {
  const zh = n.transliterations.find((t) => t.script === "zh");
  const ja = n.transliterations.find((t) => t.script === "ja");
  return {
    display: n.display_name,
    gender: n.gender,
    zhText: zh?.text ?? "",
    zhReading: zh?.reading ?? "",
    jaText: ja?.text ?? "",
    jaReading: ja?.reading ?? "",
  };
}

interface Props {
  api: AdminApi;
  prefill: NameDraft | null;
  onPrefillUsed: () => void;
}

export function NamesTab({ api, prefill, onPrefillUsed }: Props) {
  const [draft, setDraft] = useState<NameDraft>(EMPTY_DRAFT);
  const [editing, setEditing] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [onlyPending, setOnlyPending] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<NameOut> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.listNames(page, q.trim(), onlyPending));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, [api, page, q, onlyPending]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (prefill) {
      setDraft(prefill);
      setEditing(null);
      onPrefillUsed();
    }
  }, [prefill, onPrefillUsed]);

  const set = (key: keyof NameDraft, value: string) => setDraft((d) => ({ ...d, [key]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = toBody(draft);
    if (typeof body === "string") {
      setError(body);
      return;
    }
    try {
      const saved = editing ? await api.updateName(editing, body) : await api.createName(body);
      setNotice(
        saved.missing_glyphs.length
          ? `Guardado, pero el robot aún no puede escribir: ${saved.missing_glyphs.join(" ")} (faltan trazos).`
          : `«${saved.display_name}» guardado y verificado.`,
      );
      setDraft(EMPTY_DRAFT);
      setEditing(null);
      await load();
    } catch (err) {
      setNotice(null);
      setError(errorText(err));
    }
  }

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      setError(null);
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} aria-label="Formulario de nombre" className="space-y-3 rounded-2xl border-4 border-slate-900 p-4">
        <h3 className="text-xl font-bold">{editing ? "Editar nombre" : "Añadir nombre"}</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className={LABEL}>
            Nombre
            <input className={`${FIELD} w-full`} value={draft.display} onChange={(e) => set("display", e.target.value)} />
          </label>
          <label className={LABEL}>
            Género
            <select className={`${FIELD} w-full`} value={draft.gender} onChange={(e) => set("gender", e.target.value)}>
              <option value="u">Neutro</option>
              <option value="m">Masculino</option>
              <option value="f">Femenino</option>
            </select>
          </label>
          <span />
          <label className={LABEL}>
            Chino (hanzi)
            <input lang="zh-Hans" className={`${FIELD} w-full font-sc`} value={draft.zhText} onChange={(e) => set("zhText", e.target.value)} />
          </label>
          <label className={LABEL}>
            Pinyin
            <input className={`${FIELD} w-full`} value={draft.zhReading} onChange={(e) => set("zhReading", e.target.value)} />
          </label>
          <span />
          <label className={LABEL}>
            Japonés (katakana)
            <input lang="ja" className={`${FIELD} w-full font-jp`} value={draft.jaText} onChange={(e) => set("jaText", e.target.value)} />
          </label>
          <label className={LABEL}>
            Romaji
            <input className={`${FIELD} w-full`} value={draft.jaReading} onChange={(e) => set("jaReading", e.target.value)} />
          </label>
        </div>
        <div className="flex gap-3">
          <button type="submit" className={PRIMARY}>
            Guardar (verificado)
          </button>
          {(editing || draft !== EMPTY_DRAFT) && (
            <button type="button" className={BTN} onClick={() => { setDraft(EMPTY_DRAFT); setEditing(null); }}>
              Limpiar
            </button>
          )}
        </div>
      </form>

      {notice && <p role="status" className="text-lg font-semibold text-emerald-900">{notice}</p>}
      {error && <p role="alert" className="text-lg font-semibold text-red-800">{error}</p>}

      <div className="flex flex-wrap items-end gap-4">
        <label className={LABEL}>
          Buscar
          <input type="search" className={`${FIELD} w-64`} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </label>
        <label className="flex items-center gap-2 text-lg font-semibold">
          <input type="checkbox" className="h-6 w-6" checked={onlyPending} onChange={(e) => { setOnlyPending(e.target.checked); setPage(1); }} />
          Solo sin verificar
        </label>
      </div>

      <ul className="space-y-2" aria-label="Diccionario">
        {data?.items.map((n) => {
          const zh = n.transliterations.find((t) => t.script === "zh");
          const ja = n.transliterations.find((t) => t.script === "ja");
          return (
            <li key={n.id} className="flex flex-wrap items-center gap-4 rounded-xl border-2 border-slate-900 p-3">
              <strong className="min-w-32 text-xl">{n.display_name}</strong>
              <span lang="zh-Hans" className="font-sc text-2xl">{zh?.text ?? "—"}</span>
              <span lang="ja" className="font-jp text-2xl">{ja?.text ?? "—"}</span>
              <span className={`rounded-full px-3 py-1 text-base font-bold ${n.verified ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"}`}>
                {n.verified ? "Verificado" : "Sin verificar"}
              </span>
              <span className="ml-auto flex flex-wrap gap-2">
                <button type="button" className={BTN} onClick={() => { setDraft(toDraft(n)); setEditing(n.id); }}>
                  Editar
                </button>
                <button type="button" className={BTN} onClick={() => void run(() => api.verifyName(n.id, !n.verified))}>
                  {n.verified ? "Quitar verificación" : "Verificar"}
                </button>
                <button
                  type="button"
                  className={BTN}
                  onClick={() => window.confirm(`¿Eliminar «${n.display_name}»?`) && void run(() => api.deleteName(n.id))}
                >
                  Eliminar
                </button>
              </span>
            </li>
          );
        })}
      </ul>
      {data?.items.length === 0 && <p className="text-lg">No hay nombres que coincidan.</p>}
      {data && data.total > data.page_size && (
        <div className="flex items-center gap-4 text-lg">
          <button type="button" className={BTN} disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</button>
          <span>Página {page} de {Math.ceil(data.total / data.page_size)}</span>
          <button type="button" className={BTN} disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>Siguiente</button>
        </div>
      )}
    </div>
  );
}
