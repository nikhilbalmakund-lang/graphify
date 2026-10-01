"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { isTypingTarget } from "@/lib/utils";

export const SHORTCUTS: { key: string; label: string; href?: string }[] = [
  { key: "/", label: "Search / command palette" },
  { key: "Ctrl+K", label: "Command palette" },
  { key: "G", label: "Go to dashboard", href: "/" },
  { key: "M", label: "Markets", href: "/markets" },
  { key: "S", label: "AI signals", href: "/signals" },
  { key: "C", label: "Chart", href: "/chart" },
  { key: "A", label: "AI analyst", href: "/analyst" },
  { key: "B", label: "Backtesting", href: "/backtesting" },
  { key: "P", label: "Paper trading", href: "/paper-trading" },
  { key: "?", label: "Show keyboard shortcuts" },
];

const NAV: Record<string, string> = { g: "/", m: "/markets", s: "/signals", c: "/chart", a: "/analyst", b: "/backtesting", p: "/paper-trading" };

export function useGlobalShortcuts(openPalette: () => void, openHelp: () => void) {
  const router = useRouter();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      if (document.querySelector("[role='dialog']")) return;
      if (e.key === "/") {
        e.preventDefault();
        openPalette();
      } else if (e.key === "?") {
        e.preventDefault();
        openHelp();
      } else {
        const href = NAV[e.key.toLowerCase()];
        if (href) {
          e.preventDefault();
          router.push(href);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, openPalette, openHelp]);
}
