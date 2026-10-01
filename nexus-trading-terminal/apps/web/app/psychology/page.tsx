import type { Metadata } from "next";

import { PsychologyView } from "./view";

export const metadata: Metadata = { title: "Market Psychology" };

export default function Page() {
  return <PsychologyView />;
}
