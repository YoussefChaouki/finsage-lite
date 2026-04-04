/**
 * SearchEmptyState — premium pre-search hero.
 *
 * Aesthetic direction: "Institutional Terminal"
 *   Left  — editorial headline + number-led feature list + terminal-style query buttons
 *   Right — glass panel with macOS chrome, typewriter answer, score-fill source cards
 *
 * The demo loops automatically: type → show sources → 6 s pause → reset.
 */

import { useEffect, useRef, useState } from "react";
import type { ComponentType } from "react";
import { Brain, Lock, Sparkles, Zap } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

// ─── Props ────────────────────────────────────────────────────────────────────

interface SearchEmptyStateProps {
  onExampleClick: (query: string) => void;
}

// ─── Static content ───────────────────────────────────────────────────────────

const EXAMPLES = [
  "What was Apple's revenue in FY2024?",
  "Compare risk factors to previous year",
  "What are the main growth drivers?",
] as const;

interface FeatureItem {
  icon: ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  accent: string;
}

const FEATURES: FeatureItem[] = [
  {
    icon: Zap,
    title: "Hybrid Retrieval",
    desc: "BM25 sparse + dense vectors fused with Reciprocal Rank Fusion for maximum recall.",
    accent: "text-emerald-400",
  },
  {
    icon: Brain,
    title: "HyDE Expansion",
    desc: "Hypothetical Document Embeddings expand analytical queries via a local Ollama LLM.",
    accent: "text-violet-400",
  },
  {
    icon: Lock,
    title: "Local-first & Private",
    desc: "Embeddings and LLM inference run entirely on your machine. Zero data egress.",
    accent: "text-sky-400",
  },
];

const TECH_TAGS = ["pgvector", "BM25", "MiniLM-L6", "Ollama", "FastAPI"] as const;

const DEMO_QUERY = "What was Apple's revenue in FY2024?";
const DEMO_ANSWER =
  "Apple reported total net sales of $391.0B in FY2024, a 2% increase year-over-year. The Services segment delivered exceptional 13% growth, reaching $96.2B and setting a new annual record.[1] iPhone remains the largest contributor at $201.0B, while Mac and iPad also showed strong performance.[2]";

const DEMO_SOURCES = [
  {
    id: "1",
    label: "ITEM 7",
    labelClass: "text-violet-400 border-violet-500/30 bg-violet-500/10",
    title: "Management's Discussion & Analysis",
    meta: "AAPL · FY2024",
    score: 0.94,
    snippet:
      "Services net sales increased $11.3B or 13% during 2024 compared to 2023, driven by higher net sales across all geographic segments...",
  },
  {
    id: "2",
    label: "ITEM 1",
    labelClass: "text-sky-400 border-sky-500/30 bg-sky-500/10",
    title: "Business — Products & Services",
    meta: "AAPL · FY2024",
    score: 0.87,
    snippet:
      "iPhone net sales were $201.0 billion during fiscal 2024, representing the majority of the Company's total net sales...",
  },
] as const;

// ─── Demo loop hook ───────────────────────────────────────────────────────────

function useDemoLoop(text: string) {
  const [displayed, setDisplayed] = useState("");
  const [showSources, setShowSources] = useState(false);
  const indexRef = useRef(0);

  useEffect(() => {
    let timeoutId = 0;
    let intervalId = 0;

    const start = () => {
      indexRef.current = 0;
      setDisplayed("");
      setShowSources(false);

      timeoutId = setTimeout(() => {
        intervalId = setInterval(() => {
          indexRef.current += 1;
          setDisplayed(text.slice(0, indexRef.current));
          if (indexRef.current >= text.length) {
            clearInterval(intervalId);
            setShowSources(true);
            timeoutId = setTimeout(start, 6000);
          }
        }, 20);
      }, 900);
    };

    start();
    return () => {
      clearTimeout(timeoutId);
      clearInterval(intervalId);
    };
  }, [text]);

  return { displayed, showSources };
}

// ─── Citation renderer ────────────────────────────────────────────────────────

