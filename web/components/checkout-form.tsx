"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { type Quote, getMeta, getQuote, placeOrder, sendOtp } from "@/lib/api";
import { useApiError } from "@/lib/use-api-error";

function addDays(iso: string, n: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function CheckoutForm({ quoteId }: { quoteId: string }) {
  const t = useTranslations("checkout");
  const locale = useLocale();
  const router = useRouter();
  const errText = useApiError();
  const [q, setQ] = useState<Quote | null>(null);
  const [meta, setMeta] = useState<{ today: string; max_slot_days: number } | null>(null);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [pincode, setPincode] = useState("");
  const [date, setDate] = useState("");
  const [win, setWin] = useState<"morning" | "evening">("morning");
  const [pay, setPay] = useState<"pay_on_activation" | "upi_mock">("pay_on_activation");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getQuote(quoteId, locale).then(setQ).catch((e) => toast.error(errText(e)));
    getMeta().then((m) => {
      setMeta(m);
      setDate(addDays(m.today, 2));
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quoteId, locale]);

  const phoneOk = /^[6-9]\d{9}$/.test(phone);
  const valid = phoneOk && /^\d{6}$/.test(otp) && name.trim().length >= 2 && address.trim().length >= 8 && !!date && (!pincode || /^\d{6}$/.test(pincode));
  const [minD, maxD] = useMemo(() => (meta ? [addDays(meta.today, 1), addDays(meta.today, meta.max_slot_days)] : ["", ""]), [meta]);

  async function onOtp() {
    try {
      await sendOtp(phone);
      setOtpSent(true);
    } catch (e) {
      toast.error(errText(e));
    }
  }

  async function submit() {
    setBusy(true);
    try {
      const r = await placeOrder({
        quote_id: quoteId, phone, otp, business_name: name, address, pincode: pincode || undefined,
        slot_date: date, slot_window: win, payment_mode: pay, language: locale,
      });
      try {
        sessionStorage.setItem(`order:${r.order_id}:last4`, phone.slice(-4)); // lets the tracker open without asking again
      } catch {
        /* storage blocked: the tracker will ask for the last 4 digits */
      }
      router.push(`/${locale}/kyc/${r.order_id}`);
    } catch (e) {
      toast.error(errText(e));
      setBusy(false);
    }
  }

  if (!q) return <div className="flex flex-col gap-3 p-4"><Skeleton className="h-16 w-full" /><Skeleton className="h-40 w-full" /></div>;

  return (
    <main className="flex flex-col gap-5 px-4 pb-32 pt-4">
      <h1 className="text-xl font-semibold">{t("title")}</h1>
      <div className="rounded-xl bg-muted p-3 text-sm">
        <div className="font-medium">{q.bundle_title}</div>
        <div className="flex justify-between"><span>{t("total")}</span><span className="font-semibold">{q.monthly_total_display}</span></div>
        {q.one_time_paise > 0 && <div className="flex justify-between"><span>{t("setupTotal")}</span><span>{q.one_time_total_display}</span></div>}
      </div>

      <Field label={t("phone")}>
        <div className="flex gap-2">
          <Input inputMode="numeric" autoComplete="tel-national" maxLength={10} value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))} className="h-11 flex-1 text-base" />
          <Button type="button" variant="outline" className="h-11" disabled={!phoneOk} onClick={onOtp}>{otpSent ? t("otpSent") : t("sendOtp")}</Button>
        </div>
      </Field>
      {otpSent && (
        <Field label={t("otp")} hint={t("otpHint")}>
          <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} className="h-11 text-base tracking-widest" />
        </Field>
      )}
      <Field label={t("businessName")}><Input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoComplete="organization" className="h-11 text-base" /></Field>
      <Field label={t("address")}><Input value={address} onChange={(e) => setAddress(e.target.value)} maxLength={300} autoComplete="street-address" className="h-11 text-base" /></Field>
      <Field label={t("pincode")}><Input inputMode="numeric" maxLength={6} value={pincode} onChange={(e) => setPincode(e.target.value.replace(/\D/g, ""))} autoComplete="postal-code" className="h-11 text-base" /></Field>
      <Field label={t("slotDate")}><Input type="date" value={date} min={minD} max={maxD} onChange={(e) => setDate(e.target.value)} className="h-11 text-base" /></Field>

      <Choice legend={t("slotWindow")} value={win} onChange={(v) => setWin(v as "morning" | "evening")} options={[["morning", t("morning")], ["evening", t("evening")]]} />
      <Choice legend={t("payment")} value={pay} onChange={(v) => setPay(v as "pay_on_activation" | "upi_mock")} options={[["pay_on_activation", t("pay_on_activation")], ["upi_mock", t("upi_mock")]]} />
      <p className="text-xs text-muted-foreground">{t("consentNote")}</p>

      <div className="fixed inset-x-0 bottom-0 border-t bg-background p-4">
        <div className="mx-auto max-w-md">
          <Button className="h-12 w-full text-base" disabled={!valid || busy} onClick={submit}>{busy ? t("placing") : t("place")}</Button>
        </div>
      </div>
    </main>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-medium">
      {label}
      {children}
      {hint && <span className="text-xs font-normal text-muted-foreground">{hint}</span>}
    </label>
  );
}

function Choice({ legend, value, onChange, options }: { legend: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{legend}</legend>
      {options.map(([v, label]) => (
        <label key={v} className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-3 text-base ${value === v ? "border-primary bg-primary/5" : ""}`}>
          <input type="radio" name={legend} value={v} checked={value === v} onChange={() => onChange(v)} className="size-4 accent-[var(--primary)]" />
          {label}
        </label>
      ))}
    </fieldset>
  );
}
