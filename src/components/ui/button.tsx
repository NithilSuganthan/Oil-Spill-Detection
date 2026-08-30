import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "focus-ring inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-xs font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "border border-signal-cyan/30 bg-signal-cyan/10 text-signal-cyan hover:bg-signal-cyan/20",
        solid: "bg-signal-cyan text-base-950 hover:bg-signal-cyan/90 font-semibold",
        outline: "border border-line bg-transparent text-ink-dim hover:border-line-bright hover:text-ink",
        ghost: "text-ink-dim hover:bg-base-700/60 hover:text-ink",
        danger:
          "border border-signal-red/40 bg-signal-red/10 text-signal-red hover:bg-signal-red/20",
      },
      size: {
        default: "h-8 px-3",
        sm: "h-6.5 px-2 py-1 h-[26px]",
        lg: "h-9 px-4 text-sm",
        icon: "h-8 w-8",
        iconSm: "h-7 w-7",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
