"use client";

import type { RiskStatus, SettingsPayload, SystemStatus } from "@nexus/shared-types";

import { useApi } from "@/hooks/use-api";

/** Shared, de-duplicated system queries used by the shell (SWR caches by key). */
export function useSystemStatus() {
  return useApi<SystemStatus>("/api/system/status", 15_000);
}

export function useSettings() {
  return useApi<SettingsPayload>("/api/settings", 0);
}

export function useRiskStatus() {
  return useApi<RiskStatus>("/api/risk/status", 10_000);
}

export function componentStatus(status: SystemStatus | undefined, name: string): string {
  return status?.components.find((c) => c.name.toLowerCase() === name.toLowerCase())?.status ?? "UNKNOWN";
}
