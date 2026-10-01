import type { Metadata } from "next";

import { BacktestDetailView } from "./view";

export const metadata: Metadata = { title: "Backtest result" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BacktestDetailView id={id} />;
}
