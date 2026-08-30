import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider",
  {
    variants: {
      tone: {
        high: "border-signal-red/40 bg-signal-red/10 text-signal-red",
        medium: "border-signal-orange/40 bg-signal-orange/10 text-signal-orange",
        low: "border-signal-amber/40 bg-signal-amber/10 text-signal-amber",
        neutral: "border-line bg-base-700/50 text-ink-dim",
        cyan: "border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan",
        green: "border-signal-green/40 bg-signal-green/10 text-signal-green",
      },
    },
    defaultVariants: { tone: "neutral" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export const levelTone = {
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
} as const;
