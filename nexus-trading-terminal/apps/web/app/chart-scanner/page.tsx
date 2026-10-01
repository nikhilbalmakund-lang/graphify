import type { Metadata } from "next";

import { ChartScannerView } from "./view";

export const metadata: Metadata = { title: "AI Chart Scanner" };

export default function Page() {
  return <ChartScannerView />;
}
