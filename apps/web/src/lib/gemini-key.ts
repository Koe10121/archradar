const STORAGE_KEY = "archradar.byok.gemini_key";

export function isPlausibleGeminiKey(raw: string): boolean {
  const trimmed = raw.trim();
  if (trimmed.length < 20 || trimmed.length > 256) {
    return false;
  }
  return !/\s/.test(trimmed);
}

export function maskApiKey(key: string): string {
  const trimmed = key.trim();
  if (!trimmed) return "";
  if (trimmed.length < 10) return "••••";
  return `${trimmed.slice(0, 4)}••••••${trimmed.slice(-4)}`;
}

export function getSessionGeminiKey(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setSessionGeminiKey(raw: string): void {
  if (typeof window === "undefined") return;
  const trimmed = raw.trim();
  try {
    if (!trimmed) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.sessionStorage.setItem(STORAGE_KEY, trimmed);
  } catch {
    // Ignore storage quota / privacy mode errors cleanly
  }
}

export function clearSessionGeminiKey(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage errors cleanly
  }
}
