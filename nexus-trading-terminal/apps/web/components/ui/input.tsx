import * as React from "react";

import { cn } from "@/lib/utils";

const base =
  "w-full rounded-sm border border-line bg-panel-2 px-2 text-sm text-fg placeholder:text-faint transition-colors hover:border-line-strong focus:border-accent/70 focus:outline-none disabled:opacity-50";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(base, "h-8", className)} {...props} />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(base, "min-h-20 py-1.5", className)} {...props} />
));
Textarea.displayName = "Textarea";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...props }, ref) => (
  <select ref={ref} className={cn(base, "h-8 cursor-pointer pr-6", className)} {...props}>
    {children}
  </select>
));
Select.displayName = "Select";

interface FieldProps {
  label: React.ReactNode;
  htmlFor?: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function Field({ label, htmlFor, hint, error, className, children }: FieldProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <label htmlFor={htmlFor} className="label">
        {label}
      </label>
      {children}
      {error ? <p className="text-[0.7rem] text-down">{error}</p> : hint ? <p className="text-[0.7rem] text-faint">{hint}</p> : null}
    </div>
  );
}
