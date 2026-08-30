import type { ConfidenceLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface IncidentFiltersBarProps {
  search: string;
  onSearch: (v: string) => void;
  levels: ConfidenceLevel[];
  onToggleLevel: (l: ConfidenceLevel) => void;
  children?: React.ReactNode;
}

const LEVELS: { id: ConfidenceLevel; label: string; color: string }[] = [
  { id: "HIGH", label: "High", color: "#f87171" },
  { id: "MEDIUM", label: "Medium", color: "#fb923c" },
  { id: "LOW", label: "Low", color: "#facc15" },
];

export function FilterChips({
  levels,
  onToggleLevel,
}: Omit<IncidentFiltersBarProps, "search" | "onSearch" | "children">) {
  return (
    <div className="flex gap-1.5">
      {LEVELS.map((l) => {
        const on = levels.includes(l.id);
        return (
          <button
            key={l.id}
            aria-pressed={on}
            onClick={() => onToggleLevel(l.id)}
            className={cn(
              "focus-ring rounded border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors",
              on ? "text-base-950" : "border-line text-ink-dim hover:border-line-bright"
            )}
            style={on ? { borderColor: l.color, backgroundColor: l.color } : undefined}
          >
            {l.label}
          </button>
        );
      })}
    </div>
  );
}
