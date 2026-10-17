/**
 * Reproducción de audio por síntesis de voz (Web Speech API)
 * Soporta chino mandarín (zh-TW / zh-CN) y japonés (ja-JP).
 */

export function isSpeechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string, lang: "zh" | "ja", onEnd?: () => void): void {
  if (!isSpeechSupported()) return;

  try {
    window.speechSynthesis.cancel();

    // Limpiar separadores antes de pronunciar
    const cleanText = text.replace(/[·・\s]/g, "");
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = lang === "zh" ? "zh-TW" : "ja-JP";
    utterance.rate = 0.85; // velocidad ligeramente pausada y clara
    utterance.pitch = 1.0;

    if (onEnd) {
      utterance.onend = () => onEnd();
      utterance.onerror = () => onEnd();
    }

    // Buscar voz óptima si el navegador tiene varias disponibles
    const voices = window.speechSynthesis.getVoices();
    const prefix = lang === "zh" ? "zh" : "ja";
    const matchingVoice = voices.find((v) => v.lang.startsWith(prefix));
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.warn("Error en reproducción de audio:", err);
    if (onEnd) onEnd();
  }
}
