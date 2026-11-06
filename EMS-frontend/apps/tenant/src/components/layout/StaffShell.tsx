"use client";

import { useState, type ReactNode } from "react";
import { StaffSidebar } from "./StaffSidebar";
import { StaffTopbar } from "./StaffTopbar";

type StaffShellProps = {
  children: ReactNode;
};

export function StaffShell({ children }: StaffShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-paper text-ink">
      <div className="hidden lg:sticky lg:top-0 lg:flex lg:h-screen lg:shrink-0">
        <StaffSidebar />
      </div>

      {drawerOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 bg-ink/40"
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 border-r border-ink/20 bg-paper">
            <StaffSidebar onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <StaffTopbar onMenuClick={() => setDrawerOpen(true)} />
        <main className="flex-1 bg-paper px-4 py-6 md:px-8 md:py-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
