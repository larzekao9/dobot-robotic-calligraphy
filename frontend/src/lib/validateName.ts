const VALID_CHARS = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'’\- ]+$/;
const MAX_LEN = 60;
const MAX_WORDS = 4;

/** Mismas reglas que el backend (sección 7 del plan). Devuelve el mensaje de error o null. */
export function validateName(raw: string): string | null {
  const name = raw.trim();
  if (!name) return "Escribe un nombre.";
  if (name.length > MAX_LEN) return `El nombre no puede superar ${MAX_LEN} caracteres.`;
  if (!VALID_CHARS.test(name)) {
    return "Solo se permiten letras, espacios, guiones y apóstrofes.";
  }
  if (name.split(/[\s-]+/).filter(Boolean).length > MAX_WORDS) {
    return `Usa como máximo ${MAX_WORDS} palabras.`;
  }
  return null;
}
