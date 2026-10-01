"use client";

import { Activity, Bot, CandlestickChart, LayoutDashboard, MoreHorizontal, Zap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Dialog, DialogContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

import { isActive } from "./nav";
import { NavList } from "./sidebar";

const TABS = [
  { href: "/", label: "Home", icon: LayoutDashboard },
  { href: "/markets", label: "Markets", icon: Activity },
  { href: "/signals", label: "Signals", icon: Zap },
  { href: "/chart", label: "Chart", icon: CandlestickChart },
  { href: "/analyst", label: "AI", icon: Bot },
];

export function MobileNav({ onMore }: { onMore: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 grid h-14 grid-cols-6 border-t border-line bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      {TABS.map((t) => {
        const active = isActive(pathname, t.href);
        const Icon = t.icon;
        return (
          <Link key={t.href} href={t.href} aria-current={active ? "page" : undefined} className={cn("flex flex-col items-center justify-center gap-0.5 text-[0.62rem]", active ? "text-accent" : "text-muted")}>
            <Icon className="size-4.5" />
            {t.label}
          </Link>
        );
      })}
      <button type="button" onClick={onMore} className="flex flex-col items-center justify-center gap-0.5 text-[0.62rem] text-muted" aria-label="More pages">
        <MoreHorizontal className="size-4.5" />
        More
      </button>
    </nav>
  );
}

export function MobileDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent side="left" title="Navigation" className="p-0" aria-describedby={undefined}>
        <div className="-m-4">
          <NavList onNavigate={() => onOpenChange(false)} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
