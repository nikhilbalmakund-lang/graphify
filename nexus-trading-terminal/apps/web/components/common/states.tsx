import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function EmptyState({ title, description, icon, action, className }: { title: string; description?: React.ReactNode; icon?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-4 py-10 text-center", className)}>
      <div className="text-faint [&_svg]:size-6">{icon ?? <Inbox />}</div>
      <p className="text-sm font-medium text-fg">{title}</p>
      {description ? <p className="max-w-md text-xs text-muted">{description}</p> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry, className, compact }: { error: unknown; onRetry?: () => void; className?: string; compact?: boolean }) {
  return (
    <div role="alert" className={cn("flex items-center gap-3 rounded-sm border border-down/30 bg-down/5 px-3", compact ? "py-2" : "py-4", className)}>
      <AlertTriangle className="size-4 shrink-0 text-down" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-down">Could not load data</p>
        <p className="truncate text-xs text-muted">{errorMessage(error)}</p>
      </div>
      {onRetry ? (
        <Button size="xs" variant="ghost" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function LoadingRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-7 w-full" />
      ))}
    </div>
  );
}

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-xs text-muted", className)} role="status">
      <Loader2 className="size-3.5 animate-spin" />
      {label ?? <span className="sr-only">Loading</span>}
    </span>
  );
}

/** Standard data-block wrapper: loading skeleton, error with retry, empty state, or children. */
export function DataBlock<T>({
  data,
  error,
  isLoading,
  onRetry,
  empty,
  isEmpty,
  rows = 4,
  children,
}: {
  data: T | undefined;
  error: unknown;
  isLoading: boolean;
  onRetry?: () => void;
  empty?: React.ReactNode;
  isEmpty?: (d: T) => boolean;
  rows?: number;
  children: (d: T) => React.ReactNode;
}) {
  if (error && data === undefined) return <ErrorState error={error} onRetry={onRetry} />;
  if (data === undefined) return isLoading ? <LoadingRows rows={rows} /> : null;
  if (isEmpty?.(data)) return <>{empty ?? <EmptyState title="Nothing here yet" />}</>;
  return <>{children(data)}</>;
}
