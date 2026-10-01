import * as React from "react";

import { cn } from "@/lib/utils";

export function Panel({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return <section className={cn("panel flex min-w-0 flex-col", className)} {...props} />;
}

interface PanelHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
}

export function PanelHeader({ title, subtitle, icon, actions, className, ...props }: PanelHeaderProps) {
  return (
    <div className={cn("flex min-h-10 items-center gap-2 border-b border-line px-3 py-2", className)} {...props}>
      {icon ? <span className="text-accent [&_svg]:size-3.5">{icon}</span> : null}
      <div className="min-w-0 flex-1">
        <h2 className="truncate text-[0.72rem] font-semibold uppercase tracking-[0.09em] text-fg">{title}</h2>
        {subtitle ? <p className="truncate text-[0.7rem] text-muted">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-1.5">{actions}</div> : null}
    </div>
  );
}

export function PanelBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("min-w-0 flex-1 p-3", className)} {...props} />;
}
