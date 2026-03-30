/**
 * CitationChip — amber inline badge for answer citations.
 *
 * Hover highlights the matching SourceCard; click scrolls to it.
 */

interface CitationChipProps {
  number: number;
  chunkId: string;
  onHover: (chunkId: string | null) => void;
  onClick: (chunkId: string) => void;
}

export function CitationChip({
  number,
  chunkId,
  onHover,
  onClick,
}: CitationChipProps) {
  return (
    <button
      type="button"
      className="inline-flex items-center justify-center min-w-[1.25rem] px-1 py-0 rounded text-[10px] leading-5 font-mono font-bold bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 hover:text-amber-300 transition-colors cursor-pointer align-baseline mx-0.5 focus:outline-none focus:ring-1 focus:ring-amber-500/60"
      onMouseEnter={() => onHover(chunkId)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(chunkId)}
    >
      {number}
    </button>
  );
}
