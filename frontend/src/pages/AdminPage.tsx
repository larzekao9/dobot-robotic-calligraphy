import { useCallback, useMemo, useState } from "react";
import { adminApi } from "../api/client";
import { NamesTab, type NameDraft } from "../components/admin/NamesTab";
import { PendingTab } from "../components/admin/PendingTab";
import { SyllablesTab } from "../components/admin/SyllablesTab";
import { BTN } from "../components/admin/ui";
import { PageShell } from "../components/PageShell";

type Tab = "names" | "syllables" | "pending";
const TABS: [Tab, string][] = [
  ["names", "Diccionario"],
  ["syllables", "Sílabas"],
  ["pending", "Pendientes de revisión"],
];

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("names");
  const [prefill, setPrefill] = useState<NameDraft | null>(null);
  const api = useMemo(() => adminApi(), []);
  const clearPrefill = useCallback(() => setPrefill(null), []);

  return (
    <PageShell>
      <h2 className="text-3xl font-bold">Administración</h2>
      <div role="tablist" aria-label="Secciones de administración" className="flex flex-wrap gap-2">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`${BTN} ${tab === id ? "bg-slate-900 text-white" : ""}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "names" && <NamesTab api={api} prefill={prefill} onPrefillUsed={clearPrefill} />}
      {tab === "syllables" && <SyllablesTab api={api} />}
      {tab === "pending" && (
        <PendingTab
          api={api}
          onPromote={(draft) => {
            setPrefill(draft);
            setTab("names");
          }}
        />
      )}
    </PageShell>
  );
}
