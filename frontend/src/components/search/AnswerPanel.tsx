/**
 * AnswerPanel — displays the LLM-generated answer with a typewriter effect.
 *
 * Parses inline [N] citation markers and replaces them with CitationChip
 * components for bidirectional highlighting with SourceCards.
 *
 * The typewriter uses useRef for the current index (no re-render per tick)
 * and useState only for the displayed slice (triggers paint).
 */

import { useEffect, useRef, useState } from "react";
import { Clock, Sparkles } from "lucide-react";
import { CitationChip } from "./CitationChip";

export interface Citation {
  id: number;
  chunk_id: string;
}

interface AnswerPanelProps {
  answer: string;
  citations: Citation[];
  latencyMs: number | null;
  onHoverCitation: (chunkId: string | null) => void;
  onClickCitation: (chunkId: string) => void;
}

// ─── Citation parser ──────────────────────────────────────────────────────────

type TextSegment = { type: "text"; text: string };
type CitationSegment = { type: "citation"; number: number };
type Segment = TextSegment | CitationSegment;

const SUPER_TO_NUM: Record<string, number> = {
  "¹": 1,
  "²": 2,
  "³": 3,
  "⁴": 4,
  "⁵": 5,
  "⁶": 6,
  "⁷": 7,
  "⁸": 8,
  "⁹": 9,
};

/** Splits text into plain text segments and [N] citation segments. */
function parseSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  const pattern = /\[([¹²³⁴⁵⁶⁷⁸⁹\d]+)\]/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      segments.push({ type: "text", text: text.slice(last, match.index) });
    }
    const raw = match[1];
    const fromSuper = SUPER_TO_NUM[raw];
    const num = fromSuper !== undefined ? fromSuper : parseInt(raw, 10);
    if (!isNaN(num)) {
      segments.push({ type: "citation", number: num });
    }
    last = pattern.lastIndex;
  }

  if (last < text.length) {
    segments.push({ type: "text", text: text.slice(last) });
  }
  return segments;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function AnswerPanel({
  answer,
  citations,
  latencyMs,
  onHoverCitation,
  onClickCitation,
}: AnswerPanelProps) {
  const [displayedText, setDisplayedText] = useState("");
  // useRef for index: increments without causing re-renders
  const indexRef = useRef(0);

  useEffect(() => {
    // Reset for the new answer
    setDisplayedText("");
    indexRef.current = 0;

    if (!answer) return;

    const timerId = setInterval(() => {
      indexRef.current += 1;
      setDisplayedText(answer.slice(0, indexRef.current));
      if (indexRef.current >= answer.length) {
        clearInterval(timerId);
      }
    }, 15);

    return () => clearInterval(timerId);
  }, [answer]);

  const segments = parseSegments(displayedText);
  const isTyping = displayedText.length < answer.length;

  return (
    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-emerald-400" />
          <span className="text-sm font-semibold text-emerald-400">Answer</span>
          <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/20 px-1.5 py-0.5 font-medium text-[10px] text-emerald-400">
            AI Generated
          </span>
        </div>
        {latencyMs !== null && (
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <Clock className="h-3 w-3" />
            <span>{latencyMs.toLocaleString()}ms</span>
          </div>
        )}
      </div>

      {/* Typewriter text with inline citations */}
      <p className="text-sm leading-relaxed text-slate-200">
        {segments.map((seg, i) => {
          if (seg.type === "text") {
            return <span key={i}>{seg.text}</span>;
          }
          const citation = citations.find((c) => c.id === seg.number);
          if (!citation) {
            return (
              <span key={i} className="text-amber-400">
                [{seg.number}]
              </span>
            );
          }
          return (
            <CitationChip
              key={i}
              number={seg.number}
              chunkId={citation.chunk_id}
              onHover={onHoverCitation}
              onClick={onClickCitation}
            />
          );
        })}
        {/* Blinking cursor while typing */}
        {isTyping && (
          <span className="ml-0.5 inline-block h-[1em] w-0.5 animate-pulse bg-emerald-400 align-text-bottom" />
        )}
      </p>
    </div>
  );
}
