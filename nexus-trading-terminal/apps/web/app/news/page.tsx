import type { Metadata } from "next";

import { NewsView } from "./view";

export const metadata: Metadata = { title: "News" };

export default function Page() {
  return <NewsView />;
}
