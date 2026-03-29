import { NavLink } from "react-router-dom";
import { Search, FolderOpen, FileText, Menu, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { StatusDot } from "@/components/ui/StatusDot";
import { getHealth } from "@/lib/api";
import { APP_NAME, POLLING_INTERVAL } from "@/lib/constants";

const NAV_ITEMS = [
  { to: "/", label: "Search", Icon: Search, end: true },
  { to: "/browse", label: "Browse", Icon: FolderOpen, end: false },
  { to: "/documents", label: "Documents", Icon: FileText, end: false },
] as const;

/**
 * Fixed 240px sidebar with logo, navigation links, and live API/LLM status.
 * Collapses to an icon-only rail on screens < 1024px via a toggle button.
 */
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: POLLING_INTERVAL,
    retry: false,
  });

  const apiOnline = health?.status === "ok";
  const llmOnline = health?.ollama_available ?? false;

  return (
    <>
      {/* Mobile toggle (visible < lg) */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="fixed top-3 left-3 z-50 flex h-8 w-8 items-center justify-center rounded-md bg-slate-800 text-slate-400 lg:hidden"
        aria-label="Toggle sidebar"
      >
        {collapsed ? <Menu size={16} /> : <X size={16} />}
      </button>

      <aside
        className={cn(
          // Base styles
          "flex h-screen flex-col border-r border-slate-800 bg-slate-900 transition-all duration-200",
          // Desktop: always visible at fixed width
          "lg:relative lg:translate-x-0",
          // Mobile: overlay, toggled
          "fixed inset-y-0 left-0 z-40",
          collapsed
            ? "-translate-x-full lg:w-14 lg:translate-x-0"
            : "w-60 translate-x-0",
        )}
      >
        {/* ── Logo ─────────────────────────────────────────── */}
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-slate-800 px-4">
          <span className="text-base font-semibold tracking-tight text-slate-100">
            {APP_NAME.replace("-Lite", "")}
          </span>
          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/30">
            Lite
          </span>
        </div>

        {/* ── Navigation ───────────────────────────────────── */}
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
          {NAV_ITEMS.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-slate-800 text-slate-100"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
                )
              }
            >
              <Icon size={16} className="shrink-0" />
              <span
                className={cn(
                  "transition-all duration-200",
                  collapsed ? "lg:hidden" : "",
                )}
              >
                {label}
              </span>
            </NavLink>
          ))}
        </nav>

        {/* ── Status indicators ────────────────────────────── */}
        <div
          className={cn(
            "shrink-0 border-t border-slate-800 p-4 space-y-2",
            collapsed ? "lg:px-2" : "",
          )}
        >
          <StatusDot online={apiOnline} label="API" />
          <StatusDot online={llmOnline} label="LLM" />
        </div>
      </aside>

      {/* Mobile backdrop */}
      {!collapsed && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setCollapsed(true)}
        />
      )}
    </>
  );
}
