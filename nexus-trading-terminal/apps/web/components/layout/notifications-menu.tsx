"use client";

import type { NotificationItem } from "@nexus/shared-types";
import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";
import { Popover } from "radix-ui";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { post } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

export function NotificationsMenu() {
  const { data, mutate } = useApi<NotificationItem[]>("/api/notifications?limit=30", 30_000);
  const now = useNow();
  const unread = data?.filter((n) => !n.read).length ?? 0;
  const markAll = async () => {
    await post("/api/notifications/read", {});
    void mutate();
  };
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`} className="relative">
          <Bell />
          {unread ? (
            <span className="num absolute -right-0.5 -top-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-accent px-0.5 text-[0.55rem] font-bold text-bg">
              {unread > 99 ? "99+" : unread}
            </span>
          ) : null}
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={6} className="z-[75] w-[min(92vw,380px)] rounded-md border border-line-strong bg-panel shadow-2xl">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <p className="text-xs font-semibold text-fg-strong">Notifications</p>
            <Button size="xs" variant="ghost" onClick={markAll} disabled={!unread}>
              <CheckCheck /> Mark all read
            </Button>
          </div>
          <ul className="max-h-[60vh] overflow-y-auto">
            {!data?.length ? <li className="px-3 py-8 text-center text-xs text-muted">No notifications yet.</li> : null}
            {data?.map((n) => {
              const inner = (
                <div className={cn("flex gap-2 px-3 py-2", !n.read && "bg-accent/[0.04]")}>
                  <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", n.read ? "bg-transparent" : n.severity === "ERROR" ? "bg-down" : n.severity === "WARNING" ? "bg-warn" : "bg-accent")} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <p className="truncate text-xs font-medium text-fg">{n.title}</p>
                      {n.is_demo ? <Badge tone="warn" className="px-1 text-[0.55rem]">Demo</Badge> : null}
                    </div>
                    <p className="line-clamp-2 text-[0.7rem] text-muted">{n.body}</p>
                    <p className="mt-0.5 text-[0.62rem] text-faint">{now ? timeAgo(n.ts, now) : ""}</p>
                  </div>
                </div>
              );
              return (
                <li key={n.id} className="border-b border-line/60 last:border-0">
                  {n.signal_id ? (
                    <Popover.Close asChild>
                      <Link href={`/signals/${n.signal_id}`} className="block hover:bg-elevated/60">
                        {inner}
                      </Link>
                    </Popover.Close>
                  ) : (
                    inner
                  )}
                </li>
              );
            })}
          </ul>
          <div className="border-t border-line px-3 py-1.5 text-right">
            <Popover.Close asChild>
              <Link href="/alerts" className="text-[0.7rem] text-accent hover:underline">
                Manage alerts →
              </Link>
            </Popover.Close>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
