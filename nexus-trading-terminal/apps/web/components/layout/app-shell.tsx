"use client";

import { useCallback, useState } from "react";

import { useGlobalShortcuts } from "@/hooks/use-shortcuts";
import { useLocalStorage } from "@/hooks/use-local-storage";

import { CommandPalette } from "./command-palette";
import { MobileDrawer, MobileNav } from "./mobile-nav";
import { RightPanel } from "./right-panel";
import { ShortcutsDialog } from "./shortcuts-dialog";
import { Sidebar } from "./sidebar";
import { Ticker } from "./ticker";
import { DemoBanner, TopBar } from "./top-bar";
import { useSettings } from "./use-system";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [rightPref, setRightPref] = useLocalStorage<boolean | null>("nexus.rightPanel", null);
  const { data: settings } = useSettings();
  const settingDefault = (settings?.settings?.appearance as { show_right_panel?: boolean } | undefined)?.show_right_panel ?? true;
  const rightOpen = rightPref ?? settingDefault;

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const openHelp = useCallback(() => setHelpOpen(true), []);
  const toggleRight = useCallback(() => setRightPref(!rightOpen), [rightOpen, setRightPref]);
  useGlobalShortcuts(openPalette, openHelp);

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <a href="#main" className="sr-only-focusable fixed left-2 top-2 z-[90] rounded-sm bg-accent px-3 py-1.5 text-xs font-semibold text-bg">
        Skip to content
      </a>
      <DemoBanner />
      <TopBar onOpenPalette={openPalette} onOpenMenu={() => setMenuOpen(true)} onToggleRight={toggleRight} rightOpen={rightOpen} />
      <Ticker />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto pb-16 focus:outline-none lg:pb-0">
          {children}
        </main>
        {rightOpen ? <RightPanel /> : null}
      </div>
      <MobileNav onMore={() => setMenuOpen(true)} />
      <MobileDrawer open={menuOpen} onOpenChange={setMenuOpen} />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} onShowShortcuts={openHelp} onToggleRight={toggleRight} />
      <ShortcutsDialog open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  );
}
