import { useCallback, useRef, useState } from "react";
import { convertName } from "../api/client";
import type { Conversion } from "../api/types";

export type ConvertState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: Conversion }
  | { status: "error"; message: string };

export function useConvert() {
  const [state, setState] = useState<ConvertState>({ status: "idle" });
  const latest = useRef(0);

  const convert = useCallback(async (name: string) => {
    const id = ++latest.current; // ignora respuestas de consultas anteriores
    setState({ status: "loading" });
    try {
      const data = await convertName(name);
      if (id === latest.current) setState({ status: "success", data });
    } catch (e) {
      if (id === latest.current) {
        const message = e instanceof Error ? e.message : "Ocurrió un error inesperado.";
        setState({ status: "error", message });
      }
    }
  }, []);

  return { state, convert };
}
