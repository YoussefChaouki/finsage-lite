import React from "react";
import { cn } from "@/lib/utils";

interface SkeletonCardProps {
  /** Number of text line skeletons to render inside the card. */
  lines?: number;
  className?: string;
}

function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("animate-pulse rounded bg-slate-800", className)}
      style={style}
    />
  );
}

/**
 * Placeholder card shown while content is loading.
 * Renders a header strip and configurable number of text line skeletons.
 */
export function SkeletonCard({ lines = 3, className }: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-slate-800 bg-slate-900 p-4 space-y-3",
        className,
      )}
    >
      {/* Header row */}
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-24" />
      </div>
      {/* Text lines */}
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            className="h-3"
            style={{ width: i === lines - 1 ? "60%" : "100%" }}
          />
        ))}
      </div>
      {/* Score bar skeleton */}
      <Skeleton className="h-1.5 w-full" />
    </div>
  );
}
