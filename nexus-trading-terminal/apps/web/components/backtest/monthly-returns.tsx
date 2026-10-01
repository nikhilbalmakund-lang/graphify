import { Tip } from "@/components/ui/tooltip";
import { fmtPct } from "@/lib/format";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Year × month grid of returns (%). Losing months are shown as prominently as winning ones. */
export function MonthlyReturns({ data }: { data: Record<string, number> }) {
  const years = [...new Set(Object.keys(data).map((k) => k.slice(0, 4)))].sort();
  if (!years.length) return <p className="text-xs text-faint">No monthly data.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0.5 text-[0.68rem]">
        <thead>
          <tr>
            <th className="w-12" />
            {MONTHS.map((m) => (
              <th key={m} scope="col" className="font-semibold text-muted">
                {m}
              </th>
            ))}
            <th scope="col" className="font-semibold text-muted">
              Year
            </th>
          </tr>
        </thead>
        <tbody>
          {years.map((y) => {
            const vals = MONTHS.map((_, i) => data[`${y}-${String(i + 1).padStart(2, "0")}`]);
            const total = vals.reduce<number>((acc, v) => (v === undefined ? acc : (1 + acc / 100) * (1 + v / 100) * 100 - 100), 0);
            return (
              <tr key={y}>
                <th scope="row" className="num pr-1 text-right font-semibold text-muted">
                  {y}
                </th>
                {vals.map((v, i) => (
                  <td key={i} className="p-0">
                    {v === undefined ? (
                      <div className="h-7 rounded-xs bg-elevated/30" />
                    ) : (
                      <Tip content={`${MONTHS[i]} ${y}: ${fmtPct(v, 2)}`}>
                        <div
                          className="num flex h-7 items-center justify-center rounded-xs text-fg-strong"
                          style={{ background: v >= 0 ? `rgba(38,194,129,${0.15 + Math.min(1, Math.abs(v) / 5) * 0.6})` : `rgba(240,82,92,${0.15 + Math.min(1, Math.abs(v) / 5) * 0.6})` }}
                        >
                          {v.toFixed(1)}
                        </div>
                      </Tip>
                    )}
                  </td>
                ))}
                <td className={`num px-1 text-center font-semibold ${total >= 0 ? "text-up" : "text-down"}`}>{fmtPct(total, 1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
