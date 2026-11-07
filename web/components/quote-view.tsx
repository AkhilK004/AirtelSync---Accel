"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, Share2 } from "lucide-react";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { type Quote, getQuote, quoteShared, toggleAddon } from "@/lib/api";
import { useApiError } from "@/lib/use-api-error";

export function QuoteView({ quoteId }: { quoteId: string }) {
  const t = useTranslations("quote");
  const retry = useTranslations("common")("retry");
  const locale = useLocale();
  const errText = useApiError();
  const [q, setQ] = useState<Quote | null>(null);
  const [failed, setFailed] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [touched, setTouched] = useState(false); // animate only after the owner changes something, not on page load

  const load = useCallback((view = false) => {
    getQuote(quoteId, locale, view).then(setQ).catch(() => setFailed(true));
  }, [quoteId, locale]);
  useEffect(() => {
    load(true); // the first load of the page counts as a quote view; refetches after a toggle do not
  }, [load]);

  async function onToggle(sku: string, on: boolean) {
    setPending(sku);
    try {
      const r = await toggleAddon(quoteId, sku, on, locale); // totals always come from the API
      setTouched(true);
      setQ(r.quote);
      r.notices.forEach((n) => toast.info(n.text));
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setPending(null);
    }
  }

  if (failed)
    return (
      <div className="flex flex-col items-start gap-3 p-4">
        <p>{t("notFound")}</p>
        <Button variant="outline" className="h-11" onClick={() => {
            setFailed(false);
            load();
          }}>
          {retry}
        </Button>
      </div>
    );
  if (!q)
    return (
      <div className="flex flex-col gap-3 p-4" aria-busy="true">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );

  const shareText = t("shareText", { bundle: q.bundle_title, total: q.monthly_total_display });
  const shareHref = `https://wa.me/?text=${encodeURIComponent(`${shareText} ${typeof window !== "undefined" ? window.location.href : ""}`)}`;
  const assumptions = q.assumptions.filter((a) => a.key !== "gst_extra");

  return (
    <main className="flex flex-col gap-6 px-4 pb-32 pt-5">
      <div>
        <p className="text-sm text-muted-foreground">{t("title")}</p>
        <h1 className="font-display text-[1.9rem] leading-tight text-primary">{q.bundle_title}</h1>
      </div>

      {q.assisted && <div className="rounded-md border border-action bg-action/15 p-3 text-sm">{t("assisted")}</div>}

      {/* The bill slip: ledger rows with dotted leaders; the total ticks when it changes */}
      <section className="slip" aria-label={q.bundle_title}>
        <ul className="px-4 pt-2">
          {q.lines.map((l) => (
            <li key={l.sku} className={`border-b border-dashed py-3 last:border-b-0 ${touched && !l.required ? "animate-stamp" : ""}`}>
              <div className="flex items-baseline gap-2">
                <span className="font-semibold">{l.name}</span>
                <span className="leader" aria-hidden />
                <span className="tabular shrink-0 font-semibold">{l.line_monthly_display}</span>
              </div>
              <div className="text-sm text-muted-foreground">{l.reason}</div>
              <div className="text-xs text-muted-foreground">
                {l.required ? t("included") + " · " : ""}
                {t("each", { qty: l.qty, price: l.unit_price_display })}
              </div>
            </li>
          ))}
        </ul>
        <hr className="slip-rule mx-4" />
        <div key={q.monthly_total_display} className={`mx-2 mt-2 rounded-md px-2 py-3 ${touched ? "animate-tick" : ""}`} aria-live="polite">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-base font-semibold">{t("monthlyTotal")}</span>
            <span className="font-display tabular text-[2.4rem] leading-none text-primary">{q.monthly_total_display}</span>
          </div>
          <div className="mt-1 text-sm text-muted-foreground">
            {t("perMonth")} · {t("contract", { months: q.contract_months })}
          </div>
        </div>
      </section>

      {q.addons.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">{t("extras")}</h2>
          <p className="text-sm text-muted-foreground">{t("extrasHint")}</p>
          <ul className="flex flex-col gap-2">
            {q.addons.map((a) => (
              <li key={a.sku} className={`flex items-center gap-3 rounded-lg border bg-card p-3 ${a.on ? "border-primary" : ""}`}>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{a.name}</div>
                  <div className="text-sm text-muted-foreground">{a.reason}</div>
                  <div className="tabular mt-1 text-sm font-medium">
                    +{a.monthly_display}
                    {a.setup_display !== "₹0" && <span className="font-normal text-muted-foreground"> · {t("setup", { amount: a.setup_display })}</span>}
                  </div>
                </div>
                <Switch
                  checked={a.on}
                  disabled={pending !== null}
                  onCheckedChange={(v) => onToggle(a.sku, v)}
                  aria-label={a.name}
                  className="scale-125"
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      {assumptions.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">{t("assumptions")}</h2>
          <ul className="flex flex-col gap-1.5 text-sm">
            {assumptions.map((a) => (
              <li key={a.key} className="rounded-md bg-muted px-3 py-2">
                {a.text}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-lg border bg-card">
        <button className="flex min-h-12 w-full items-center justify-between px-4 text-left font-medium" onClick={() => setOpen(!open)} aria-expanded={open}>
          {t("breakdown")}
          <ChevronDown className={`size-5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
        </button>
        {open && (
          <dl className="flex flex-col gap-1.5 border-t p-4 text-sm">
            <Row k={t("subtotal")} v={q.monthly_subtotal_display} />
            <Row k={t("gst", { rate: q.gst_rate_pct })} v={q.gst_display} />
            <Row k={t("monthlyTotal")} v={q.monthly_total_display} bold />
            {q.one_time_paise > 0 && (
              <>
                <hr className="slip-rule my-1" />
                <Row k={t("oneTime")} v={q.one_time_display} />
                <Row k={t("oneTimeGst")} v={q.one_time_gst_display} />
                <Row k={t("oneTimeTotal")} v={q.one_time_total_display} bold />
              </>
            )}
          </dl>
        )}
      </section>

      <a href={shareHref} onClick={() => quoteShared(quoteId)} target="_blank" rel="noopener noreferrer" className={`${buttonVariants({ variant: "outline" })} h-12 gap-2 border-primary text-base text-primary`}>
        <Share2 aria-hidden /> {t("share")}
      </a>

      <div className="fixed inset-x-0 bottom-0 border-t bg-card p-4">
        <div className="mx-auto flex max-w-md items-center gap-3">
          <div className="min-w-0">
            <div className="font-display tabular text-2xl leading-none text-primary">{q.monthly_total_display}</div>
            <div className="mt-1 text-xs text-muted-foreground">{t("perMonth")}</div>
          </div>
          <Link href={`/${locale}/checkout/${q.id}`} className={`${buttonVariants({ size: "lg" })} ml-auto h-12 px-8 text-base`}>
            {t("continue")}
          </Link>
        </div>
      </div>
    </main>
  );
}

function Row({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div className={`flex items-baseline gap-2 ${bold ? "font-semibold" : ""}`}>
      <dt>{k}</dt>
      <span className="leader" aria-hidden />
      <dd className="tabular">{v}</dd>
    </div>
  );
}
