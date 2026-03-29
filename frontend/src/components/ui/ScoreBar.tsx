import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ScoreBarProps {
  /** Normalised relevance score in [0, 1]. */
  score: number;
  showValue?: boolean;
  className?: string;
}

function scoreColor(score: number): string {
  if (score >= 0.8) return "bg-emerald-500";
  if (score >= 0.6) return "bg-amber-500";
  return "bg-red-500";
}

/**
 * Horizontal progress bar representing a retrieval relevance score.
 * Colour thresholds: emerald ≥ 0.8, amber ≥ 0.6, red below.
 * Exact percentage shown in a tooltip on hover.
 */
export function ScoreBar({ score, showValue = true, className }: ScoreBarProps) {
  const pct = Math.round(score * 100);
  const color = scoreColor(score);

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={cn("flex items-center gap-2", className)}>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
              <div
                className={cn("h-full rounded-full transition-all", color)}
                style={{ width: `${pct}%` }}
              />
            </div>
            {showValue && (
              <span className="w-8 text-right font-mono text-[10px] text-slate-400">
                {score.toFixed(2)}
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          Relevance: {pct}%
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
