import { useEffect, useState } from "react";
import { listRequests } from "../api/client";
import type { Page, RequestItem, ScriptKey } from "../api/types";
import { PageShell } from "../components/PageShell";
import { formatDate } from "../lib/format";
import { navigate } from "../lib/router";

const BTN =
  "min-h-12 rounded-xl border-4 border-slate-900 px-4 text-lg font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400 disabled:opacity-50";

export function HistoryPage() {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [data, setData] = useState<Page<RequestItem> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      listRequests(page, q.trim())
        .then((d) => {
          if (cancelled) return;
          setData(d);
          setError(null);
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(e instanceof Error ? e.message : "No se pudo cargar el historial.");
        });
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [page, q]);

  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const view = (id: string, script: ScriptKey) =>
    navigate(`/preview?request=${id}&script=${script}&rank=1`);

  return (
    <PageShell>
      <h2 className="text-3xl font-bold">Historial</h2>
      <label className="block space-y-1 text-lg font-semibold">
        Buscar por nombre
        <input
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          className="min-h-12 w-full rounded-xl border-4 border-slate-900 px-3 text-xl sm:w-96"
        />
      </label>
      {error && (
        <p role="alert" className="text-xl font-semibold text-red-800">
          {error}
        </p>
      )}
      {data?.items.length === 0 && <p className="text-xl">No hay consultas todavía.</p>}
      <ul className="space-y-3" aria-label="Consultas">
        {data?.items.map((r) => (
          <li
            key={r.id}
            className="flex flex-wrap items-center gap-4 rounded-2xl border-4 border-slate-900 bg-white p-4"
          >
            <strong className="min-w-40 text-2xl">{r.input_name}</strong>
            <span lang="zh-Hans" className="font-sc text-3xl">
              {r.zh_text ?? "—"}
            </span>
            <span lang="ja" className="font-jp text-3xl">
              {r.ja_text ?? "—"}
            </span>
            <span className="text-base text-slate-700">{formatDate(r.created_at)}</span>
            <span className="ml-auto flex gap-2">
              {r.zh_text && (
                <button type="button" className={BTN} onClick={() => view(r.id, "zh")}>
                  Ver chino
                </button>
              )}
              {r.ja_text && (
                <button type="button" className={BTN} onClick={() => view(r.id, "ja")}>
                  Ver japonés
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {data && data.total > data.page_size && (
        <div className="flex items-center gap-4 text-lg">
          <button type="button" className={BTN} disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Anterior
          </button>
          <span>
            Página {page} de {lastPage}
          </span>
          <button
            type="button"
            className={BTN}
            disabled={page >= lastPage}
            onClick={() => setPage(page + 1)}
          >
            Siguiente
          </button>
        </div>
      )}
    </PageShell>
  );
}
