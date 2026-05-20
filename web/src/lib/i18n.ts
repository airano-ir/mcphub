// Tiny i18n: read translations from /api/i18n/{lang}, fall back to the key.
// We don't introduce react-i18next yet — the surface is small and most copy is hard-coded EN in the prototype.
import { useTranslations } from "./queries";
import { useUiStore } from "./store";

export function useT() {
  const lang = useUiStore((s) => s.lang);
  const { data } = useTranslations(lang);
  return (key: string, fallback?: string): string => {
    if (data && key in data) return data[key];
    return fallback ?? key;
  };
}
