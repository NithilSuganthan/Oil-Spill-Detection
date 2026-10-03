"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar, Menu, Search } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "GLOBE" },
  { href: "/monitor", label: "MONITOR" },
  { href: "/investigate", label: "INVESTIGATE" },
  { href: "/live-analysis", label: "LIVE ANALYSIS" },
  { href: "/reports", label: "REPORTS" },
] as const;

function useISTClock() {
  const [now, setNow] = React.useState<Date | null>(null);
  React.useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!now) return { time: "--:--:--", date: "-- Sep ----" };
  const time = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(now);
  const date = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(now);
  return { time, date };
}

interface TopNavProps {
  onOpenMobileNav?: () => void;
  onSearch?: (query: string) => void;
}

export function TopNav({ onOpenMobileNav, onSearch }: TopNavProps) {
  const pathname = usePathname();
  const { time, date } = useISTClock();
  const [searchQuery, setSearchQuery] = React.useState("");

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim() && onSearch) {
      onSearch(searchQuery.trim());
    }
  };

  return (
    <header className="relative z-40 flex h-11 shrink-0 items-center justify-between border-b border-line/60 bg-base-950/95 px-4 backdrop-blur-md">
      <div className="flex items-center gap-5">
        {onOpenMobileNav && (
          <button
            aria-label="Open navigation"
            onClick={onOpenMobileNav}
            className="focus-ring rounded p-1.5 text-ink-dim hover:text-ink lg:hidden"
          >
            <Menu className="h-4 w-4" />
          </button>
        )}
        <Link href="/" className="focus-ring group flex items-center gap-2.5 rounded">
          <div className="relative flex h-7 w-7 items-center justify-center rounded border border-signal-cyan/30 bg-signal-cyan/10">
            <Radar className="h-3.5 w-3.5 text-signal-cyan" />
            <span className="absolute inset-0 animate-scan overflow-hidden rounded">
              <span className="absolute top-0 h-full w-1/3 bg-gradient-to-r from-transparent via-signal-cyan/15 to-transparent" />
            </span>
          </div>
          <div className="leading-tight">
            <p className="font-mono text-xs font-bold tracking-[0.22em] text-ink">
              SAGAR&nbsp;WATCH
            </p>
            <p className="hidden text-[8px] uppercase tracking-[0.16em] text-ink-faint sm:block">
              Oil Spill Intelligence System
            </p>
          </div>
        </Link>

        <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "focus-ring relative rounded px-2.5 py-1 font-mono text-[10px] tracking-[0.14em] transition-colors",
                  active
                    ? "text-signal-cyan"
                    : "text-ink-dim hover:bg-base-700/50 hover:text-ink"
                )}
              >
                {item.label}
                {active && (
                  <span className="absolute inset-x-2.5 -bottom-[11px] h-px bg-signal-cyan" />
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="hidden md:flex items-center gap-1.5 rounded border border-line/50 bg-base-800/50 px-2.5 py-1">
          <Search className="h-3 w-3 text-ink-faint" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search vessels, incidents, coordinates..."
            className="w-48 bg-transparent font-mono text-[10px] text-ink placeholder:text-ink-faint/50 outline-none"
            aria-label="Search"
          />
        </form>

        {/* NRT Status + Clock */}
        <div className="flex items-center gap-2 rounded border border-line/50 bg-base-800/50 px-2 py-1">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-signal-green" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-green" />
          </span>
          <span className="font-mono text-[10px] font-semibold tracking-widest text-signal-green">
            NRT
          </span>
          <div className="hidden sm:flex flex-col items-end leading-none">
            <span className="font-mono text-[10px] tabular-nums text-ink-dim">
              {time} <span className="text-ink-faint">IST</span>
            </span>
            <span className="font-mono text-[8px] tabular-nums text-ink-faint">
              {date}
            </span>
          </div>
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
      <nav className="glass-panel absolute left-0 top-0 flex h-full w-60 animate-fade-in flex-col gap-1 rounded-none border-y-0 border-l-0 p-3">
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
