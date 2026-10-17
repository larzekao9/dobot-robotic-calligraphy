import { useCallback, useEffect, useState } from "react";
import { cancelJob, listJobs, startJob } from "../api/client";
import type { Job, JobStatus } from "../api/types";
import { formatDate, formatDuration } from "../lib/format";

export const STATUS_LABEL: Record<JobStatus, string> = {
  draft: "Borrador",
  queued: "En cola",
  running: "Escribiendo",
  done: "Terminado",
  failed: "Fallido",
  cancelled: "Cancelado",
};

const TONE: Record<JobStatus, string> = {
  draft: "bg-slate-200 text-slate-900",
  queued: "bg-sky-100 text-sky-900",
  running: "bg-indigo-100 text-indigo-900",
  done: "bg-emerald-100 text-emerald-900",
  failed: "bg-red-100 text-red-900",
  cancelled: "bg-amber-100 text-amber-900",
};

const BTN =
  "min-h-12 rounded-xl border-4 border-slate-900 px-4 text-lg font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400 disabled:opacity-60";

interface Props {
  pollMs?: number;
  highlight?: string | null;
}

/** Cola de trabajos: refresca sola mientras haya alguno en cola o escribiendo. */
export function JobsPanel({ pollMs = 1000, highlight = null }: Props) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setJobs(await listJobs());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar la cola.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = jobs?.some((j) => j.status === "queued" || j.status === "running") ?? false;
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => void load(), pollMs);
    return () => clearInterval(id);
  }, [active, load, pollMs]);

  async function act(fn: (id: string) => Promise<Job>, id: string) {
    let failure: string | null = null;
    try {
      await fn(id);
    } catch (e) {
      failure = e instanceof Error ? e.message : "No se pudo completar la acción.";
    }
    await load(); // refresca primero: `load` limpia el error, así que el de la acción va después
    if (failure) setError(failure);
  }

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="rounded-xl border-4 border-red-800 bg-red-50 p-4 text-xl font-semibold text-red-900">
          {error}
        </p>
      )}
      {jobs?.length === 0 && (
        <p className="text-xl">No hay trabajos todavía. Prepara uno desde «Convertir».</p>
      )}
      <ul className="space-y-4" aria-label="Trabajos">
        {jobs?.map((job) => (
          <li
            key={job.id}
            aria-label={`Trabajo ${job.text}`}
            className={`space-y-3 rounded-2xl border-4 p-4 ${
              job.id === highlight ? "border-indigo-700 bg-indigo-50" : "border-slate-900 bg-white"
            }`}
          >
            <div className="flex flex-wrap items-center gap-4">
              <span lang={job.script === "zh" ? "zh-Hans" : "ja"} className="font-sc text-4xl">
                {job.text}
              </span>
              <span className="text-lg">{job.script === "zh" ? "Chino" : "Japonés"}</span>
              <span className={`rounded-full px-3 py-1 text-lg font-bold ${TONE[job.status]}`}>
                {STATUS_LABEL[job.status]}
              </span>
              <span className="text-base text-slate-700">{formatDate(job.created_at)}</span>
              {job.estimated_seconds != null && (
                <span className="text-base">~{formatDuration(job.estimated_seconds)}</span>
              )}
            </div>
            {(job.status === "running" || job.status === "queued" || job.status === "done") && (
              <div
                role="progressbar"
                aria-label={`Progreso de ${job.text}`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(job.progress * 100)}
                className="h-6 overflow-hidden rounded-full border-2 border-slate-900 bg-white"
              >
                <div
                  className="h-full bg-indigo-700 transition-all"
                  style={{ width: `${Math.round(job.progress * 100)}%` }}
                />
              </div>
            )}
            {job.error && <p className="text-lg font-semibold text-red-900">{job.error}</p>}
            <div className="flex gap-3">
              {job.status === "draft" && (
                <>
                  <button type="button" className={BTN} onClick={() => void act(startJob, job.id)}>
                    Iniciar
                  </button>
                  <button
                    type="button"
                    className={BTN}
                    title="Recorre todo con la pluma arriba, sin tocar el papel"
                    onClick={() => void act((id) => startJob(id, true), job.id)}
                  >
                    Probar en el aire
                  </button>
                </>
              )}
              {(job.status === "draft" || job.status === "queued" || job.status === "running") && (
                <button type="button" className={BTN} onClick={() => void act(cancelJob, job.id)}>
                  Cancelar
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
