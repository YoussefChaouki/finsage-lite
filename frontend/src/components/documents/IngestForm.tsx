import { useState, type FormEvent } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface IngestFormProps {
  onIngest: (ticker: string, year: number) => void;
  isLoading: boolean;
}

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = Array.from(
  { length: CURRENT_YEAR - 2019 },
  (_, i) => CURRENT_YEAR - i,
);

/**
 * Form to trigger SEC 10-K ingestion.
 * Ticker is auto-uppercased; year select covers 2020 → current year.
 */
export function IngestForm({ onIngest, isLoading }: IngestFormProps) {
  const [ticker, setTicker] = useState("");
  const [year, setYear] = useState<string>("");
  const [tickerError, setTickerError] = useState<string | null>(null);

  function validate(): boolean {
    if (!/^[A-Za-z0-9]{1,10}$/.test(ticker)) {
      setTickerError("Ticker must be 1–10 alphanumeric characters");
      return false;
    }
    setTickerError(null);
    return true;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate() || !year) return;
    onIngest(ticker.toUpperCase(), parseInt(year, 10));
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-400" htmlFor="ticker-input">
          Ticker
        </label>
        <Input
          id="ticker-input"
          placeholder="AAPL"
          value={ticker}
          onChange={(e) => {
            setTicker(e.target.value.toUpperCase());
            setTickerError(null);
          }}
          disabled={isLoading}
          className="w-32 font-mono uppercase"
          maxLength={10}
        />
        {tickerError && (
          <p className="text-xs text-red-400">{tickerError}</p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-400" htmlFor="year-select">
          Fiscal Year
        </label>
        <Select value={year} onValueChange={setYear} disabled={isLoading}>
          <SelectTrigger id="year-select" className="w-28">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            {YEAR_OPTIONS.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        type="submit"
        disabled={isLoading || !ticker || !year}
        className="gap-2 bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        <Download size={15} />
        {isLoading ? "Ingesting…" : "Ingest Filing"}
      </Button>
    </form>
  );
}
