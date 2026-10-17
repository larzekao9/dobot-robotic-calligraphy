import { useState } from "react";
import type { ZhOption } from "../api/types";
import { AudioButton } from "./AudioButton";
import { ResultCard, SourceBadge, type CardActions } from "./ResultCard";

interface Props extends Omit<CardActions, "onView" | "onPrepare"> {
  options: ZhOption[];
  onView?: (rank: number) => void;
  onPrepare?: (rank: number) => void;
}

export function ZhCard({ options, onView, onPrepare, busy }: Props) {
  const [index, setIndex] = useState(0);
  const option = options[index];

  if (!option) {
    return (
      <ResultCard title="Chino (mandarín)">
        <p className="text-xl">
          Todavía no tenemos caracteres para este nombre. Quedó pendiente de revisión.
        </p>
      </ResultCard>
    );
  }

  return (
    <ResultCard
      title="Chino (mandarín)"
      busy={busy}
      onView={onView && (() => onView(option.rank))}
      onPrepare={onPrepare && (() => onPrepare(option.rank))}
    >
      {options.length > 1 && (
        <div role="radiogroup" aria-label="Alternativas en chino" className="flex flex-wrap gap-2">
          {options.map((o, i) => (
            <button
              key={o.rank}
              type="button"
              role="radio"
              aria-checked={i === index}
              onClick={() => setIndex(i)}
              className={`min-h-12 rounded-xl border-4 px-4 text-xl font-semibold focus:outline-none focus:ring-4 focus:ring-indigo-400 ${
                i === index
                  ? "border-indigo-800 bg-indigo-800 text-white"
                  : "border-slate-900 bg-white text-slate-900"
              }`}
            >
              Opción {o.rank}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p lang="zh-Hans" aria-label="Nombre en chino" className="font-sc text-7xl leading-tight">
            {option.text}
          </p>
          <p className="text-3xl font-medium text-slate-700">{option.pinyin}</p>
        </div>
        <AudioButton text={option.text} lang="zh" size="lg" label="Escuchar pronunciación en chino mandarín" />
      </div>
      <SourceBadge source={option.source} verified={option.verified} />
      <ul className="divide-y-2 divide-slate-200 text-xl" aria-label="Significado de cada carácter">
        {option.chars.map((c, i) => (
          <li key={`${c.char}-${i}`} className="flex items-center justify-between py-2.5">
            <div className="flex items-baseline gap-4">
              <span lang="zh-Hans" className="font-sc text-4xl font-semibold">
                {c.char}
              </span>
              <span className="w-20 text-2xl font-medium text-indigo-700">{c.pinyin}</span>
              <span className={c.meaning ? "text-slate-800" : "text-slate-600"}>
                {c.meaning ?? "Sin significado registrado"}
              </span>
            </div>
            <AudioButton text={c.char} lang="zh" size="sm" label={`Pronunciar ${c.char}`} />
          </li>
        ))}
      </ul>
    </ResultCard>
  );
}
