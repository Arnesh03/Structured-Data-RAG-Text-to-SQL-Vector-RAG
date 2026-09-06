"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";

/**
 * Light/dark toggle.
 *
 * The `dark` class on <html> is the single source of truth: the blocking
 * script in layout.tsx sets it before first paint, and this reads it back
 * through an external store rather than mirroring it into React state. That
 * keeps the two from drifting, and renders `false` on the server so hydration
 * matches whatever the script decided.
 */
const subscribe = (onChange: () => void) => {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
};

const isDark = () => document.documentElement.classList.contains("dark");

export function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe, isDark, () => false);

  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* storage blocked - the toggle still works for this session */
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="flex size-8 items-center justify-center rounded-full text-muted transition duration-300 hover:bg-surface-2 hover:text-text"
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
