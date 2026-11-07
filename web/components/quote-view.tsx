"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, Share2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
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
      <div className="flex flex-col gap-3 p-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-16 w-56" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );

  const shareText = t("shareText", { bundle: q.bundle_title, total: q.monthly_total_display });
  const shareHref = `https://wa.me/?text=${encodeURIComponent(`${shareText} ${typeof window !== "undefined" ? window.location.href : ""}`)}`;
  const assumptions = q.assumptions.filter((a) => a.key !== "gst_extra");

  return (
    <main className="flex flex-col gap-5 px-4 pb-32 pt-4">
      <section>
        <div className="text-sm text-muted-foreground">{t("title")}</div>
        <h1 className="text-xl font-semibold">{q.bundle_title}</h1>
        <div className="mt-2 text-4xl font-bold tracking-tight">{q.monthly_total_display}</div>
        <div className="text-sm text-muted-foreground">
          {t("perMonth")} · {t("contract", { months: q.contract_months })}
        </div>
      </section>

      {q.assisted && <div className="rounded-lg bg-muted p-3 text-sm">{t("assisted")}</div>}

      <section className="flex flex-col gap-2">
        {q.lines
          .filter((l) => l.required)
          .map((l) => (
            <LineCard key={l.sku} line={l} included={t("included")} each={t("each", { qty: l.qty, price: l.unit_price_display })} />
          ))}
      </section>

      {q.addons.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">{t("extras")}</h2>
          <p className="text-sm text-muted-foreground">{t("extrasHint")}</p>
          {q.addons.map((a) => (
            <div key={a.sku} className="flex items-center gap-3 rounded-xl border p-3">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{a.name}</div>
                <div className="text-sm text-muted-foreground">{a.reason}</div>
                <div className="mt-1 text-sm">
                  +{a.monthly_display}
                  {a.setup_display !== "₹0" && <span className="text-muted-foreground"> · {t("setup", { amount: a.setup_display })}</span>}
                </div>
              </div>
              <Switch
                checked={a.on}
                disabled={pending !== null}
                onCheckedChange={(v) => onToggle(a.sku, v)}
                aria-label={a.name}
                className="scale-125"
              />
            </div>
          ))}
        </section>
      )}

      {assumptions.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-muted-foreground">{t("assumptions")}</h2>
          <div className="flex flex-wrap gap-2">
            {assumptions.map((a) => (
              <Badge key={a.key} variant="secondary" className="h-auto whitespace-normal py-1 text-left text-xs font-normal">
                {a.text}
              </Badge>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-xl border">
        <button className="flex h-12 w-full items-center justify-between px-3 text-left font-medium" onClick={() => setOpen(!open)} aria-expanded={open}>
          {t("breakdown")}
          <ChevronDown className={`size-5 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <dl className="flex flex-col gap-1 border-t p-3 text-sm">
            <Row k={t("subtotal")} v={q.monthly_subtotal_display} />
            <Row k={t("gst", { rate: q.gst_rate_pct })} v={q.gst_display} />
            <Row k={t("monthlyTotal")} v={q.monthly_total_display} bold />
            {q.one_time_paise > 0 && (
              <>
                <div className="my-1 border-t" />
                <Row k={t("oneTime")} v={q.one_time_display} />
                <Row k={t("oneTimeGst")} v={q.one_time_gst_display} />
                <Row k={t("oneTimeTotal")} v={q.one_time_total_display} bold />
              </>
            )}
          </dl>
        )}
      </section>

      <a href={shareHref} onClick={() => quoteShared(quoteId)} target="_blank" rel="noopener noreferrer" className={`${buttonVariants({ variant: "outline" })} h-11 gap-2 text-base`}>
        <Share2 /> {t("share")}
      </a>

      <div className="fixed inset-x-0 bottom-0 border-t bg-background p-4">
        <div className="mx-auto flex max-w-md items-center gap-3">
          <div className="min-w-0">
            <div className="text-lg font-bold leading-none">{q.monthly_total_display}</div>
            <div className="text-xs text-muted-foreground">{t("perMonth")}</div>
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
    <div className={`flex justify-between ${bold ? "font-semibold" : ""}`}>
      <dt>{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}

function LineCard({ line, included, each }: { line: Quote["lines"][number]; included: string; each: string }) {
  return (
    <div className="rounded-xl border p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium">{line.name}</div>
        <div className="shrink-0 font-semibold">{line.line_monthly_display}</div>
      </div>
      <div className="text-sm text-muted-foreground">{line.reason}</div>
      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
        {line.required && <Badge variant="secondary">{included}</Badge>}
        <span>{each}</span>
      </div>
    </div>
  );
}
