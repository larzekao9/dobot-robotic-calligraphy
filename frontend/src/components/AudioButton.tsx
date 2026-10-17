import { useState } from "react";
import { isSpeechSupported, speak } from "../lib/speech";

interface AudioButtonProps {
  text: string;
  lang: "zh" | "ja";
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function AudioButton({
  text,
  lang,
  label = "Escuchar pronunciación",
  size = "md",
  className = "",
}: AudioButtonProps) {
  const [playing, setPlaying] = useState(false);

  if (!isSpeechSupported()) {
    return null;
  }

  const handlePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPlaying(true);
    speak(text, lang, () => setPlaying(false));
  };

  const sizeStyles = {
    sm: "px-2.5 py-1 text-sm gap-1.5",
    md: "px-3.5 py-1.5 text-base gap-2",
    lg: "px-5 py-2.5 text-xl gap-2.5",
  };

  return (
    <button
      type="button"
      onClick={handlePlay}
      title={label}
      aria-label={label}
      className={`inline-flex items-center justify-center font-semibold rounded-xl border-2 transition-all active:scale-95 ${
        playing
          ? "bg-amber-100 border-amber-600 text-amber-900 shadow-inner"
          : "bg-slate-100 hover:bg-indigo-50 border-slate-300 hover:border-indigo-600 text-slate-800 hover:text-indigo-900 shadow-sm"
      } ${sizeStyles[size]} ${className}`}
    >
      <span className={playing ? "animate-pulse" : ""}>
        {playing ? "🔊" : "🔉"}
      </span>
      <span>{playing ? "Escuchando…" : "Pronunciar"}</span>
    </button>
  );
}
