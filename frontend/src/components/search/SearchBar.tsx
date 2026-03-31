/**
 * SearchBar — main search input with keyboard shortcut hint.
 *
 * Exposed via forwardRef so the parent can imperatively focus the input
 * (⌘K shortcut) or set its value (example queries).
 */

import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SearchBarHandle {
  focus: () => void;
  setValue: (value: string) => void;
}

interface SearchBarProps {
  onSubmit: (query: string) => void;
  isLoading: boolean;
  defaultValue?: string;
}

export const SearchBar = forwardRef<SearchBarHandle, SearchBarProps>(
  function SearchBar({ onSubmit, isLoading, defaultValue = "" }, ref) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [value, setValue] = useState(defaultValue);

    useImperativeHandle(
      ref,
      () => ({
        focus: () => inputRef.current?.focus(),
        setValue,
      }),
      [setValue],
    );

    const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const trimmed = value.trim();
      if (!trimmed || isLoading) return;
      onSubmit(trimmed);
    };

    return (
      <form onSubmit={handleSubmit} className="flex w-full items-stretch">
        {/* Input */}
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 z-10 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Ask anything about SEC 10-K filings..."
            className={cn(
              "w-full rounded-l-xl border border-r-0 border-slate-700 bg-slate-900",
              "py-4 pl-12 pr-16 text-lg text-slate-100 placeholder:text-slate-500",
              "transition-colors duration-200",
              "focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/40",
            )}
          />
          {/* ⌘K hint — only visible when input is empty */}
          {!value && (
            <kbd className="pointer-events-none absolute right-4 top-1/2 hidden -translate-y-1/2 select-none items-center gap-1 rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 sm:flex">
              ⌘K
            </kbd>
          )}
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={isLoading || !value.trim()}
          className={cn(
            "flex items-center gap-2 rounded-r-xl border border-emerald-600 bg-emerald-600 px-6 py-4",
            "text-base font-medium text-white",
            "transition-all duration-200",
            "hover:border-emerald-500 hover:bg-emerald-500",
            "active:bg-emerald-700",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-950",
          )}
        >
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Search className="h-5 w-5" />
          )}
          <span className="hidden sm:inline">Search</span>
        </button>
      </form>
    );
  },
);
