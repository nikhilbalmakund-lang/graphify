import type { Metadata } from "next";

import { StatusView } from "./view";

export const metadata: Metadata = { title: "System Status" };

export default function Page() {
  return <StatusView />;
}
