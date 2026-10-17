import { useState } from "react";
import { createJob } from "../api/client";
import type { ScriptKey } from "../api/types";
import { JaCard } from "../components/JaCard";
import { NameForm } from "../components/NameForm";
import { PageShell } from "../components/PageShell";
import { ZhCard } from "../components/ZhCard";
import { useConvert } from "../hooks/useConvert";
import { DEFAULT_LAYOUT } from "../lib/layout";
import { navigate } from "../lib/router";

export function ConverterPage() {
  const { state, convert } = useConvert();
  const [busy, setBusy] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);
  const requestId = state.status === "success" ? state.data.request_id : "";

  function view(script: ScriptKey, rank: number) {
    navigate(`/preview?request=${requestId}&script=${script}&rank=${rank}`);
  }

  async function prepare(script: ScriptKey, rank: number) {
    setBusy(true);
    setPrepareError(null);
    try {
      const job = await createJob({
        request_id: requestId,
        script,
        rank,
        layout: DEFAULT_LAYOUT,
      });
      navigate(`/jobs?highlight=${job.id}`);
    } catch (e) {
      setPrepareError(e instanceof Error ? e.message : "No se pudo preparar el trabajo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <NameForm loading={state.status === "loading"} onSubmit={convert} />

      <div aria-live="polite" className="space-y-4">
        {state.status === "loading" && <p className="text-2xl">Convirtiendo tu nombre…</p>}
        {state.status === "error" && (
          <p
            role="alert"
            className="rounded-xl border-4 border-red-800 bg-red-50 p-4 text-xl font-semibold text-red-900"
          >
            {state.message}
          </p>
        )}
        {prepareError && (
          <p role="alert" className="text-xl font-semibold text-red-800">
            {prepareError}
          </p>
        )}
        {state.status === "success" && (
          <>
            <p className="text-xl">
              Resultado para <strong>{state.data.input}</strong>
              <span className="text-slate-700"> · sílabas: {state.data.syllables.join("-")}</span>
            </p>
            <div className="grid gap-6 lg:grid-cols-2">
              <ZhCard
                key={`zh-${requestId}`}
                options={state.data.zh}
                busy={busy}
                onView={(rank) => view("zh", rank)}
                onPrepare={(rank) => void prepare("zh", rank)}
              />
              <JaCard
                key={`ja-${requestId}`}
                options={state.data.ja}
                busy={busy}
                onView={() => view("ja", 1)}
                onPrepare={() => void prepare("ja", 1)}
              />
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
