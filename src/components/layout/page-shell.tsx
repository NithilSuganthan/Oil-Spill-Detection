"use client";

import * as React from "react";
import { TopNav, MobileNav } from "@/components/layout/top-nav";
import { SatelliteViewerModal } from "@/components/viewer/satellite-viewer-modal";

export function PageShell({
  children,
  maxWidth = "max-w-7xl",
  viewer = true,
}: {
  children: React.ReactNode;
  maxWidth?: string;
  viewer?: boolean;
}) {
  const [mobileNav, setMobileNav] = React.useState(false);
  return (
    <div className="flex min-h-screen flex-col">
      <TopNav onOpenMobileNav={() => setMobileNav(true)} />
      <MobileNav open={mobileNav} onClose={() => setMobileNav(false)} />
      <main className={`mx-auto w-full ${maxWidth} flex-1 px-4 py-6`}>{children}</main>
      <footer className="border-t border-line py-3 text-center font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint/70">
        SAGAR WATCH · Prototype · Mock Data Only
      </footer>
      {viewer && <SatelliteViewerModal />}
    </div>
  );
}
