import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingRows } from "@/components/common/states";

import { ChartView } from "./view";

export const metadata: Metadata = { title: "Chart" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingRows rows={10} className="p-4" />}>
      <ChartView />
    </Suspense>
  );
}
