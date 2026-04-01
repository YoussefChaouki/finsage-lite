/**
 * FilingSelector — dropdown to pick an ingested SEC filing.
 *
 * Options are formatted as "AAPL — FY2024 (Apple Inc.)".
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDocuments } from "@/hooks/useDocuments";

interface FilingSelectorProps {
  value: string | null;
  onChange: (id: string) => void;
}

export function FilingSelector({ value, onChange }: FilingSelectorProps) {
  const { documents, isLoading } = useDocuments();

  return (
    <Select value={value ?? ""} onValueChange={onChange} disabled={isLoading}>
      <SelectTrigger className="w-full bg-slate-900 border-slate-700 text-slate-200 focus:ring-emerald-500/50">
        <SelectValue placeholder={isLoading ? "Loading filings…" : "Select a filing…"} />
      </SelectTrigger>
      <SelectContent className="bg-slate-900 border-slate-700 text-slate-200">
        {documents.length === 0 && !isLoading ? (
          <div className="py-6 text-center text-sm text-slate-500">
            No filings ingested yet
          </div>
        ) : (
          documents.map((doc) => (
            <SelectItem
              key={doc.id}
              value={doc.id}
              className="text-slate-200 focus:bg-slate-800 focus:text-slate-100"
            >
              {doc.ticker} — FY{doc.fiscal_year} ({doc.company_name})
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  );
}
