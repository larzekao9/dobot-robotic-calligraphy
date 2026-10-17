import type { JaOption } from "../api/types";
import { AudioButton } from "./AudioButton";
import { ResultCard, SourceBadge, type CardActions } from "./ResultCard";

export function JaCard({ options, onView, onPrepare, busy }: { options: JaOption[] } & CardActions) {
  const option = options[0];

  return (
    <ResultCard
      title="Japonés (katakana)"
      busy={busy}
      onView={option && onView}
      onPrepare={option && onPrepare}
    >
      {option ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p lang="ja" aria-label="Nombre en japonés" className="font-jp text-7xl leading-tight">
                {option.text}
              </p>
              <p className="text-3xl font-medium text-slate-700">{option.romaji}</p>
            </div>
            <AudioButton text={option.text} lang="ja" size="lg" label="Escuchar pronunciación en japonés" />
          </div>
          <SourceBadge source={option.source} verified={option.verified} />
        </>
      ) : (
        <p className="text-xl">No pudimos convertir este nombre al japonés.</p>
      )}
    </ResultCard>
  );
}
