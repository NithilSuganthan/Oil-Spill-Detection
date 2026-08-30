"use client";

import * as React from "react";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps {
  options: SelectOption[];
  value: string;
  onValueChange: (v: string) => void;
  className?: string;
  ariaLabel?: string;
}

export function Select({ options, value, onValueChange, className, ariaLabel }: SelectProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const current = options.find((o) => o.value === value);

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="focus-ring flex h-8 w-full items-center justify-between gap-2 rounded-md border border-line bg-base-850 px-2.5 text-xs text-ink hover:border-line-bright"
      >
        <span className="truncate">{current?.label ?? "Select…"}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 z-50 mt-1 max-h-64 overflow-auto rounded-md border border-line-bright bg-base-850 py-1 shadow-panel animate-fade-in"
        >
          {options.map((opt) => (
            <li key={opt.value}>
              <button
                type="button"
                role="option"
                aria-selected={opt.value === value}
                disabled={opt.disabled}
                onClick={() => {
                  onValueChange(opt.value);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between px-2.5 py-1.5 text-left text-xs",
                  opt.value === value ? "text-signal-cyan" : "text-ink-dim",
                  !opt.disabled && "hover:bg-base-700/70 hover:text-ink",
                  opt.disabled && "cursor-not-allowed opacity-40"
                )}
              >
                <span className="truncate">{opt.label}</span>
                {opt.value === value && <Check className="ml-2 h-3 w-3 shrink-0" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
