import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";

interface MainLayoutProps {
  children: ReactNode;
}

/**
 * Root layout: fixed sidebar on the left, scrollable main content on the right.
 * Each page renders inside `children` and owns its own header if needed.
 */
export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <Sidebar />
      <main className="flex flex-1 flex-col overflow-y-auto">{children}</main>
    </div>
  );
}
