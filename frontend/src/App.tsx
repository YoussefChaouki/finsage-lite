/**
 * FinSage-Lite — Root application component.
 *
 * Minimal scaffold for Sprint 5.0 infrastructure setup.
 * Dark theme is applied globally via the "dark" class on <html> in index.css.
 */

function App() {
  return (
    <div className="min-h-screen bg-finsage-bg text-finsage-text flex items-center justify-center">
      <div className="text-center space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
          FinSage-Lite
        </h1>
        <p className="text-sm text-slate-400">
          SEC 10-K RAG — frontend infrastructure ready
        </p>
        <div className="flex items-center justify-center gap-2 text-xs text-emerald-500">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          Sprint 5.0 setup complete
        </div>
      </div>
    </div>
  );
}

export default App;
