"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button, type ButtonProps } from "@/components/ui/button";
import { downloadFrom } from "@/lib/download";

export function ExportButton({ path, filename, label = "Export CSV", ...props }: { path: string; filename: string; label?: string } & ButtonProps) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      {...props}
      disabled={busy || props.disabled}
      onClick={async () => {
        setBusy(true);
        try {
          await downloadFrom(path, filename);
          toast.success(`Exported ${filename}`);
        } catch (e) {
          toast.error(e instanceof Error ? e.message : "Export failed");
        } finally {
          setBusy(false);
        }
      }}
    >
      <Download /> {label}
    </Button>
  );
}
