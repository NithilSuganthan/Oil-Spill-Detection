"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar, Waves, Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "MONITOR" },
  { href: "/incidents", label: "INCIDENTS" },
  { href: "/analytics", label: "ANALYTICS" },
  { href: "/reports", label: "REPORTS" },
  { href: "/about", label: "ABOUT" },
] as const;

function useISTClock() {
  const [now, setNow] = React.useState<Date | null>(null);
  React.useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!now) return "--:--:--";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(now);
}

export function TopNav({ onOpenMobileNav }: { onOpenMobileNav?: () => void }) {
  const pathname = usePathname();
  const clock = useISTClock();

  return (
    <header className="relative z-40 flex h-14 shrink-0 items-center justify-between border-b border-line bg-base-900/90 px-4 backdrop-blur">
      <div className="flex items-center gap-6">
        {onOpenMobileNav && (
          <button
            aria-label="Open navigation"
            onClick={onOpenMobileNav}
            className="focus-ring rounded p-1.5 text-ink-dim hover:text-ink lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <Link href="/" className="focus-ring group flex items-center gap-3 rounded">
          <div className="relative flex h-8 w-8 items-center justify-center rounded border border-signal-cyan/30 bg-signal-cyan/10">
            <Radar className="h-4 w-4 text-signal-cyan" />
            <span className="absolute inset-0 animate-scan overflow-hidden rounded">
              <span className="absolute top-0 h-full w-1/3 bg-gradient-to-r from-transparent via-signal-cyan/15 to-transparent" />
            </span>
          </div>
          <div className="leading-tight">
            <p className="font-mono text-sm font-bold tracking-[0.22em] text-ink">
              SAGAR&nbsp;WATCH
            </p>
            <p className="hidden text-[10px] uppercase tracking-[0.18em] text-ink-faint sm:block">
              Oil Spill Intelligence System
            </p>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 lg:flex" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "focus-ring relative rounded px-3 py-1.5 font-mono text-[11px] tracking-[0.14em] transition-colors rounded",
                  active
                    ? "text-signal-cyan"
                    : "text-ink-dim hover:bg-base-700/50 hover:text-ink"
                )}
              >
                {item.label}
                {active && (
                  <span className="absolute inset-x-3 -bottom-[13px] h-px bg-signal-cyan" />
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center gap-1.5 rounded border border-line bg-base-850 px-2 py-1 md:flex">
          <Waves className="h-3.5 w-3.5 text-signal-teal" />
          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">
            Focus Area:
          </span>
          <span className="font-mono text-[11px] font-semibold tracking-wider text-ink">
            INDIA 🇮🇳
          </span>
        </div>

        <div className="flex items-center gap-2 rounded border border-line bg-base-850 px-2.5 py-1">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-signal-green" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-green" />
          </span>
          <span className="font-mono text-[11px] font-semibold tracking-widest text-signal-green">
            LIVE
          </span>
          <span className="hidden font-mono text-xs tabular-nums text-ink-dim sm:inline">
            {clock} <span className="text-ink-faint">IST</span>
          </span>
        </div>
      </div>
    </header>
  );
}

export function MobileNav({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        aria-label="Close navigation"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <nav className="panel absolute left-0 top-0 flex h-full w-60 animate-fade-in flex-col gap-1 rounded-none border-y-0 border-l-0 p-3">
        <p className="mb-2 px-2 font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
          Navigation
        </p>
        {NAV_ITEMS.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={cn(
                "rounded px-3 py-2 font-mono text-xs tracking-[0.14em]",
                active
                  ? "bg-signal-cyan/10 text-signal-cyan"
                  : "text-ink-dim hover:bg-base-700/60 hover:text-ink"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
