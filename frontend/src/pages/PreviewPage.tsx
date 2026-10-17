import { useEffect, useState } from "react";
import { createJob, previewLayout } from "../api/client";
import type { Layout, PathPreview, ScriptKey } from "../api/types";
import { PageShell } from "../components/PageShell";
import { StrokePlayer } from "../components/StrokePlayer";
import { formatDuration } from "../lib/format";
import { DEFAULT_LAYOUT } from "../lib/layout";
import { navigate } from "../lib/router";

const DEBOUNCE_MS = 250;
const FIELD = "min-h-12 rounded-xl border-4 border-slate-900 px-3 text-xl";
const LABEL = "block space-y-1 text-lg font-semibold";

export function PreviewPage({ params }: { params: URLSearchParams }) {
  const requestId = params.get("request");
  const script = params.get("script");
  const rank = Number(params.get("rank") ?? 1) || 1;
  const valid = Boolean(requestId) && (script === "zh" || script === "ja");

  const [layout, setLayout] = useState<Layout>(DEFAULT_LAYOUT);
  const [speed, setSpeed] = useState(1);
  const [loop, setLoop] = useState(false);
  const [preview, setPreview] = useState<PathPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!valid) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      previewLayout({ request_id: requestId!, script: script as ScriptKey, rank, layout })
        .then((p) => {
          if (cancelled) return;
          setPreview(p);
          setError(null);
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          setPreview(null);
          setError(e instanceof Error ? e.message : "No se pudo generar la vista previa.");
        });
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [valid, requestId, script, rank, layout]);

  if (!valid) {
    return (
      <PageShell>
        <p className="text-xl">
          Primero elige un nombre en <a href="#/" className="underline">Convertir</a> y pulsa «Ver
          trazos».
        </p>
      </PageShell>
    );
  }

  const set = <K extends keyof Layout>(key: K, value: Layout[K]) =>
    setLayout((l) => ({ ...l, [key]: value }));

  async function prepare() {
    setCreating(true);
    try {
      const job = await createJob({ request_id: requestId!, script: script as ScriptKey, rank, layout });
      navigate(`/jobs?highlight=${job.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo preparar el trabajo.");
    } finally {
      setCreating(false);
    }
  }

  const shrunk = preview && preview.char_size_mm < layout.char_size_mm - 0.05;

  return (
    <PageShell>
      <h2 className="text-3xl font-bold">
        Vista previa de trazos{" "}
        {preview && (
          <span lang={script === "zh" ? "zh-Hans" : "ja"} className="font-sc">
            {preview.text}
          </span>
        )}
      </h2>

      <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
        <form className="space-y-4" onSubmit={(e) => e.preventDefault()} aria-label="Ajustes">
          <label className={LABEL}>
            Papel
            <select
              className={`${FIELD} w-full`}
              value={layout.paper}
              onChange={(e) => {
                const paper = e.target.value as Layout["paper"];
                setLayout((l) => ({
                  ...l,
                  paper,
                  width_mm: paper === "custom" ? (l.width_mm ?? 200) : null,
                  height_mm: paper === "custom" ? (l.height_mm ?? 300) : null,
                }));
              }}
            >
              <option value="A4">A4 (210 × 297 mm)</option>
              <option value="A5">A5 (148 × 210 mm)</option>
              <option value="carta">Carta (216 × 279 mm)</option>
              <option value="media_carta">Media Carta (140 × 216 mm)</option>
              <option value="oficio">Oficio (216 × 330 mm)</option>
              <option value="medio_oficio">Mitad de Oficio (165 × 216 mm)</option>
              <option value="custom">Personalizado</option>
            </select>
          </label>
          {layout.paper === "custom" && (
            <div className="flex gap-3">
              <label className={LABEL}>
                Ancho (mm)
                <input
                  type="number"
                  min={50}
                  max={1000}
                  className={`${FIELD} w-full`}
                  value={layout.width_mm ?? ""}
                  onChange={(e) => set("width_mm", Number(e.target.value))}
                />
              </label>
              <label className={LABEL}>
                Alto (mm)
                <input
                  type="number"
                  min={50}
                  max={1000}
                  className={`${FIELD} w-full`}
                  value={layout.height_mm ?? ""}
                  onChange={(e) => set("height_mm", Number(e.target.value))}
                />
              </label>
            </div>
          )}
          <label className={LABEL}>
            Tamaño del carácter: {layout.char_size_mm} mm
            <input
              type="range"
              min={10}
              max={100}
              className="h-10 w-full"
              value={layout.char_size_mm}
              onChange={(e) => set("char_size_mm", Number(e.target.value))}
            />
          </label>
          <label className={LABEL}>
            Orientación
            <select
              className={`${FIELD} w-full`}
              value={layout.orientation}
              onChange={(e) => set("orientation", e.target.value as Layout["orientation"])}
            >
              <option value="horizontal">Horizontal</option>
              <option value="vertical">Vertical</option>
            </select>
          </label>
          <label className={LABEL}>
            Velocidad de la animación
            <select
              className={`${FIELD} w-full`}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            >
              {[0.5, 1, 2, 4].map((v) => (
                <option key={v} value={v}>
                  {v}×
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-3 text-lg font-semibold">
            <input
              type="checkbox"
              className="h-6 w-6"
              checked={loop}
              onChange={(e) => setLoop(e.target.checked)}
            />
            Repetir
          </label>
        </form>

        <div className="space-y-4">
          {error && (
            <p role="alert" className="rounded-xl border-4 border-red-800 bg-red-50 p-4 text-xl font-semibold text-red-900">
              {error}
            </p>
          )}
          {!preview && !error && <p className="text-xl">Calculando trazos…</p>}
          {preview && (
            <>
              <StrokePlayer
                strokes={preview.strokes}
                width={preview.paper_width_mm}
                height={preview.paper_height_mm}
                speed={speed}
                loop={loop}
              />
              <p className="text-xl" data-testid="estimate">
                Tiempo estimado de escritura: <strong>{formatDuration(preview.estimated_seconds)}</strong>{" "}
                · {preview.char_count} caracteres, {preview.stroke_count} trazos
              </p>
              {shrunk && (
                <p className="text-lg text-amber-900">
                  Para que quepa, los caracteres se reducen a {preview.char_size_mm} mm.
                </p>
              )}
            </>
          )}
          <button
            type="button"
            onClick={() => void prepare()}
            disabled={creating || !preview}
            className="min-h-14 rounded-xl bg-indigo-800 px-6 text-xl font-bold text-white focus:outline-none focus:ring-4 focus:ring-indigo-400 disabled:opacity-60"
          >
            {creating ? "Preparando…" : "Preparar para escribir"}
          </button>
        </div>
      </div>
    </PageShell>
  );
}
