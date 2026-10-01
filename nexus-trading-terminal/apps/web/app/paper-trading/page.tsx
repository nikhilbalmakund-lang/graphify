import type { Metadata } from "next";

import { PaperTradingView } from "./view";

export const metadata: Metadata = { title: "Paper Trading" };

export default function Page() {
  return <PaperTradingView />;
}
