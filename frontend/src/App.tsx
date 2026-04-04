import { useCallback, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Keyboard } from "lucide-react";
import { Toaster } from "sonner";
import { MainLayout } from "@/components/layout/MainLayout";
import SearchPage from "@/pages/SearchPage";
import BrowsePage from "@/pages/BrowsePage";
import DocumentsPage from "@/pages/DocumentsPage";
import NotFoundPage from "@/pages/NotFoundPage";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useGlobalShortcuts } from "@/hooks/useKeyboardShortcuts";

const fadeVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
};

const SHORTCUTS = [
  { keys: ["⌘", "K"], description: "Focus search" },
  { keys: ["⌘", "/"], description: "Show keyboard shortcuts" },
  { keys: ["Esc"], description: "Clear search results" },
] as const;

/** Animated page wrapper — fades in/out on route change. */
function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        variants={fadeVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="flex h-full flex-col"
      >
        <Routes location={location}>
          <Route path="/" element={<SearchPage />} />
          <Route path="/browse" element={<BrowsePage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

/** Inner app — must be inside BrowserRouter to use router hooks. */
function AppInner() {
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const openShortcuts = useCallback(() => setShortcutsOpen(true), []);

  usePageTitle();
  useGlobalShortcuts(openShortcuts);

  return (
    <>
      <MainLayout>
        <AnimatedRoutes />
      </MainLayout>

      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          classNames: {
            toast: "border-slate-700 bg-slate-900 text-slate-100",
            success: "border-emerald-800",
            error: "border-red-800",
          },
        }}
      />

      {/* Global keyboard shortcuts dialog — Cmd/Ctrl+/ */}
      <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
        <DialogContent className="border-slate-800 bg-slate-900 sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-slate-100">
              <Keyboard className="h-4 w-4 text-emerald-400" />
              Keyboard Shortcuts
            </DialogTitle>
            <DialogDescription className="text-slate-500">
              Navigate FinSage-Lite without lifting your hands.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-1 pt-1">
            {SHORTCUTS.map(({ keys, description }) => (
              <div
                key={description}
                className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-slate-800/60"
              >
                <span className="text-sm text-slate-300">{description}</span>
                <div className="flex items-center gap-1">
                  {keys.map((key) => (
                    <kbd
                      key={key}
                      className="rounded border border-slate-700 bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-slate-400"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInner />
    </BrowserRouter>
  );
}
