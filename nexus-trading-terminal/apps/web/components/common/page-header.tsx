import * as React from "react";

import { cn } from "@/lib/utils";

export function PageHeader({ title, description, actions, badges, className }: { title: string; description?: React.ReactNode; actions?: React.ReactNode; badges?: React.ReactNode; className?: string }) {
  return (
    <header className={cn("flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold tracking-tight text-fg-strong">{title}</h1>
          {badges}
        </div>
        {description ? <p className="mt-0.5 max-w-3xl text-xs text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function PageContainer({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto flex w-full max-w-[1680px] flex-col gap-3 p-3 sm:p-4", className)}>{children}</div>;
}
