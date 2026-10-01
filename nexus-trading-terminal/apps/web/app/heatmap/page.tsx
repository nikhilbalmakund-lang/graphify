import type { Metadata } from "next";

import { HeatmapView } from "./view";

export const metadata: Metadata = { title: "Heatmap" };

export default function Page() {
  return <HeatmapView />;
}
