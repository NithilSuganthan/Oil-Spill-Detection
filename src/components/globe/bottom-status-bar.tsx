"use client";

import * as React from "react";
import { Ship, Satellite, Droplets, Waves, Wind } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StatusCard {
  id: string;
  label: string;
  icon: React.ElementType;
  status: string;
  statusColor: string;
  value?: string;
  detail?: string;
  sparkline?: number[];
  color: string;
}

interface BottomStatusBarProps {
  cards: StatusCard[];
  className?: string;
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const h = 18;
  const w = 54;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} className="opacity-80 shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BottomStatusBar({ cards, className }: BottomStatusBarProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 overflow-x-auto",
        className
      )}
    >
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.id}
            className="rounded-lg border border-line/60 bg-base-950/90 backdrop-blur-xl px-3 py-2 flex flex-col justify-between shadow-lg"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 min-w-0">
                <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: card.color }} />
                <span className="font-mono text-[9px] font-extrabold uppercase tracking-wider text-ink-dim truncate">
                  {card.label}
                </span>
              </div>
              {card.sparkline && (
                <MiniSparkline data={card.sparkline} color={card.color} />
              )}
            </div>

            <div className="flex items-baseline justify-between mt-1.5">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className={cn("h-1.5 w-1.5 rounded-full shrink-0 animate-pulse", card.statusColor.replace("text-", "bg-"))} />
                <span className={cn("font-mono text-[9px] font-bold uppercase truncate", card.statusColor)}>
                  {card.status}
                </span>
              </div>
              {card.value && (
                <span className="font-mono text-sm font-extrabold text-ink tabular-nums ml-1">
                  {card.value}
                </span>
              )}
            </div>

            {card.detail && (
              <div className="font-mono text-[8px] text-ink-faint mt-0.5 truncate">
                {card.detail}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
