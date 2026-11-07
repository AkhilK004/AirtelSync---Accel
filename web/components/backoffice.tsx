"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AuthError, type Funnel, type Lead, type LeadDetail,
  clearAuth, getAuth, getFunnel, leadDetail, listLeads, me, resetDemo, setAuth, setLeadStatus,
} from "@/lib/backoffice-api";

const DEMO_TOKEN = process.env.NEXT_PUBLIC_DEMO_ADMIN_TOKEN ?? "";
const SEGMENTS = [["micro_retail", "Micro retail"], ["professional_office", "Professional office"], ["multi_site", "Multi-site"], ["manufacturer", "Manufacturer"]];
const STAGES = ["advisor", "quote", "checkout", "kyc", "order"];
const ROUTES = [["field_sales", "Field sales"], ["partner", "Partner"], ["telesales", "Telesales"], ["compliance", "Compliance hold"]];
const ACTION_LABEL: Record<string, string> = { kyc_assist_udyam: "KYC assist: Udyam path", restore_gstin: "Restore GSTIN" };
const HOLD_LABEL: Record<string, string> = { gstin_cancelled: "GSTIN cancelled", gstin_suspended: "GSTIN suspended", gstin_inactive: "GSTIN not active" };
const STATUSES = ["new", "contacted", "won", "lost"];
const REASON_LABEL: Record<string, string> = {
  needs_site_survey: "Needs site survey", requested_human: "Asked for a person", price: "Price", abandoned: "Abandoned", quote_not_accepted: "Quote not accepted",
  kyc_issue: "KYC issue", callback_requested: "Callback requested",
};
const label = (m: string[][], k: string | null) => m.find((x) => x[0] === k)?.[1] ?? k ?? "—";
const age = (h: number) => (h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)}d`);

export function BackOffice() {
  const authStored = useSyncExternalStore(() => () => {}, () => getAuth() ?? "", () => null);
  const [override, setOverride] = useState<string | null | undefined>(undefined);
  const auth = override !== undefined ? override : authStored || null;
  if (authStored === null) return <div className="p-6"><Skeleton className="h-40 w-full max-w-md" /></div>;
  if (!auth) return <Login onAuth={setOverride} />;
  return <Dashboard auth={auth} onSignOut={() => { clearAuth(); setOverride(null); }} />;
}

function Login({ onAuth }: { onAuth: (a: string) => void }) {
  const [u, setU] = useState("admin");
  const [p, setP] = useState("");
  const [err, setErr] = useState(false);
  async function go(e: React.FormEvent) {
    e.preventDefault();
    const a = btoa(`${u}:${p}`);
    try {
      await me(a);
      setAuth(u, p);
      onAuth(a);
    } catch {
      setErr(true);
    }
  }
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">Back-office</h1>
      <form onSubmit={go} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">Username<Input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" className="h-10" /></label>
        <label className="flex flex-col gap-1 text-sm">Password<Input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" className="h-10" /></label>
        {err && <p role="alert" className="text-sm text-red-600">Wrong username or password.</p>}
        <Button type="submit" className="h-11" disabled={!p}>Sign in</Button>
      </form>
    </main>
  );
}

function Dashboard({ auth, onSignOut }: { auth: string; onSignOut: () => void }) {
  const [filters, setFilters] = useState({ route: "", segment: "", stage: "", status: "" });
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const [tick, setTick] = useState(0);
  const load = useCallback(() => setTick((t) => t + 1), []);
  useEffect(() => {
    let alive = true;
    Promise.all([listLeads(auth, filters), getFunnel(auth)])
      .then(([l, f]) => {
        if (!alive) return;
        setLeads(l);
        setFunnel(f);
      })
      .catch((e) => {
        if (e instanceof AuthError) onSignOut();
        else toast.error("Could not load data");
      });
    return () => {
      alive = false;
    };
  }, [auth, filters, onSignOut, tick]);

  async function reset() {
    await resetDemo(DEMO_TOKEN);
    toast.success("Demo data reset");
    load();
  }

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Back-office</h1>
          <p className="text-sm text-muted-foreground">Leads the advisor could not close, ranked by chance to activate</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}><RefreshCw /> Refresh</Button>
          {DEMO_TOKEN && <Button variant="outline" size="sm" onClick={reset}>Reset demo data</Button>}
          <Button variant="ghost" size="sm" onClick={onSignOut}>Sign out</Button>
        </div>
      </header>

      {funnel ? <FunnelPanel f={funnel} /> : <Skeleton className="h-56 w-full" />}

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2" aria-label="filters">
          <Select name="Route" value={filters.route} options={ROUTES} onChange={(v) => setFilters({ ...filters, route: v })} />
          <Select name="Segment" value={filters.segment} options={SEGMENTS} onChange={(v) => setFilters({ ...filters, segment: v })} />
          <Select name="Stage" value={filters.stage} options={STAGES.map((s) => [s, s])} onChange={(v) => setFilters({ ...filters, stage: v })} />
          <Select name="Status" value={filters.status} options={STATUSES.map((s) => [s, s])} onChange={(v) => setFilters({ ...filters, status: v })} />
          <span className="self-center text-sm text-muted-foreground">{leads ? `${leads.length} leads` : ""}</span>
        </div>
        <div className="overflow-x-auto rounded-xl border bg-background">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-36">Score</TableHead><TableHead title="Chance of activating x typical monthly bundle value for the segment">Exp. value / mo</TableHead><TableHead>Business</TableHead><TableHead>Stage</TableHead><TableHead>Reason</TableHead>
                <TableHead>Route</TableHead><TableHead>Team</TableHead><TableHead>Age</TableHead><TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads?.map((l) => (
                <TableRow key={l.id} onClick={() => setOpen(l.id)} className="cursor-pointer" data-lead={l.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-16 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary" style={{ width: `${Math.min(100, (l.score ?? 0) * 100 * 4)}%` }} /></div>
                      <span className="text-xs tabular-nums">{l.score != null ? `${(l.score * 100).toFixed(0)}%` : "—"}</span>
                    </div>
                  </TableCell>
                  <TableCell className="tabular-nums">{l.compliance_hold ? <Badge variant="destructive">{HOLD_LABEL[l.compliance_hold] ?? l.compliance_hold}</Badge> : l.expected_value_display}</TableCell>
                  <TableCell><div className="font-medium">{l.name}</div><div className="text-xs text-muted-foreground">{label(SEGMENTS, l.segment)}{l.city ? ` · ${l.city}` : ""}</div>{l.next_action ? <Badge variant="outline" className="mt-1" title={l.next_action.text}>{ACTION_LABEL[l.next_action.code] ?? l.next_action.code}</Badge> : null}</TableCell>
                  <TableCell className="capitalize">{l.stage}</TableCell>
                  <TableCell>{REASON_LABEL[l.reason] ?? l.reason}</TableCell>
                  <TableCell>{label(ROUTES, l.route)}{l.partner_code ? <div className="text-xs text-muted-foreground">{l.partner_code}</div> : null}</TableCell>
                  <TableCell>{l.territory_team}</TableCell>
                  <TableCell className="tabular-nums">{age(l.age_hours)}</TableCell>
                  <TableCell><Badge variant={l.status === "won" ? "default" : l.status === "lost" ? "destructive" : "secondary"}>{l.status}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {leads === null && <Skeleton className="m-3 h-40" />}
        </div>
        <p className="text-xs text-muted-foreground">Score = modelled chance the lead activates (logistic regression on creation-time facts; ranking tool, not a forecast). Reasons show the three strongest drivers.</p>
      </section>

      <LeadSheet auth={auth} id={open} onClose={() => setOpen(null)} onChanged={load} />
    </main>
  );
}

function Select({ name, value, options, onChange }: { name: string; value: string; options: string[][]; onChange: (v: string) => void }) {
  return (
    <select aria-label={name} value={value} onChange={(e) => onChange(e.target.value)} className="h-9 rounded-lg border bg-background px-2 text-sm">
      <option value="">{name}: all</option>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

function Kpi({ title, value, base, target, unit = "" }: { title: string; value: number | null; base?: number; target?: number; unit?: string }) {
  return (
    <div className="rounded-xl border bg-background p-3">
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className="text-2xl font-semibold tabular-nums">{value == null ? "—" : `${value}${unit}`}</div>
      {(base != null || target != null) && <div className="text-xs text-muted-foreground">{base != null && `baseline ${base}${unit}`}{base != null && target != null && " · "}{target != null && `target ${target}${unit}`}</div>}
    </div>
  );
}

function FunnelPanel({ f }: { f: Funnel }) {
  const max = Math.max(1, ...f.stages.map((s) => s.count));
  const k = f.kpis;
  return (
    <section className="grid gap-4 lg:grid-cols-2" aria-label="funnel">
      <div className="rounded-xl border bg-background p-4">
        <h2 className="mb-3 font-semibold">Funnel</h2>
        <ul className="flex flex-col gap-2">
          {f.stages.map((s) => (
            <li key={s.key} className="grid grid-cols-[9rem_1fr_6rem] items-center gap-2 text-sm">
              <span>{s.label}</span>
              <div className="h-5 overflow-hidden rounded bg-muted"><div className="h-full bg-primary/80" style={{ width: `${(s.count / max) * 100}%` }} /></div>
              <span className="text-right tabular-nums">{s.count}{s.pct_of_prev != null && <span className="text-xs text-muted-foreground"> ({s.pct_of_prev}%)</span>}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">{f.seeded_events} of {f.total_events} events are seeded demo data.</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Kpi title="Lead → activation" value={k.lead_to_activation_pct} base={f.baseline.lead_to_activation_pct} target={f.target.lead_to_activation_pct} unit="%" />
        <Kpi title="Needs → quote accepted" value={k.needs_to_quote_pct} base={f.baseline.needs_to_quote_pct} target={f.target.needs_to_quote_pct} unit="%" />
        <Kpi title="Median days to activate" value={k.median_days_to_activate} base={f.baseline.days_to_activate} target={f.target.days_to_activate} />
        <Kpi title="KYC auto-approval" value={k.kyc_auto_approval_pct} unit="%" />
        <Kpi title="Status checks per order" value={k.status_checks_per_order} base={f.baseline.status_checks_per_order} target={f.target.status_checks_per_order} />
        <Kpi title="Handoffs to people" value={k.handoffs} />
      </div>
    </section>
  );
}

function LeadSheet({ auth, id, onClose, onChanged }: { auth: string; id: string | null; onClose: () => void; onChanged: () => void }) {
  const [d, setD] = useState<LeadDetail | null>(null);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    leadDetail(auth, id).then((v) => { setD(v); setLoadedId(id); }).catch(() => toast.error("Could not load lead"));
  }, [auth, id]);
  const cur = d && loadedId === id ? d : null;
  async function mark(status: string) {
    if (!id) return;
    await setLeadStatus(auth, id, status);
    toast.success(`Marked ${status}`);
    setD(await leadDetail(auth, id));
    onChanged();
  }
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto p-4 sm:max-w-md">
        <SheetHeader className="p-0">
          <SheetTitle>{cur?.name ?? "Lead"}</SheetTitle>
          <SheetDescription>{cur ? `${label(ROUTES, cur.route)} · ${cur.territory_team} team${cur.partner_code ? ` · ${cur.partner_code}` : ""}` : "Loading…"}</SheetDescription>
        </SheetHeader>
        {!cur ? <Skeleton className="h-40" /> : (
          <div className="flex flex-col gap-4">
            <div>
              <div className="text-sm font-medium">Why this score ({cur.score != null ? `${(cur.score * 100).toFixed(1)}%` : "—"})</div>
              <div className="mt-1 flex flex-wrap gap-1.5">{cur.score_reasons.map((r) => <Badge key={r} variant={r.endsWith("↑") ? "secondary" : "outline"}>{r}</Badge>)}</div>
            </div>
            {cur.next_action ? <div className="rounded-lg border border-primary/40 p-2 text-sm" data-next-action={cur.next_action.code}><span className="font-medium">Next step:</span> {cur.next_action.text}</div> : null}
            {cur.compliance_hold ? (
              <div className="rounded-lg border border-destructive/40 p-2 text-sm"><span className="font-medium">Compliance hold:</span> {HOLD_LABEL[cur.compliance_hold] ?? cur.compliance_hold}</div>
            ) : (
              <div className="text-sm"><span className="font-medium">Expected value:</span> {cur.expected_value_display} / month (chance of activating x typical bundle value for the segment)</div>
            )}
            <div className="text-sm"><span className="font-medium">Why it is here:</span> {REASON_LABEL[cur.reason] ?? cur.reason} · stage {cur.stage}</div>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-lg bg-muted p-3 text-sm">
              {Object.entries(cur.profile).map(([k, v]) => <div key={k}><dt className="text-xs text-muted-foreground">{k.replace(/_/g, " ")}</dt><dd>{Array.isArray(v) ? v.join(", ") : String(v)}</dd></div>)}
              {cur.phone_masked && <div><dt className="text-xs text-muted-foreground">phone</dt><dd>{cur.phone_masked}</dd></div>}
            </dl>
            {cur.quote && (
              <div className="rounded-lg border p-3 text-sm">
                <div className="font-medium">{cur.quote.bundle} · {cur.quote.monthly_total_display}/month incl. GST</div>
                <ul className="mt-1 text-muted-foreground">{cur.quote.lines.map((l) => <li key={l.name}>{l.name} × {l.qty} — {l.monthly}</li>)}</ul>
                {cur.quote.assumptions.map((a) => <p key={a} className="mt-1 text-xs">{a}</p>)}
              </div>
            )}
            {cur.order && <div className="text-sm"><span className="font-medium">Order:</span> {cur.order.state}</div>}
            {cur.kyc && (
              <div className="rounded-lg border p-3 text-sm">
                <div className="font-medium">KYC: {cur.kyc.decision?.status ?? "not evaluated"}</div>
                <ul className="mt-1 flex flex-col gap-1">{cur.kyc.issues.map((i, n) => <li key={n}><span className={i.status === "FAIL" ? "text-red-600" : "text-amber-600"}>{i.status}</span> {i.label}: {i.message}</li>)}</ul>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {["contacted", "won", "lost"].map((s) => <Button key={s} size="sm" variant={cur.status === s ? "default" : "outline"} onClick={() => mark(s)}>Mark {s}</Button>)}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
