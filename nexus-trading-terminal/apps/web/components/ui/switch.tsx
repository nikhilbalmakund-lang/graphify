"use client";

import { Switch as SwitchPrimitive } from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Switch = React.forwardRef<HTMLButtonElement, React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>>(
  ({ className, ...props }, ref) => (
    <SwitchPrimitive.Root
      ref={ref}
      className={cn(
        "peer inline-flex h-4.5 w-8 shrink-0 cursor-pointer items-center rounded-full border border-line-strong bg-elevated transition-colors data-[state=checked]:border-accent/60 data-[state=checked]:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block size-3 translate-x-0.5 rounded-full bg-muted transition-transform data-[state=checked]:translate-x-[15px] data-[state=checked]:bg-accent" />
    </SwitchPrimitive.Root>
  ),
);
Switch.displayName = "Switch";
