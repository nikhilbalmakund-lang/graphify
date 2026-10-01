import type { Metadata } from "next";

import { AlertsView } from "./view";

export const metadata: Metadata = { title: "Alerts" };

export default function Page() {
  return <AlertsView />;
}
