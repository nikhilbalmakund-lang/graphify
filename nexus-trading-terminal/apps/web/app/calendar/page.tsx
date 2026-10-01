import type { Metadata } from "next";

import { CalendarView } from "./view";

export const metadata: Metadata = { title: "Economic Calendar" };

export default function Page() {
  return <CalendarView />;
}
