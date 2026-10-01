"use client";

import type { BacktestDetail } from "@nexus/shared-types";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { BacktestResultView } from "@/components/backtest/result-view";
import { RiskNotice } from "@/components/common/disclaimer";
import { PageContainer } from "@/components/common/page-header";
import { DataBlock } from "@/components/common/states";
import { useApi } from "@/hooks/use-api";

export function BacktestDetailView({ id }: { id: string }) {
  const { data, error, isLoading, mutate } = useApi<BacktestDetail>(`/api/backtests/${id}`);
  return (
    <PageContainer>
      <Link href="/backtesting" className="inline-flex items-center gap-1 text-[0.7rem] text-muted hover:text-accent">
        <ArrowLeft className="size-3" /> Backtesting
      </Link>
      <DataBlock data={data} error={error} isLoading={isLoading} onRetry={() => mutate()} rows={10}>
        {(bt) => <BacktestResultView bt={bt} />}
      </DataBlock>
      <RiskNotice>Backtests are simulations on historical (or DEMO synthetic) data. They are not predictions, and past performance does not guarantee future results.</RiskNotice>
    </PageContainer>
  );
}
