import { useState, type FormEvent } from "react";
import { validateName } from "../lib/validateName";

interface Props {
  loading: boolean;
  onSubmit: (name: string) => void;
}

export function NameForm({ loading, onSubmit }: Props) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const problem = validateName(value);
    setError(problem);
    if (!problem) onSubmit(value.trim());
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-3">
      <label htmlFor="name" className="block text-2xl font-semibold">
        Tu nombre
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          id="name"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoComplete="off"
          autoCapitalize="words"
          placeholder="Por ejemplo: María José"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "name-error" : undefined}
          className="min-h-16 flex-1 rounded-xl border-4 border-slate-900 px-4 text-3xl focus:outline-none focus:ring-4 focus:ring-indigo-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="min-h-16 rounded-xl bg-indigo-800 px-8 text-2xl font-bold text-white hover:bg-indigo-900 focus:outline-none focus:ring-4 focus:ring-indigo-400 disabled:cursor-wait disabled:opacity-60"
        >
          {loading ? "Convirtiendo…" : "Convertir"}
        </button>
      </div>
      {error && (
        <p id="name-error" role="alert" className="text-xl font-semibold text-red-800">
          {error}
        </p>
      )}
    </form>
  );
}
