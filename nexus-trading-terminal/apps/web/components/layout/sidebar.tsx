"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { isActive, NAV_GROUPS } from "./nav";

export function NavList({ onNavigate, collapsed }: { onNavigate?: () => void; collapsed?: boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-3 py-3">
      {NAV_GROUPS.map((g) => (
        <div key={g.label} className="flex flex-col gap-px">
          {!collapsed ? <p className="px-3 pb-1 text-[0.6rem] font-semibold uppercase tracking-[0.12em] text-faint">{g.label}</p> : null}
          {g.items.map((item) => {
            const active = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "group mx-1.5 flex h-7 items-center gap-2.5 rounded-sm px-2 text-[0.8rem] text-muted transition-colors hover:bg-elevated hover:text-fg",
                  active && "bg-elevated text-fg-strong shadow-[inset_2px_0_0_var(--color-accent)]",
                )}
              >
                <Icon className={cn("size-3.5 shrink-0", active ? "text-accent" : "text-faint group-hover:text-muted")} />
                {!collapsed ? <span className="flex-1 truncate">{item.label}</span> : null}
                {!collapsed && item.shortcut ? (
                  <kbd className="hidden rounded-xs border border-line px-1 font-mono text-[0.6rem] text-faint group-hover:inline-block">{item.shortcut}</kbd>
                ) : null}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-52 shrink-0 overflow-y-auto border-r border-line bg-panel/50 lg:block" aria-label="Sidebar">
      <NavList />
    </aside>
  );
}
