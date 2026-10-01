"use client";

import useSWR, { type SWRConfiguration } from "swr";

import { fetcher } from "@/lib/api";

/** SWR wrapper for same-origin API GETs. Pass null to skip. */
export function useApi<T>(path: string | null, refreshMs?: number, config?: SWRConfiguration<T>) {
  return useSWR<T>(path, fetcher, {
    refreshInterval: refreshMs ?? 0,
    revalidateOnFocus: false,
    keepPreviousData: true,
    shouldRetryOnError: true,
    errorRetryCount: 3,
    ...config,
  });
}
