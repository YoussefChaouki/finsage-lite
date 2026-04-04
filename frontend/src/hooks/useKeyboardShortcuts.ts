import { useEffect } from "react";

/** Registers a global Cmd/Ctrl+/ shortcut that calls onShowHelp. */
export function useGlobalShortcuts(onShowHelp: () => void): void {
  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        onShowHelp();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onShowHelp]);
}
