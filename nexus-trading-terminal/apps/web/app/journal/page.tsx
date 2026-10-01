import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingRows } from "@/components/common/states";

import { JournalView } from "./view";

export const metadata: Metadata = { title: "Trade Journal" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingRows rows={10} className="p-4" />}>
      <JournalView />
    </Suspense>
  );
}
