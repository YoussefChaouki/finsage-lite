import { cn } from "@/lib/utils";

interface StatusDotProps {
  online: boolean;
  label: string;
  className?: string;
}

/**
 * Animated status indicator.
 * Green with ping animation when online, red when offline.
 */
export function StatusDot({ online, label, className }: StatusDotProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="relative flex h-2 w-2">
        {online && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
        )}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            online ? "bg-emerald-500" : "bg-red-500",
          )}
        />
      </span>
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  );
}
