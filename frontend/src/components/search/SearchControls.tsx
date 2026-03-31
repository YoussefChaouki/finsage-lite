/**
 * SearchControls — filter row below the SearchBar.
 *
 * - Company select (populated from /api/v1/documents)
 * - Year select (filtered to the chosen company)
 * - Dense / BM25 / Hybrid mode toggle
 * - HyDE switch with tooltip
 *
 * All state lives in the Zustand appStore so it persists across navigations.
 */

import { useMemo } from "react";
import { Info } from "lucide-react";
import { useAppStore } from "@/store/appStore";
import { useDocuments } from "@/hooks/useDocuments";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { SearchMode } from "@/lib/types";

const MODES: { value: SearchMode; label: string }[] = [
  { value: "dense", label: "Dense" },
  { value: "sparse", label: "BM25" },
  { value: "hybrid", label: "Hybrid" },
];

export function SearchControls() {
  const {
    selectedCompany,
    selectedYear,
    selectedMode,
    hydeEnabled,
    setCompany,
    setYear,
    setMode,
    toggleHyde,
  } = useAppStore();

  const { documents } = useDocuments();

  // Deduplicated list of companies
  const companies = useMemo(() => {
    const seen = new Set<string>();
    return documents.filter((d) => {
      if (seen.has(d.company_name)) return false;
      seen.add(d.company_name);
      return true;
    });
  }, [documents]);

  // Fiscal years filtered by the selected company
  const years = useMemo(() => {
    const filtered = selectedCompany
      ? documents.filter((d) => d.company_name === selectedCompany)
      : documents;
    const yearSet = new Set(filtered.map((d) => d.fiscal_year));
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [documents, selectedCompany]);

  const handleCompanyChange = (v: string) => {
    setCompany(v === "__all__" ? null : v);
    setYear(null); // reset dependent year filter
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Company */}
      <Select
        value={selectedCompany ?? "__all__"}
        onValueChange={handleCompanyChange}
      >
        <SelectTrigger className="h-8 w-44 border-slate-700 bg-slate-900 text-sm text-slate-300 focus:ring-emerald-500/40">
          <SelectValue placeholder="All companies" />
        </SelectTrigger>
        <SelectContent className="border-slate-700 bg-slate-900">
          <SelectItem value="__all__" className="text-slate-400">
            All companies
          </SelectItem>
          {companies.map((d) => (
            <SelectItem
              key={d.company_name}
              value={d.company_name}
              className="text-slate-300"
            >
              {d.ticker} — {d.company_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Fiscal year */}
      <Select
        value={selectedYear?.toString() ?? "__all__"}
        onValueChange={(v) => setYear(v === "__all__" ? null : Number(v))}
      >
        <SelectTrigger className="h-8 w-28 border-slate-700 bg-slate-900 text-sm text-slate-300 focus:ring-emerald-500/40">
          <SelectValue placeholder="All years" />
        </SelectTrigger>
        <SelectContent className="border-slate-700 bg-slate-900">
          <SelectItem value="__all__" className="text-slate-400">
            All years
          </SelectItem>
          {years.map((y) => (
            <SelectItem key={y} value={y.toString()} className="text-slate-300">
              FY{y}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Mode toggle group */}
      <div className="flex overflow-hidden rounded-lg border border-slate-700">
        {MODES.map((mode) => (
          <button
            key={mode.value}
            type="button"
            onClick={() => setMode(mode.value)}
            className={cn(
              "px-3 py-1 text-xs font-medium transition-colors",
              selectedMode === mode.value
                ? "bg-emerald-600 text-white"
                : "bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200",
            )}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* HyDE switch */}
      <div className="flex items-center gap-1.5">
        <Switch
          id="hyde-switch"
          checked={hydeEnabled}
          onCheckedChange={toggleHyde}
          className="h-5 w-9 data-[state=checked]:bg-emerald-600"
        />
        <label
          htmlFor="hyde-switch"
          className="cursor-pointer select-none text-xs text-slate-400"
        >
          HyDE
        </label>
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="h-3.5 w-3.5 cursor-help text-slate-600" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[260px] text-xs">
              Hypothetical Document Embeddings: generates a synthetic passage
              matching your query to improve dense retrieval quality. Requires
              Ollama to be running.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
}
