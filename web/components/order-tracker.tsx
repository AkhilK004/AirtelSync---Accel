"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2, Circle, CircleDot, MessageCircle, Smartphone } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, type OrderView, demoAdvance, getMeta, getOrder, orderCallback, rescheduleOrder } from "@/lib/api";
import { useApiError } from "@/lib/use-api-error";

const POLL_MS = 5000;
const DEMO_TOKEN = process.env.NEXT_PUBLIC_DEMO_ADMIN_TOKEN ?? "";

function addDays(iso: string, n: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function OrderTracker({ orderId }: { orderId: string }) {
  const t = useTranslations("track");
  const locale = useLocale();
  const errText = useApiError();
  const demo = useSearchParams().get("demo") === "1" && !!DEMO_TOKEN;
  // last 4 digits saved at checkout; null on the server (not ready), "" when absent. An override wins once the user types or access is denied.
  const stored = useSyncExternalStore(
    () => () => {},
    () => {
      try {
        return sessionStorage.getItem(`order:${orderId}:last4`) ?? "";
      } catch {
        return "";
      }
    },
    () => null,
  );
  const [override, setOverride] = useState<string | null | undefined>(undefined);
  const ready = stored !== null;
  const last4 = override !== undefined ? override : stored || null;
  const setLast4 = setOverride;
  const [input, setInput] = useState("");
  const [o, setO] = useState<OrderView | null>(null);
  const [tab, setTab] = useState<"timeline" | "messages">("timeline");
  const [resOpen, setResOpen] = useState(false);
  const first = useRef(true);

  const fmt = useCallback((iso: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" }) : ""), [locale]);

  const load = useCallback(async () => {
    if (!last4) return;
    try {
      const v = await getOrder(orderId, last4, locale, first.current);
      first.current = false;
      setO(v);
    } catch (e) {
      if (e instanceof ApiError && e.code === "ORDER_ACCESS") {
        try {
          sessionStorage.removeItem(`order:${orderId}:last4`);
        } catch {
          /* ignore */
        }
        setLast4(null);
      }
      toast.error(errText(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId, last4, locale]);

  useEffect(() => {
    if (!last4) return;
    load();
    const id = setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
    return () => clearInterval(id);
  }, [last4, load]);

  if (!ready) return <div className="p-4"><Skeleton className="h-40 w-full" /></div>;
  if (!last4)
    return (
      <main className="flex flex-col gap-4 p-4">
        <h1 className="text-xl font-semibold">{t("last4Title")}</h1>
        <p className="text-sm text-muted-foreground">{t("last4Hint")}</p>
        <Input inputMode="numeric" maxLength={4} value={input} onChange={(e) => setInput(e.target.value.replace(/\D/g, ""))} aria-label={t("last4")} className="h-12 text-center text-xl tracking-[0.5em]" />
        <Button className="h-12 text-base" disabled={input.length !== 4} onClick={() => setLast4(input)}>{t("show")}</Button>
      </main>
    );
  if (!o)
    return <div className="flex flex-col gap-3 p-4"><Skeleton className="h-10 w-48" /><Skeleton className="h-64 w-full" /></div>;

  async function callback() {
    try {
      await orderCallback(orderId, last4!);
      toast.success(t("helpDone"));
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  }
  async function advance() {
    try {
      setO(await demoAdvance(orderId, DEMO_TOKEN, locale));
    } catch (e) {
      toast.error(errText(e));
    }
  }

  return (
    <main className="flex flex-col gap-5 px-4 pb-24 pt-4">
      <div>
        <div className="text-xs text-muted-foreground">{t("order")} {o.id.slice(-6).toUpperCase()}</div>
        <h1 className="text-xl font-semibold">{o.business_name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge className="text-sm">{o.state_label}</Badge>
          {o.eta_activation && o.state !== "ACTIVATED" && o.state !== "CANCELLED" && <span className="text-sm text-muted-foreground">{t("activeBy", { date: fmt(o.eta_activation) })}</span>}
        </div>
      </div>

      {o.side_message && (
        <div role="status" className={`rounded-xl p-3 text-sm ${o.side_state === "CANCELLED" ? "bg-red-50 text-red-900" : o.side_state === "KYC_ACTION_REQUIRED" ? "bg-amber-50 text-amber-900" : "bg-blue-50 text-blue-900"}`}>
          {o.side_message}
        </div>
      )}
      {o.needs_kyc && (
        <Link href={`/${locale}/kyc/${orderId}`} className={`${buttonVariants({ size: "lg" })} h-12 text-base`}>{t("fixDocs")}</Link>
      )}

      <div className="flex gap-2" role="tablist">
        {(["timeline", "messages"] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`h-10 flex-1 rounded-full border text-sm ${tab === k ? "border-primary bg-primary/10 font-medium" : ""}`}>{t(k)}</button>
        ))}
      </div>

      {tab === "timeline" ? (
        <>
          <ol className="flex flex-col">
            {o.steps.map((s, i) => (
              <li key={s.key} className="flex gap-3" data-status={s.status}>
                <div className="flex flex-col items-center">
                  {s.status === "done" ? <CheckCircle2 className="size-6 text-green-600" /> : s.status === "current" ? <CircleDot className="size-6 text-primary" /> : <Circle className="size-6 text-muted-foreground/50" />}
                  {i < o.steps.length - 1 && <div className={`my-1 w-0.5 flex-1 ${s.status === "done" ? "bg-green-600" : "bg-muted"}`} />}
                </div>
                <div className={`pb-5 ${s.status === "current" ? "font-semibold" : s.status === "upcoming" ? "text-muted-foreground" : ""}`}>
                  <div>{s.label}</div>
                  {s.eta && <div className="text-xs font-normal text-muted-foreground">{fmt(s.eta)}</div>}
                </div>
              </li>
            ))}
          </ol>

          {o.tech && (
            <div className="rounded-xl border p-3 text-sm">
              <div className="text-muted-foreground">{t("technician")}</div>
              <div className="font-medium">{o.tech}</div>
              <div className="mt-1">{t("visit")}: {fmt(o.slot.date)}, {o.slot.window_label}</div>
            </div>
          )}

          <section className="flex flex-col gap-2">
            <h2 className="text-base font-semibold">{t("products")}</h2>
            {o.lines.map((l) => (
              <div key={l.sku} className="flex items-center justify-between gap-2 rounded-xl border p-3">
                <div className="min-w-0">
                  <div className="font-medium">{l.name}{l.qty > 1 ? ` × ${l.qty}` : ""}</div>
                  <div className="text-xs text-muted-foreground">
                    {l.status === "ACTIVATED" ? "" : l.mode === "digital" ? t("live") : l.install_days ? t("installDays", { days: l.install_days }) : ""}
                    {l.eta && l.status !== "ACTIVATED" ? ` · ${t("by", { date: fmt(l.eta) })}` : ""}
                  </div>
                </div>
                <Badge variant={l.status === "ACTIVATED" ? "default" : "secondary"} className="h-auto whitespace-normal text-center">{l.status_label}</Badge>
              </div>
            ))}
          </section>

        </>
      ) : (
        <ul className="flex flex-col gap-3">
          {o.messages.length === 0 && <li className="text-sm text-muted-foreground">{t("noMessages")}</li>}
          {o.messages.map((m, i) => (
            <li key={i} className="flex gap-2 rounded-xl bg-muted p-3 text-sm">
              {m.channel === "whatsapp" ? <MessageCircle className="mt-0.5 size-4 shrink-0 text-green-600" aria-label={t("whatsapp")} /> : <Smartphone className="mt-0.5 size-4 shrink-0" aria-label={t("sms")} />}
              <div><div>{m.text}</div><div className="mt-0.5 text-xs text-muted-foreground">{m.channel === "whatsapp" ? t("whatsapp") : t("sms")} · {m.ts.slice(11, 16)}</div></div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex gap-2">
        {o.can_reschedule && <Button variant="outline" className="h-11 flex-1" onClick={() => setResOpen(true)}>{t("reschedule")}</Button>}
        <Button variant="outline" className="h-11 flex-1" onClick={callback}>{t("help")}</Button>
      </div>
      {demo && o.state !== "ACTIVATED" && o.state !== "CANCELLED" && (
        <Button variant="secondary" className="h-11" onClick={advance}>{t("demoAdvance")}</Button>
      )}
      <p className="text-center text-xs text-muted-foreground">{t("refreshing")}</p>

      <RescheduleDialog open={resOpen} onOpenChange={setResOpen} current={o.slot.date} onSave={async (d, w) => {
        try {
          setO(await rescheduleOrder(orderId, last4, d, w, locale));
          setResOpen(false);
        } catch (e) {
          toast.error(errText(e));
        }
      }} />
    </main>
  );
}

function RescheduleDialog({ open, onOpenChange, current, onSave }: { open: boolean; onOpenChange: (o: boolean) => void; current: string; onSave: (d: string, w: string) => void }) {
  const t = useTranslations("track");
  const c = useTranslations("checkout");
  const [meta, setMeta] = useState<{ today: string; max_slot_days: number } | null>(null);
  const [date, setDate] = useState(current);
  const [win, setWin] = useState("morning");
  useEffect(() => {
    if (open) getMeta().then(setMeta).catch(() => {});
  }, [open]);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{t("rescheduleTitle")}</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">{t("date")}
            <Input type="date" value={date} min={meta ? addDays(meta.today, 1) : undefined} max={meta ? addDays(meta.today, meta.max_slot_days) : undefined} onChange={(e) => setDate(e.target.value)} className="h-11 text-base" />
          </label>
          <div className="flex gap-2">
            {(["morning", "evening"] as const).map((w) => (
              <Button key={w} type="button" variant={win === w ? "default" : "outline"} className="h-11 flex-1" onClick={() => setWin(w)}>{c(w)}</Button>
            ))}
          </div>
          <Button className="h-12 text-base" onClick={() => onSave(date, win)}>{t("save")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
