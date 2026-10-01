"use client";

import type { PerformanceReport } from "@nexus/shared-types";
import { Bot, ChartNoAxesCombined } from "lucide-react";

import { Callout } from "@/components/common/disclaimer";
import { PageContainer, PageHeader } from "@/components/common/page-header";
import { Stat } from "@/components/common/stat";
import { DataBlock, EmptyState } from "@/components/common/states";
import { PerformanceSection } from "@/components/panels/performance";
import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { fmtMoney, fmtNum, titleCase } from "@/lib/format";

interface ModelAnalytics {
  providers: { provider: string; calls: number; errors: number; cached: number; avg_latency_ms: number | null; cost_usd: number | null; input_tokens: number | null; output_tokens: number | null }[];
  agreement_levels: Record<string, number>;
  agreement_rate: number | null;
  disagreement_rate: number | null;
  critic_verdicts: Record<string, number>;
  critic_rejection_rate: number | null;
  disclaimer: string;
  pricing_note: string;
}

const pct = (v: number | null) => (v === null ? "—" : `${fmtNum(v * 100, 1)}%`);

export function AnalyticsView() {
  const perf = useApi<{ paper: PerformanceReport; signals: PerformanceReport; notes: string[] }>("/api/analytics/performance", 60_000);
  const models = useApi<ModelAnalytics>("/api/ai/analytics", 60_000);
  return (
    <PageContainer>
      <PageHeader title="Analytics" description="Performance of paper trades and of signals (hypothetical, in R), plus AI model usage, agreement and critic statistics." />
      <Tabs defaultValue="paper">
        <TabsList>
          <TabsTrigger value="paper">Paper trading</TabsTrigger>
          <TabsTrigger value="signals">Signal outcomes</TabsTrigger>
          <TabsTrigger value="models">AI model analytics</TabsTrigger>
        </TabsList>
        <TabsContent value="paper">
          <DataBlock data={perf.data} error={perf.error} isLoading={perf.isLoading} onRetry={() => perf.mutate()}>
            {(d) => (
              <div className="flex flex-col gap-3">
                <Callout tone="info">{d.notes.join(" ")}</Callout>
                <PerformanceSection report={d.paper} unit="usd" title="Paper trades (SIMULATED)" />
              </div>
            )}
          </DataBlock>
        </TabsContent>
        <TabsContent value="signals">
          <DataBlock data={perf.data} error={perf.error} isLoading={perf.isLoading} onRetry={() => perf.mutate()}>
            {(d) => (
              <div className="flex flex-col gap-3">
                <Callout tone="warn">Signal performance assumes each signal was followed exactly per its plan and is expressed in R. It is hypothetical and excludes execution costs beyond the plan.</Callout>
                <PerformanceSection report={d.signals} unit="r" title="Resolved signals" />
              </div>
            )}
          </DataBlock>
        </TabsContent>
        <TabsContent value="models">
          <DataBlock data={models.data} error={models.error} isLoading={models.isLoading} onRetry={() => models.mutate()}>
            {(m) => (
              <div className="flex flex-col gap-3">
                <Callout tone="warn" title="Interpretation">
                  {m.disclaimer}
                </Callout>
                <Panel>
                  <PanelHeader title="Agreement & critic" icon={<ChartNoAxesCombined />} />
                  <PanelBody className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <Stat label="Agreement rate" value={pct(m.agreement_rate)} hint="HIGH or MEDIUM consensus among compared reviews" />
                    <Stat label="Disagreement rate" value={pct(m.disagreement_rate)} hint="LOW or CONFLICT consensus" />
                    <Stat label="Critic rejection rate" value={pct(m.critic_rejection_rate)} />
                    <Stat label="Consensus records" value={Object.values(m.agreement_levels).reduce((a, b) => a + b, 0)} />
                  </PanelBody>
                  <PanelBody className="flex flex-wrap gap-1.5 border-t border-line">
                    {Object.entries(m.agreement_levels).map(([k, v]) => (
                      <Badge key={k}>
                        {k} {v}
                      </Badge>
                    ))}
                    {Object.entries(m.critic_verdicts).map(([k, v]) => (
                      <Badge key={k} tone="purple">
                        critic {titleCase(k)} {v}
                      </Badge>
                    ))}
                    {!Object.keys(m.agreement_levels).length && !Object.keys(m.critic_verdicts).length ? <span className="text-xs text-faint">No AI reviews recorded yet.</span> : null}
                  </PanelBody>
                </Panel>
                <Panel>
                  <PanelHeader title="Calls by provider" icon={<Bot />} subtitle={m.pricing_note} />
                  {m.providers.length ? (
                    <Table>
                      <THead>
                        <tr>
                          <TH>Provider</TH>
                          <TH align="right">Calls</TH>
                          <TH align="right">Errors</TH>
                          <TH align="right">Cached</TH>
                          <TH align="right">Avg latency</TH>
                          <TH align="right">Tokens in / out</TH>
                          <TH align="right">Cost estimate</TH>
                        </tr>
                      </THead>
                      <tbody>
                        {m.providers.map((p) => (
                          <TR key={p.provider}>
                            <TD className="font-medium">{p.provider}</TD>
                            <TD align="right" className="num">
                              {p.calls}
                            </TD>
                            <TD align="right" className={p.errors ? "num text-down" : "num"}>
                              {p.errors}
                            </TD>
                            <TD align="right" className="num">
                              {p.cached}
                            </TD>
                            <TD align="right" className="num">
                              {p.avg_latency_ms === null ? "—" : `${fmtNum(p.avg_latency_ms / 1000, 2)}s`}
                            </TD>
                            <TD align="right" className="num">
                              {p.input_tokens ?? "—"} / {p.output_tokens ?? "—"}
                            </TD>
                            <TD align="right" className="num">
                              {p.cost_usd === null ? "n/a" : fmtMoney(p.cost_usd, 4)}
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                  ) : (
                    <EmptyState title="No AI calls recorded" description="Configure Claude or Gemini in Settings. Rule-based demo summaries are not counted as AI calls." />
                  )}
                </Panel>
              </div>
            )}
          </DataBlock>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
