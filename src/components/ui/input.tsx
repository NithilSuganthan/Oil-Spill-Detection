import * as React from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "focus-ring h-8 w-full rounded-md border border-line bg-base-850 px-2.5 text-xs text-ink placeholder:text-ink-faint",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

interface SearchInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> {
  value: string;
  onValueChange: (v: string) => void;
}

function SearchInput({ value, onValueChange, className, ...props }: SearchInputProps) {
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
      <Input
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className="pl-7.5 pr-7 pl-[30px]"
        {...props}
      />
      {value && (
        <button
          aria-label="Clear search"
          onClick={() => onValueChange("")}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-ink-faint hover:text-ink"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

export { Input, SearchInput };
