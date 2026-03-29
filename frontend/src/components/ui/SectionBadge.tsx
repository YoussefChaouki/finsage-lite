import { cn } from "@/lib/utils";
import { SECTION_COLORS, SECTION_LABELS } from "@/lib/constants";
import type { SectionType } from "@/lib/types";

interface SectionBadgeProps {
  section: SectionType;
  /** "sm" shows short key (ITEM_1A), "md" shows full label (Risk Factors) */
  variant?: "sm" | "md";
  className?: string;
}

/**
 * Coloured badge for SEC 10-K section types.
 * Colours are defined in SECTION_COLORS and match the design system.
 */
export function SectionBadge({
  section,
  variant = "sm",
  className,
}: SectionBadgeProps) {
  const style = SECTION_COLORS[section];
  const label =
    variant === "md" ? SECTION_LABELS[section] : section.replace("_", " ");

  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 font-mono font-medium",
        variant === "sm" ? "py-0 text-[10px]" : "py-0.5 text-xs",
        style.badge,
        className,
      )}
    >
      {label}
    </span>
  );
}
