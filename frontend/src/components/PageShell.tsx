import type { ReactNode } from "react";
import { HeaderBar } from "./HeaderBar";

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl space-y-8 p-6 text-slate-900">
      <HeaderBar />
      {children}
    </main>
  );
}
