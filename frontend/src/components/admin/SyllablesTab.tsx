import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { AdminApi } from "../../api/client";
import type { Connotation, Page, SyllableIn, SyllableOut } from "../../api/types";
import { BTN, errorText, FIELD, LABEL, PRIMARY } from "./ui";

const EMPTY: SyllableIn = {
  script: "zh",
  syllable_es: "",
  output: "",
  reading: "",
  meaning: null,
  connotation: "neutral",
  gender_hint: "u",
  score: 50,
};

const CONNOTATIONS: [Connotation, string][] = [
  ["positive", "Positiva"],
  ["neutral", "Neutra"],
  ["avoid", "Evitar"],
];

const toInput = ({ id: _id, ...rest }: SyllableOut): SyllableIn => rest;

export function SyllablesTab({ api }: { api: AdminApi }) {
  const [draft, setDraft] = useState<SyllableIn>(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [script, setScript] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<SyllableOut> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.listSyllables(page, script, q.trim()));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, [api, page, script, q]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      setError(null);
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const body = { ...draft, meaning: draft.meaning?.trim() || null };
      await (editing ? api.updateSyllable(editing, body) : api.createSyllable(body));
      setDraft(EMPTY);
      setEditing(null);
    });
  }

  const set = <K extends keyof SyllableIn>(key: K, value: SyllableIn[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  return (
    <div className="space-y-6">
      <form onSubmit={submit} aria-label="Formulario de sílaba" className="space-y-3 rounded-2xl border-4 border-slate-900 p-4">
        <h3 className="text-xl font-bold">{editing ? "Editar sílaba" : "Añadir sílaba"}</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className={LABEL}>
            Escritura
            <select className={`${FIELD} w-full`} value={draft.script} onChange={(e) => set("script", e.target.value as SyllableIn["script"])}>
              <option value="zh">Chino</option>
              <option value="ja">Japonés</option>
            </select>
          </label>
          <label className={LABEL}>
            Sílaba (español)
            <input className={`${FIELD} w-full`} value={draft.syllable_es} onChange={(e) => set("syllable_es", e.target.value)} />
          </label>
          <label className={LABEL}>
            Carácter
            <input className={`${FIELD} w-full font-sc`} value={draft.output} onChange={(e) => set("output", e.target.value)} />
          </label>
          <label className={LABEL}>
            Lectura
            <input className={`${FIELD} w-full`} value={draft.reading} onChange={(e) => set("reading", e.target.value)} />
          </label>
          <label className={LABEL}>
            Significado
            <input className={`${FIELD} w-full`} value={draft.meaning ?? ""} onChange={(e) => set("meaning", e.target.value)} />
          </label>
          <label className={LABEL}>
            Connotación
            <select className={`${FIELD} w-full`} value={draft.connotation} onChange={(e) => set("connotation", e.target.value as Connotation)}>
              {CONNOTATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className={LABEL}>
            Puntaje (0–100)
            <input type="number" min={0} max={100} className={`${FIELD} w-full`} value={draft.score} onChange={(e) => set("score", Number(e.target.value))} />
          </label>
        </div>
        <div className="flex gap-3">
          <button type="submit" className={PRIMARY}>Guardar</button>
          {editing && (
            <button type="button" className={BTN} onClick={() => { setDraft(EMPTY); setEditing(null); }}>Cancelar edición</button>
          )}
        </div>
      </form>

      {error && <p role="alert" className="text-lg font-semibold text-red-800">{error}</p>}

      <div className="flex flex-wrap items-end gap-4">
        <label className={LABEL}>
          Escritura
          <select className={`${FIELD} w-48`} value={script} onChange={(e) => { setScript(e.target.value); setPage(1); }}>
            <option value="">Todas</option>
            <option value="zh">Chino</option>
            <option value="ja">Japonés</option>
          </select>
        </label>
        <label className={LABEL}>
          Buscar sílaba o carácter
          <input type="search" className={`${FIELD} w-64`} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </label>
      </div>

      <ul className="space-y-2" aria-label="Sílabas">
        {data?.items.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center gap-4 rounded-xl border-2 border-slate-900 p-3">
            <span className="w-20 text-xl font-bold">{s.syllable_es}</span>
            <span lang={s.script === "zh" ? "zh-Hans" : "ja"} className="font-sc text-3xl">{s.output}</span>
            <span className="w-24 text-lg">{s.reading}</span>
            <span className="min-w-32 text-base text-slate-700">{s.meaning ?? ""}</span>
            <label className="text-base font-semibold">
              <span className="sr-only">Connotación de {s.output}</span>
              <select
                className={`${FIELD} ${s.connotation === "avoid" ? "bg-red-100" : ""}`}
                value={s.connotation}
                onChange={(e) => void run(() => api.updateSyllable(s.id, { ...toInput(s), connotation: e.target.value as Connotation }))}
              >
                {CONNOTATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <span className="text-base">Puntaje {s.score}</span>
            <span className="ml-auto flex gap-2">
              <button type="button" className={BTN} onClick={() => { setDraft(toInput(s)); setEditing(s.id); }}>Editar</button>
              <button
                type="button"
                className={BTN}
                onClick={() => window.confirm(`¿Eliminar ${s.syllable_es} → ${s.output}?`) && void run(() => api.deleteSyllable(s.id))}
              >
                Eliminar
              </button>
            </span>
          </li>
        ))}
      </ul>
      {data?.items.length === 0 && <p className="text-lg">No hay sílabas que coincidan.</p>}
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
