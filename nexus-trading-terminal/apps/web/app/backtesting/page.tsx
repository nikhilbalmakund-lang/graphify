import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingRows } from "@/components/common/states";

import { BacktestingView } from "./view";

export const metadata: Metadata = { title: "Backtesting" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingRows rows={10} className="p-4" />}>
      <BacktestingView />
    </Suspense>
  );
}
