import type { Metadata } from "next";

import { ScannerView } from "./view";

export const metadata: Metadata = { title: "Market Scanner" };

export default function Page() {
  return <ScannerView />;
}
