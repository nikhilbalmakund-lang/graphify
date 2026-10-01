"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

// Route-level error boundary. Shows a generic message - never a stack trace.
export default function RouteError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-4 py-24 text-center">
      <AlertTriangle className="size-6 text-down" />
      <p className="text-sm font-semibold text-fg">Something went wrong rendering this page.</p>
      <p className="max-w-md text-xs text-muted">The error was contained to this view. Your data is unaffected. Try again, or check System Status if the backend is unreachable.</p>
      <Button variant="outline" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
