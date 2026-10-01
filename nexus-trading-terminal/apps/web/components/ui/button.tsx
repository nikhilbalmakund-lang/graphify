import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-3.5 [&_svg]:shrink-0 cursor-pointer select-none",
  {
    variants: {
      variant: {
        primary: "bg-accent text-bg hover:bg-accent/85",
        secondary: "bg-elevated text-fg border border-line hover:border-line-strong hover:bg-line/60",
        ghost: "text-muted hover:text-fg hover:bg-elevated",
        outline: "border border-line text-fg hover:border-accent/60 hover:text-fg-strong",
        danger: "bg-down/90 text-white hover:bg-down",
        success: "bg-up/90 text-bg hover:bg-up",
        link: "text-accent hover:underline underline-offset-4 px-0",
      },
      size: {
        xs: "h-6 px-2 text-[0.72rem]",
        sm: "h-7 px-2.5 text-xs",
        md: "h-8 px-3 text-sm",
        lg: "h-10 px-4 text-sm",
        icon: "h-7 w-7 p-0",
      },
    },
    defaultVariants: { variant: "secondary", size: "sm" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, ...props }, ref) => {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
});
Button.displayName = "Button";

export { buttonVariants };
