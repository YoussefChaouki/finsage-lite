import { Link } from "react-router-dom";

/** 404 — route not found. */
export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
      <div className="space-y-1">
        <p className="text-6xl font-semibold text-slate-700">404</p>
        <p className="text-slate-400 text-sm">Page not found.</p>
      </div>
      <Link
        to="/"
        className="text-xs text-sky-400 hover:text-sky-300 underline underline-offset-4 transition-colors"
      >
        Back to Search
      </Link>
    </div>
  );
}
