import { JobsPanel } from "../components/JobsPanel";
import { PageShell } from "../components/PageShell";

export function JobsPage({ params }: { params: URLSearchParams }) {
  return (
    <PageShell>
      <h2 className="text-3xl font-bold">Cola de trabajos</h2>
      <p className="text-lg text-slate-700">
        Por ahora los trabajos se ejecutan en un simulador: no se mueve ningún robot.
      </p>
      <JobsPanel highlight={params.get("highlight")} />
    </PageShell>
  );
}
