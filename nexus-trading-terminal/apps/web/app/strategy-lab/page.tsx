import type { Metadata } from "next";

import { StrategyLabView } from "./view";

export const metadata: Metadata = { title: "Strategy Lab" };

export default function Page() {
  return <StrategyLabView />;
}
