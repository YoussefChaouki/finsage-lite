import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { rebuildBm25Index } from "@/lib/api";

/**
 * Button that triggers a BM25 index rebuild after confirmation.
 * Shows a success toast with the indexed chunk count on completion.
 */
export function RebuildIndexButton() {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  async function handleConfirm() {
    setIsLoading(true);
    try {
      const { chunk_count } = await rebuildBm25Index();
      setOpen(false);
      toast.success(`BM25 index rebuilt — ${chunk_count.toLocaleString("en-US")} chunks indexed`);
    } catch {
      toast.error("Failed to rebuild BM25 index");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-slate-100">
          <RefreshCw size={14} />
          Rebuild Index
        </Button>
      </DialogTrigger>

      <DialogContent className="border-slate-800 bg-slate-900 text-slate-100">
        <DialogHeader>
          <DialogTitle>Rebuild BM25 Index</DialogTitle>
          <DialogDescription className="text-slate-400">
            This will reload all chunks from the database into the in-memory
            BM25 index. Required after ingesting new filings. The operation
            typically takes a few seconds.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={isLoading}
            className="text-slate-400 hover:text-slate-200"
          >
            Cancel
          </Button>
          <Button
            onClick={() => void handleConfirm()}
            disabled={isLoading}
            className="gap-2 bg-emerald-600 text-white hover:bg-emerald-500"
          >
            {isLoading ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                Rebuilding…
              </>
            ) : (
              <>
                <RefreshCw size={14} />
                Confirm
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
