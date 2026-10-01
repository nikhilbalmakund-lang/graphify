"use client";

import type { Briefing } from "@nexus/shared-types";
import { RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BulletList, ExplainedSections } from "@/components/common/explained";
import { EmptyState, ErrorState, LoadingRows } from "@/components/common/states";
import { ModeBadge } from "@/components/market/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Select } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { useNow } from "@/hooks/use-now";
import { errorMessage, post, qs } from "@/lib/api";
import { timeAgo, titleCase } from "@/lib/format";

const SESSIONS = ["", "ASIA_OPEN", "PRE_MARKET", "LONDON_OPEN", "NEW_YORK_OPEN", "INTRADAY", "POST_MARKET"];

export function ProviderLabel({ isAi, provider, model }: { isAi: boolean; provider: string; model: string }) {
  return isAi ? (
    <Badge tone="purple">
      AI · {provider} {model}
    </Badge>
  ) : (
    <Badge tone="neutral" title="Rule-based fallback: no AI model was called">
      Rule-based (non-AI)
    </Badge>
  );
}

export function BriefingPanel({ detailed }: { detailed?: boolean }) {
  const { data, error, isLoading, mutate } = useApi<{ briefing: Briefing | null }>("/api/ai/briefing", 120_000);
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState("");
  const now = useNow();
  const b = data?.briefing;
  const generate = async () => {
    setBusy(true);
    try {
      const res = await post<{ briefing: Briefing }>(`/api/ai/briefing${qs({ session: session || undefined, force: true })}`);
      await mutate(res, { revalidate: false });
      toast.success("Briefing generated from current structured data");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel>
      <PanelHeader
        title="AI market briefing"
        subtitle={b ? `${titleCase(b.session)} · ${now ? timeAgo(b.created_at, now) : ""}` : "Generated only from actual structured data"}
        icon={<Sparkles />}
        actions={
          <>
            {detailed ? (
              <Select aria-label="Briefing session" value={session} onChange={(e) => setSession(e.target.value)} className="h-7 w-36 text-xs">
                {SESSIONS.map((s) => (
                  <option key={s} value={s}>
                    {s ? titleCase(s) : "Current session"}
                  </option>
                ))}
              </Select>
            ) : null}
            <Button size="xs" variant="outline" onClick={generate} disabled={busy}>
              <RefreshCw className={busy ? "animate-spin" : ""} /> {busy ? "Generating" : "Refresh"}
            </Button>
          </>
        }
      />
      <PanelBody>
        {error && !data ? <ErrorState error={error} onRetry={() => mutate()} /> : null}
        {isLoading && !data ? <LoadingRows rows={5} /> : null}
        {data && !b ? (
          <EmptyState title="No briefing yet" description="Briefings are generated on schedule per session, or on demand. They summarise real structured inputs only." action={<Button size="sm" variant="primary" onClick={generate} disabled={busy}>Generate briefing</Button>} />
        ) : null}
        {b ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <ProviderLabel isAi={b.is_ai} provider={b.provider} model={b.model} />
              {b.is_demo_data ? <ModeBadge mode="DEMO" /> : null}
              {b.prompt_version ? <span className="text-[0.62rem] text-faint">prompt v{b.prompt_version}</span> : null}
            </div>
            <p className="text-sm font-medium leading-snug text-fg-strong">{b.content.theme}</p>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <p className="label mb-1">Strongest trends</p>
                <BulletList items={b.content.strongest_trends} />
              </div>
              <div>
                <p className="label mb-1">Major risks</p>
                <BulletList items={b.content.major_risks.slice(0, detailed ? 20 : 5)} tone="warn" />
              </div>
              <div>
                <p className="label mb-1">Volatility</p>
                <p className="text-xs text-fg">{b.content.volatility}</p>
              </div>
              <div>
                <p className="label mb-1">Upcoming events</p>
                <BulletList items={b.content.upcoming_events} empty="No high-impact events scheduled." />
              </div>
              <div className="md:col-span-2">
                <p className="label mb-1">Assets worth monitoring</p>
                <div className="flex flex-wrap gap-1.5">
                  {b.content.assets_to_monitor.length ? b.content.assets_to_monitor.map((a) => <Badge key={a} tone="accent">{a}</Badge>) : <span className="text-xs text-faint">None stand out.</span>}
                </div>
              </div>
            </div>
            {detailed ? <ExplainedSections value={{ facts: b.content.facts, interpretation: b.content.interpretation, uncertainty: b.content.uncertainty }} /> : null}
            {b.content.warnings?.length ? <BulletList items={b.content.warnings} tone="warn" /> : null}
          </div>
        ) : null}
      </PanelBody>
    </Panel>
  );
}
