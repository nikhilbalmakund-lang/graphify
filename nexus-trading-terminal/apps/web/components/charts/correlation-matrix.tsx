import { Tip } from "@/components/ui/tooltip";

function cellColor(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "transparent";
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(38,194,129,${0.12 + a * 0.6})` : `rgba(240,82,92,${0.12 + a * 0.6})`;
}

/** Pearson correlation matrix of daily returns, rendered as a heat grid. */
export function CorrelationMatrix({ symbols, matrix }: { symbols: string[]; matrix: (number | null)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-0.5 text-[0.66rem]" aria-label="Correlation matrix">
        <thead>
          <tr>
            <th />
            {symbols.map((s) => (
              <th key={s} scope="col" className="px-1 pb-1 font-semibold text-muted [writing-mode:vertical-rl] rotate-180 sm:[writing-mode:horizontal-tb] sm:rotate-0">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((row, i) => (
            <tr key={row}>
              <th scope="row" className="pr-1.5 text-right font-semibold text-muted">
                {row}
              </th>
              {symbols.map((col, j) => {
                const v = matrix[i]?.[j] ?? null;
                return (
                  <td key={col} className="p-0">
                    <Tip content={`${row} / ${col}: ${v === null ? "n/a" : v.toFixed(2)}`}>
                      <div className="num flex h-7 min-w-10 items-center justify-center rounded-xs text-fg-strong" style={{ background: cellColor(v) }}>
                        {v === null ? "—" : i === j ? "1" : v.toFixed(2)}
                      </div>
                    </Tip>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
