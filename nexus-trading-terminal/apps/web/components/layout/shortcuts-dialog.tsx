"use client";

import { Dialog, DialogContent } from "@/components/ui/dialog";
import { SHORTCUTS } from "@/hooks/use-shortcuts";

export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Keyboard shortcuts" description="Single-key shortcuts work anywhere except while typing in a field.">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="contents">
              <dt>
                <kbd className="inline-block min-w-7 rounded-xs border border-line-strong bg-elevated px-1.5 py-0.5 text-center font-mono text-xs text-fg">{s.key}</kbd>
              </dt>
              <dd className="self-center text-xs text-muted">{s.label}</dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
