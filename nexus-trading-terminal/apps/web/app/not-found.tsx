import Link from "next/link";

import { EmptyState } from "@/components/common/states";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <EmptyState
      className="py-24"
      title="Page not found"
      description="This page does not exist. Use the command palette (/) to jump anywhere."
      action={
        <Button asChild variant="outline">
          <Link href="/">Back to dashboard</Link>
        </Button>
      }
    />
  );
}
