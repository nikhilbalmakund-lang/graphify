"use client";

import { useNow } from "@/hooks/use-now";

export function UtcClock({ className }: { className?: string }) {
  const now = useNow();
  const text = now ? new Date(now).toISOString().slice(11, 19) : "--:--:--";
  return (
    <time className={className} dateTime={now ? new Date(now).toISOString() : undefined} aria-label="UTC time">
      <span className="num text-fg">{text}</span> <span className="text-faint">UTC</span>
    </time>
  );
}
