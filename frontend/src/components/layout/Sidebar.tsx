import { NavLink } from "react-router-dom";
import { Search, FolderOpen, FileText, Menu, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { getHealth } from "@/lib/api";
import { APP_NAME, POLLING_INTERVAL } from "@/lib/constants";

const NAV_ITEMS = [
  { to: "/", label: "Search", desc: "Query 10-K filings", Icon: Search, end: true },
  { to: "/browse", label: "Browse", desc: "Navigate by section", Icon: FolderOpen, end: false },
  { to: "/documents", label: "Documents", desc: "Manage filings", Icon: FileText, end: false },
] as const;

/**
 * Fixed sidebar with gradient background, icon-box nav, and system status card.
 * Collapses to icon rail on narrow screens.
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
      {/* Mobile toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="fixed top-3 left-3 z-50 flex h-8 w-8 items-center justify-center rounded-md bg-slate-800 text-slate-400 lg:hidden"
        aria-label="Toggle sidebar"
      >
        {collapsed ? <Menu size={16} /> : <X size={16} />}
      </button>

      <aside
        className={cn(
          "flex h-screen flex-col border-r border-white/[0.05] transition-all duration-200",
          "lg:relative lg:translate-x-0",
          "fixed inset-y-0 left-0 z-40",
          collapsed
            ? "-translate-x-full lg:w-16 lg:translate-x-0"
            : "w-64 translate-x-0",
        )}
        style={{
          background: "linear-gradient(180deg, #08121f 0%, #070e1b 45%, #060b16 100%)",
        }}
      >
        {/* ── Logo ───────────────────────────────────────────── */}
        <div
          className={cn(
            "flex h-16 shrink-0 items-center border-b",
            collapsed ? "justify-center px-4" : "gap-3 px-5",
          )}
          style={{ borderColor: "rgba(255,255,255,0.05)" }}
        >
          {/* Geometric star mark */}
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
            style={{
              background: "linear-gradient(135deg, #10b981 0%, #047857 100%)",
              boxShadow:
                "0 0 20px rgba(16,185,129,0.22), inset 0 1px 0 rgba(255,255,255,0.18)",
            }}
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4 fill-white" aria-hidden>
              <path d="M8 0.8L10.1 5.9L15.5 8L10.1 10.1L8 15.2L5.9 10.1L0.5 8L5.9 5.9L8 0.8Z" />
            </svg>
          </div>

          {!collapsed && (
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-display text-[15px] font-bold leading-none tracking-tight text-white">
                  {APP_NAME.replace("-Lite", "")}
                </span>
                <span
                  className="rounded px-1.5 py-px font-mono text-[9px] font-bold uppercase tracking-widest text-emerald-400"
                  style={{
                    background: "rgba(16,185,129,0.12)",
                    border: "1px solid rgba(16,185,129,0.22)",
                  }}
                >
                  Lite
                </span>
              </div>
              <p className="mt-0.5 text-[10px] tracking-wide text-slate-600">
                SEC 10-K Intelligence
              </p>
            </div>
          )}
        </div>

        {/* ── Navigation ─────────────────────────────────────── */}
        <nav
          className={cn(
            "flex flex-1 flex-col overflow-y-auto py-3",
            collapsed ? "gap-1 px-2" : "gap-0.5 px-3",
          )}
        >
          {NAV_ITEMS.map(({ to, label, desc, Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              {({ isActive }) => (
                <div
                  className={cn(
                    "group relative flex cursor-pointer items-center rounded-xl transition-all duration-150",
                    collapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5",
                    isActive ? "text-emerald-400" : "text-slate-400 hover:text-slate-100",
                  )}
                  style={
                    isActive
                      ? {
                          background:
                            "linear-gradient(135deg, rgba(16,185,129,0.12) 0%, rgba(16,185,129,0.04) 100%)",
                          boxShadow: "inset 0 0 0 1px rgba(16,185,129,0.14)",
                        }
                      : undefined
                  }
                >
                  {/* Active left accent bar */}
                  {isActive && !collapsed && (
                    <div
                      className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full"
                      style={{
                        background: "linear-gradient(180deg, #10b981 0%, #059669 100%)",
                      }}
                    />
                  )}

                  {/* Icon box */}
                  <div
                    className={cn(
                      "flex shrink-0 items-center justify-center rounded-lg transition-all",
                      collapsed ? "h-9 w-9" : "h-8 w-8",
                    )}
                    style={
                      isActive
                        ? { background: "rgba(16,185,129,0.14)" }
                        : {
                            background: "rgba(255,255,255,0.04)",
                          }
                    }
                  >
                    <Icon
                      size={collapsed ? 17 : 15}
                      className={cn(
                        isActive
                          ? "text-emerald-400"
                          : "text-slate-500 group-hover:text-slate-300",
                      )}
                    />
                  </div>

                  {/* Label + description */}
                  {!collapsed && (
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-semibold leading-tight">{label}</p>
                      <p
                        className={cn(
                          "mt-px text-[11px] leading-tight",
                          isActive
                            ? "text-emerald-500/50"
                            : "text-slate-600 group-hover:text-slate-500",
                        )}
                      >
                        {desc}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* ── Attribution ────────────────────────────────────── */}
        {!collapsed && (
          <div className="shrink-0 px-5 pb-2">
            <p className="font-mono text-[10px] text-slate-700">
              © 2025 Youssef Chaouki
            </p>
          </div>
        )}

        {/* ── System status card ──────────────────────────────── */}
        <div className={cn("shrink-0 pb-5", collapsed ? "px-2" : "px-4")}>
          <div
            className="overflow-hidden rounded-xl"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            {!collapsed && (
              <div
                className="border-b px-3 py-2.5"
                style={{ borderColor: "rgba(255,255,255,0.05)" }}
              >
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-600">
                  System
                </p>
              </div>
            )}
            <div className={cn("space-y-px", collapsed ? "p-2" : "p-2.5")}>
              {/* API row */}
              <div
                className={cn(
                  "flex items-center rounded-lg px-2 py-1.5",
                  collapsed ? "justify-center" : "justify-between",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                    {apiOnline && (
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-50" />
                    )}
                    <span
                      className={cn(
                        "relative inline-flex h-1.5 w-1.5 rounded-full",
                        apiOnline ? "bg-emerald-500" : "bg-red-500/70",
                      )}
                    />
                  </span>
                  {!collapsed && (
                    <span className="text-xs font-medium text-slate-400">API</span>
                  )}
                </div>
                {!collapsed && (
                  <span
                    className={cn(
                      "font-mono text-[10px]",
                      apiOnline ? "text-emerald-500" : "text-red-500/70",
                    )}
                  >
                    {apiOnline ? "online" : "offline"}
                  </span>
                )}
              </div>

              {/* LLM row */}
              <div
                className={cn(
                  "flex items-center rounded-lg px-2 py-1.5",
                  collapsed ? "justify-center" : "justify-between",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                    {llmOnline && (
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-violet-400 opacity-40" />
                    )}
                    <span
                      className={cn(
                        "relative inline-flex h-1.5 w-1.5 rounded-full",
                        llmOnline ? "bg-violet-400" : "bg-slate-600",
                      )}
                    />
                  </span>
                  {!collapsed && (
                    <span className="text-xs font-medium text-slate-400">LLM</span>
                  )}
                </div>
                {!collapsed && (
                  <span
                    className={cn(
                      "font-mono text-[10px]",
                      llmOnline ? "text-violet-400" : "text-slate-600",
                    )}
                  >
                    {llmOnline ? "ollama" : "offline"}
                  </span>
                )}
              </div>
            </div>
          </div>
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
