import { useCallback, useState } from "react";

export type Theme = "light" | "dark";

const THEME_KEY = "hs-theme";

export function getSavedTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* localStorage недоступен — светлая по умолчанию */
  }
  return "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = getSavedTheme();
    applyTheme(saved);
    return saved;
  });

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* сохранение не критично */
      }
      applyTheme(next);
      return next;
    });
  }, []);

  return { theme, toggle };
}
