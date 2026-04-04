import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const TITLES: Record<string, string> = {
  "/": "Search — FinSage-Lite",
  "/browse": "Browse — FinSage-Lite",
  "/documents": "Documents — FinSage-Lite",
};

/** Updates document.title on each route change. Must be mounted inside BrowserRouter. */
export function usePageTitle(): void {
  const { pathname } = useLocation();

  useEffect(() => {
    document.title = TITLES[pathname] ?? "FinSage-Lite";
  }, [pathname]);
}
