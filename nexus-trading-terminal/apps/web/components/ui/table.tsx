import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full border-collapse text-[0.8rem]", className)} {...props} />
    </div>
  );
}

export function THead({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("sticky top-0 z-[1] bg-panel", className)} {...props} />;
}

export function TR({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("border-b border-line/70 transition-colors hover:bg-elevated/40", className)} {...props} />;
}

interface THProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  sortKey?: string;
  sort?: { key: string; dir: "asc" | "desc" };
  onSort?: (key: string) => void;
  align?: "left" | "right" | "center";
}

export function TH({ className, sortKey, sort, onSort, align = "left", children, ...props }: THProps) {
  const active = sortKey && sort?.key === sortKey;
  const Icon = active ? (sort?.dir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (sort?.dir === "asc" ? "ascending" : "descending") : undefined}
      className={cn(
        "whitespace-nowrap border-b border-line px-2.5 py-2 text-[0.66rem] font-semibold uppercase tracking-wider text-muted",
        align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left",
        className,
      )}
      {...props}
    >
      {sortKey && onSort ? (
        <button type="button" onClick={() => onSort(sortKey)} className={cn("inline-flex items-center gap-1 hover:text-fg", active && "text-fg")}>
          {children}
          <Icon className="size-3 opacity-70" />
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function TD({ className, align = "left", ...props }: React.TdHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  return (
    <td
      className={cn("whitespace-nowrap px-2.5 py-1.5 align-middle", align === "right" ? "text-right" : align === "center" ? "text-center" : "", className)}
      {...props}
    />
  );
}

/** Generic client-side sort helper. */
export function useSort<T>(rows: T[], initial: { key: string; dir: "asc" | "desc" }) {
  const [sort, setSort] = React.useState(initial);
  const onSort = (key: string) => setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));
  const sorted = React.useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = (a as Record<string, unknown>)[sort.key];
      const bv = (b as Record<string, unknown>)[sort.key];
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      const r = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? r : -r;
    });
    return copy;
  }, [rows, sort]);
  return { sorted, sort, onSort };
}
