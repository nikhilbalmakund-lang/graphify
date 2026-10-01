import type { Metadata } from "next";

import { SignalsView } from "./view";

export const metadata: Metadata = { title: "AI Signals" };

export default function Page() {
  return <SignalsView />;
}
