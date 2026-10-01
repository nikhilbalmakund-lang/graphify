"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

interface DialogContentProps extends Omit<React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>, "title"> {
  title: React.ReactNode;
  description?: React.ReactNode;
  side?: "center" | "left" | "bottom";
}

export const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, title, description, side = "center", children, ...props }, ref) => (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[60] bg-black/65 backdrop-blur-[1px]" />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          "fixed z-[70] flex flex-col border border-line-strong bg-panel shadow-2xl focus:outline-none",
          side === "center" && "left-1/2 top-[12vh] max-h-[80vh] w-[min(92vw,560px)] -translate-x-1/2 rounded-md",
          side === "left" && "inset-y-0 left-0 w-[min(86vw,320px)] border-y-0 border-l-0",
          side === "bottom" && "inset-x-0 bottom-0 max-h-[85vh] rounded-t-md",
          className,
        )}
        {...props}
      >
        <div className="flex items-start gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            <DialogPrimitive.Title className="text-sm font-semibold text-fg-strong">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-0.5 text-xs text-muted">{description}</DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="sr-only">{typeof title === "string" ? title : "Dialog"}</DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close className="rounded-sm p-1 text-muted hover:bg-elevated hover:text-fg" aria-label="Close">
            <X className="size-4" />
          </DialogPrimitive.Close>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  ),
);
DialogContent.displayName = "DialogContent";
