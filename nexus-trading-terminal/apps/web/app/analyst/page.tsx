import type { Metadata } from "next";

import { AnalystView } from "./view";

export const metadata: Metadata = { title: "AI Analyst" };

export default function Page() {
  return <AnalystView />;
}
