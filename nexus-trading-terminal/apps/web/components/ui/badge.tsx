import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-xs border px-1.5 py-[1px] text-[0.66rem] font-semibold uppercase tracking-wider leading-4 whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "border-line-strong text-muted bg-elevated/60",
        accent: "border-accent/40 text-accent bg-accent/10",
        purple: "border-accent-2/40 text-accent-2 bg-accent-2/10",
        up: "border-up/40 text-up bg-up/10",
        down: "border-down/40 text-down bg-down/10",
        warn: "border-warn/45 text-warn bg-warn/10",
        info: "border-info/40 text-info bg-info/10",
        solidUp: "border-transparent bg-up text-bg",
        solidDown: "border-transparent bg-down text-white",
        solidWarn: "border-transparent bg-warn text-bg",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
