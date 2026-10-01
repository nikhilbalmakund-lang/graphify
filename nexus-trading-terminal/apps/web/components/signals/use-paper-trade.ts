"use client";

import type { Order, RiskDecision, Signal } from "@nexus/shared-types";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { errorMessage, post } from "@/lib/api";
import { fmtNum } from "@/lib/format";

/** Send a signal to the PAPER broker. The backend runs the deterministic risk engine first and may veto. */
export function usePaperTrade() {
  const { mutate } = useSWRConfig();
  const [busy, setBusy] = useState<string | null>(null);
  const execute = async (s: Pick<Signal, "id" | "symbol" | "direction">) => {
    setBusy(s.id);
    try {
      const res = await post<{ order: Order; risk: RiskDecision; simulated: boolean }>(`/api/signals/${s.id}/paper`);
      if (res.order.status === "REJECTED") {
        toast.error(`Paper order rejected: ${res.order.reject_reason ?? "risk engine veto"}`);
      } else {
        toast.success(`SIMULATED ${s.direction} ${s.symbol} · ${fmtNum(res.risk.lots, 2)} lots`, {
          description: `Risk ${fmtNum(res.risk.risk_pct * 100, 2)}% (${res.risk.sizing_method}). Paper trading only - no real order sent.`,
        });
      }
      void mutate((k) => typeof k === "string" && (k.startsWith("/api/paper-trading") || k.startsWith("/api/portfolio") || k.startsWith("/api/risk") || k.startsWith("/api/journal")));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  return { execute, busy };
}
