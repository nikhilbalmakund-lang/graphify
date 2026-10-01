import type { Metadata } from "next";

import { MarketsView } from "./view";

export const metadata: Metadata = { title: "Markets" };

export default function Page() {
  return <MarketsView />;
}
