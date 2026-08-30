import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-base-700/50", className)} />;
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[120px] w-full flex-col items-center justify-center gap-3">
      <div className="relative h-8 w-8">
        <div className="absolute inset-0 rounded-full border border-line-bright" />
        <div className="absolute inset-0 animate-spin rounded-full border border-transparent border-t-signal-cyan" />
      </div>
      <p className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">{label}</p>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      {icon && <div className="mb-1 text-ink-faint">{icon}</div>}
      <p className="font-mono text-xs uppercase tracking-widest text-ink-dim">{title}</p>
      {description && <p className="max-w-xs text-xs leading-relaxed text-ink-faint">{description}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <p className="font-mono text-xs uppercase tracking-widest text-signal-red">Error</p>
      <p className="max-w-xs text-xs text-ink-faint">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="focus-ring rounded-md border border-line px-3 py-1.5 text-xs text-ink-dim hover:border-line-bright hover:text-ink"
        >
          Retry
        </button>
      )}
    </div>
  );
}
