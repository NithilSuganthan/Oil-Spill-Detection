import Link from "next/link";
import { SearchX } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <SearchX className="h-8 w-8 text-ink-faint" />
      <p className="font-mono text-sm uppercase tracking-[0.25em] text-ink-dim">
        404 · Target Not Found
      </p>
      <p className="max-w-sm text-xs text-ink-faint">
        The requested page or incident ID does not exist in this prototype&apos;s dataset.
      </p>
      <Link
        href="/"
        className="focus-ring rounded-md border border-signal-cyan/30 bg-signal-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-widest text-signal-cyan hover:bg-signal-cyan/20"
      >
        Return to Monitor
      </Link>
    </div>
  );
}
