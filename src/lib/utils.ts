import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const istFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  hour12: false,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const istDateFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
});

export function formatISTTime(iso: string): string {
  return `${istFormatter.format(new Date(iso))} IST`;
}

export function formatISTTimeShort(iso: string): string {
  const parts = istFormatter.formatToParts(new Date(iso));
  const h = parts.find((p) => p.type === "hour")?.value ?? "--";
  const m = parts.find((p) => p.type === "minute")?.value ?? "--";
  return `${h}:${m}`;
}

export function formatISTDate(iso: string): string {
  return istDateFormatter.format(new Date(iso));
}

export function formatPercent(confidence: number): string {
  return `${(confidence * 100).toFixed(1)}%`;
}

export function formatArea(km2: number): string {
  return km2 >= 10 ? km2.toFixed(1) : km2.toFixed(1);
}