function renderWithCitations(text: string) {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    if (/^\[\d+\]$/.test(part)) {
      return (
        <sup
          key={i}
          className="mx-0.5 inline-flex items-center rounded bg-emerald-500/20 px-1 py-px font-mono text-[9px] font-bold text-emerald-400"
        >
          {part.slice(1, -1)}
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// ─── Component ────────────────────────────────────────────────────────────────

export function SearchEmptyState({ onExampleClick }: SearchEmptyStateProps) {
  const { displayed, showSources } = useDemoLoop(DEMO_ANSWER);
  const isTyping = displayed.length < DEMO_ANSWER.length;

  return (
    <div className="grid gap-12 pb-12 pt-6 lg:grid-cols-[1fr_1.25fr] lg:items-start lg:gap-16">

      {/* ══════════════════════════════════════════════
          LEFT — editorial pitch
      ══════════════════════════════════════════════ */}
      <div className="flex flex-col gap-7">

        {/* Headline */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <p className="mb-4 font-mono text-xs font-medium uppercase tracking-[0.25em] text-emerald-600">
            SEC 10-K · Hybrid RAG
          </p>
          <h2 className="font-display text-4xl font-bold leading-[1.15] tracking-tight lg:text-[2.5rem]">
            <span className="text-slate-100">Unlock the intelligence</span>
            <br />
            <span className="font-light text-slate-500">buried in your</span>
            <br />
            <span className="text-emerald-400">annual filings.</span>
          </h2>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-slate-500">
            Ask natural language questions over SEC 10-K reports.
            Get cited answers powered by hybrid retrieval.
          </p>
        </motion.div>

        {/* Number-led feature list */}
        <div>
          <div className="mb-3 h-px bg-slate-800" />
          {FEATURES.map(({ icon: Icon, title, desc, accent }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, delay: 0.12 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="group flex items-start gap-4 border-b border-slate-800/60 py-4"
            >
              <span className={`mt-0.5 shrink-0 font-mono text-xs font-bold tabular-nums ${accent} opacity-50`}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0 flex-1">
                <div className="mb-1.5 flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${accent}`} />
                  <span className="text-sm font-semibold text-slate-200">{title}</span>
                </div>
                <p className="text-sm leading-relaxed text-slate-600">{desc}</p>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Tech stack row */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          className="flex flex-wrap gap-2"
        >
          {TECH_TAGS.map((tag) => (
            <span
              key={tag}
              className="rounded border border-slate-800 px-2.5 py-1 font-mono text-xs text-slate-600"
            >
              {tag}
            </span>
          ))}
        </motion.div>

        {/* Example queries */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.4 }}
        >
          <p className="mb-3 font-mono text-xs uppercase tracking-[0.2em] text-slate-600">
            Try asking
          </p>
          <div className="flex flex-col gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => onExampleClick(ex)}
                className="group flex items-center gap-3 rounded-lg border border-slate-800 bg-transparent px-4 py-3 text-left text-sm text-slate-500 transition-all duration-200 hover:border-emerald-500/25 hover:bg-emerald-500/[0.04] hover:text-slate-300"
              >
                <span className="font-mono text-emerald-700 transition-colors group-hover:text-emerald-500">
                  ›
                </span>
                {ex}
              </button>
            ))}
          </div>
        </motion.div>
      </div>

      {/* ══════════════════════════════════════════════
          RIGHT — live demo terminal panel
      ══════════════════════════════════════════════ */}
      <motion.div
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
        className="relative"
      >
        {/* Layered ambient glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute -inset-10 rounded-[3rem]"
          style={{
            background:
              "radial-gradient(ellipse at 60% 40%, rgba(16,185,129,0.10) 0%, transparent 65%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-6 -right-6 h-64 w-64 rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(16,185,129,0.07) 0%, transparent 70%)",
            filter: "blur(24px)",
          }}
        />

        {/* Panel */}
        <div
          className="relative overflow-hidden rounded-2xl"
          style={{
            background: "linear-gradient(145deg, #0d1424 0%, #070d18 100%)",
            boxShadow:
              "0 0 0 1px rgba(255,255,255,0.06), 0 32px 64px -16px rgba(0,0,0,0.7), 0 0 80px -24px rgba(16,185,129,0.15)",
          }}
        >
          {/* Dot-grid texture + top-right radial tint */}
          <div
            aria-hidden
            className="demo-panel-grid pointer-events-none absolute inset-0 opacity-40"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse at 90% 0%, rgba(16,185,129,0.06) 0%, transparent 55%)",
            }}
          />

          {/* ── Window chrome (macOS-style dots) ── */}
          <div
            className="relative flex items-center justify-between border-b px-5 py-4"
            style={{ borderColor: "rgba(255,255,255,0.05)" }}
          >
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-500/40" />
                <div className="h-3 w-3 rounded-full bg-amber-500/40" />
                <div className="h-3 w-3 rounded-full bg-emerald-500/40" />
              </div>
              <span className="font-mono text-xs text-slate-600">
                finsage — search
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span className="font-mono text-xs text-emerald-500/60">ready</span>
            </div>
          </div>

          {/* ── Terminal query line ── */}
          <div
            className="border-b px-5 py-4"
            style={{ borderColor: "rgba(255,255,255,0.04)" }}
          >
            <div className="flex items-start gap-2.5">
              <span className="mt-px select-none font-mono text-sm text-emerald-600/60">›</span>
              <span className="font-mono text-sm leading-relaxed text-slate-300">
                {DEMO_QUERY}
              </span>
            </div>
          </div>

          {/* ── Answer area ── */}
          <div className="p-5">
            {/* Section label */}
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-emerald-500" />
              <span className="font-mono text-xs font-semibold uppercase tracking-widest text-emerald-500/80">
                AI Synthesis
              </span>
              <AnimatePresence>
                {!isTyping && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="ml-auto font-mono text-xs text-slate-600"
                  >
                    147ms
                  </motion.span>
                )}
              </AnimatePresence>
            </div>

            {/* Typewriter text box */}
            <div
              className="min-h-[6rem] rounded-xl px-4 py-4"
              style={{
                background: "rgba(16,185,129,0.04)",
                border: "1px solid rgba(16,185,129,0.10)",
              }}
            >
              <p className="text-sm leading-[1.75] text-slate-300">
                {renderWithCitations(displayed)}
                {isTyping && (
                  <span
                    className="ml-px inline-block w-px animate-pulse align-text-bottom"
                    style={{
                      height: "1.1em",
                      background: "#10b981",
                    }}
                  />
                )}
              </p>
            </div>

            {/* ── Sources ── */}
            <AnimatePresence>
              {showSources && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                  className="mt-4"
                >
                  {/* Divider with label */}
                  <div className="mb-3 flex items-center gap-3">
                    <div
                      className="h-px flex-1"
                      style={{ background: "rgba(255,255,255,0.04)" }}
                    />
                    <span className="font-mono text-xs uppercase tracking-[0.2em] text-slate-700">
                      {DEMO_SOURCES.length} sources retrieved
                    </span>
                    <div
                      className="h-px flex-1"
                      style={{ background: "rgba(255,255,255,0.04)" }}
                    />
                  </div>

                  <div className="space-y-2.5">
                    {DEMO_SOURCES.map((src, i) => (
                      <motion.div
                        key={src.id}
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{
                          delay: i * 0.15,
                          duration: 0.3,
                          ease: [0.16, 1, 0.3, 1],
                        }}
                        className="relative overflow-hidden rounded-xl"
                        style={{
                          background: "rgba(255,255,255,0.025)",
                          border: "1px solid rgba(255,255,255,0.05)",
                        }}
                      >
                        {/* Relevance score background fill */}
                        <div
                          aria-hidden
                          className="pointer-events-none absolute inset-y-0 left-0"
                          style={{
                            width: `${src.score * 100}%`,
                            background:
                              "linear-gradient(90deg, rgba(16,185,129,0.08) 0%, transparent 100%)",
                          }}
                        />

                        <div className="relative p-4">
                          {/* Source header */}
                          <div className="flex items-center gap-2">
                            <span
                              className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-xs font-bold ${src.labelClass}`}
                            >
                              {src.label}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-400">
                              {src.title}
                            </span>
                            <span className="shrink-0 font-mono text-xs font-bold text-emerald-600">
                              {src.score.toFixed(2)}
                            </span>
                          </div>

                          {/* Snippet */}
                          <p className="mt-2 line-clamp-1 text-xs leading-relaxed text-slate-600">
                            {src.snippet}
                          </p>

                          {/* Meta + score bar */}
                          <div className="mt-2.5 flex items-center gap-3">
                            <span className="font-mono text-xs text-slate-700">
                              {src.meta}
                            </span>
                            <div className="flex flex-1 items-center gap-1.5">
                              <div
                                className="h-0.5 flex-1 overflow-hidden rounded-full"
                                style={{ background: "rgba(255,255,255,0.06)" }}
                              >
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${src.score * 100}%` }}
                                  transition={{
                                    delay: i * 0.15 + 0.2,
                                    duration: 0.6,
                                    ease: [0.16, 1, 0.3, 1],
                                  }}
                                  className="h-full rounded-full bg-emerald-500/60"
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
