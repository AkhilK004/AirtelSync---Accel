"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2, ChevronDown, FileUp, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  type CheckView, type KycView, type LookupResult, type Notice,
  evaluateKyc, getConsents, getKyc, getNotice, grantConsent, lookupGstin, lookupUdyam, setKycPath, uploadDoc,
} from "@/lib/api";
import { useApiError } from "@/lib/use-api-error";

type Step = "loading" | "consent" | "registration" | "documents" | "result";

function Icon({ s }: { s: CheckView["status"] }) {
  if (s === "PASS") return <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-green-600" aria-label="ok" />;
  if (s === "WARN") return <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-500" aria-label="warning" />;
  return <XCircle className="mt-0.5 size-5 shrink-0 text-red-600" aria-label="problem" />;
}

function CheckRow({ c }: { c: CheckView }) {
  return (
    <li className="flex gap-2">
      <Icon s={c.status} />
      <div className="text-sm">
        <div className="font-medium">{c.label}</div>
        {c.status !== "PASS" && <div className="text-muted-foreground">{c.message}</div>}
        {c.fix && c.status === "FAIL" && <div className="mt-0.5 font-medium text-primary">{c.fix}</div>}
      </div>
    </li>
  );
}

export function KycFlow({ orderId }: { orderId: string }) {
  const t = useTranslations("kyc");
  const locale = useLocale();
  const errText = useApiError();
  const [step, setStep] = useState<Step>("loading");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [ticks, setTicks] = useState<Record<string, boolean>>({});
  const [showFull, setShowFull] = useState(false);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<KycView | null>(null);
  const [hasGstin, setHasGstin] = useState<boolean | null>(null);
  const [idNumber, setIdNumber] = useState("");
  const [lookup, setLookup] = useState<LookupResult | null>(null);
  const [slotResults, setSlotResults] = useState<Record<string, CheckView[]>>({});
  const [slotBusy, setSlotBusy] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([getNotice(locale), getConsents(orderId), getKyc(orderId, locale)])
      .then(([n, c, v]) => {
        if (!alive) return;
        setNotice(n);
        setView(v);
        if (!c.effective.includes("kyc_verification")) setStep("consent");
        else if (v.decision) setStep("result");
        else setStep(v.uploaded.length > 0 ? "documents" : "registration");
      })
      .catch((e) => toast.error(errText(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId, locale]);

  async function agree() {
    if (!notice) return;
    setBusy(true);
    try {
      const granted = notice.purposes.filter((p) => ticks[p.id]).map((p) => p.id);
      await grantConsent(orderId, granted, locale);
      setStep("registration");
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function doLookup() {
    setBusy(true);
    try {
      const r = hasGstin ? await lookupGstin(orderId, idNumber, locale) : await lookupUdyam(orderId, idNumber, locale);
      setLookup(r);
      if (!hasGstin && r.record) await setKycPath(orderId, "udyam", locale);
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function goDocuments() {
    try {
      setView(await getKyc(orderId, locale));
      setStep("documents");
    } catch (e) {
      toast.error(errText(e));
    }
  }

  async function onFile(slot: string, file: File | undefined) {
    if (!file) return;
    setSlotBusy(slot);
    try {
      const r = await uploadDoc(orderId, slot, file, locale);
      setSlotResults((m) => ({ ...m, [slot]: r.checks }));
      setView(await getKyc(orderId, locale));
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setSlotBusy(null);
    }
  }

  async function check() {
    setBusy(true);
    try {
      setView(await evaluateKyc(orderId, locale));
      setStep("result");
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  }

  if (step === "loading" || !notice)
    return <div className="flex flex-col gap-3 p-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-40 w-full" /></div>;

  const stepNo = { consent: 1, registration: 2, documents: 3, result: 4, loading: 1 }[step];
  const required = view?.required ?? [];
  const slots = required;
  const allDone = required.every((s) => view?.uploaded.includes(s));
  const requiredOk = notice.purposes.filter((p) => p.required).every((p) => ticks[p.id]);

  return (
    <main className="flex flex-col gap-5 px-4 pb-32 pt-4">
      <div>
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <ol className="mt-2 flex gap-1" aria-label="steps">
          {(["step1", "step2", "step3", "step4"] as const).map((k, i) => (
            <li key={k} className={`h-1.5 flex-1 rounded-full ${i < stepNo ? "bg-primary" : "bg-muted"}`} title={t(k)} />
          ))}
        </ol>
        <div className="mt-1 text-xs text-muted-foreground">{stepNo}/4 · {t(`step${stepNo}` as "step1")}</div>
      </div>

      {step === "consent" && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">{notice.title}</h2>
          <dl className="flex flex-col gap-3 rounded-lg border bg-card p-4">
            {notice.summary.map((s) => {
              const i = s.indexOf(":"); // each line reads "Label: text"; show the label as a heading so the notice can be skimmed
              return (
                <div key={s}>
                  {i > 0 && i < 40 ? (
                    <>
                      <dt className="font-semibold text-primary">{s.slice(0, i)}</dt>
                      <dd className="text-[0.95rem]">{s.slice(i + 1).trim()}</dd>
                    </>
                  ) : (
                    <dd className="text-[0.95rem]">{s}</dd>
                  )}
                </div>
              );
            })}
          </dl>
          <button className="flex items-center gap-1 text-sm text-primary underline underline-offset-2" onClick={() => setShowFull(!showFull)} aria-expanded={showFull}>
            {t("readFull")} <ChevronDown className={`size-4 transition-transform ${showFull ? "rotate-180" : ""}`} />
          </button>
          {showFull && <p className="rounded-lg bg-muted p-3 text-sm">{notice.full}</p>}
          <div className="flex flex-col gap-2">
            {notice.purposes.map((p) => (
              <label key={p.id} className="flex items-center gap-3 rounded-xl border p-3">
                <span className="flex-1 text-sm">
                  {p.label}
                  <Badge variant={p.required ? "secondary" : "outline"} className="ml-2 align-middle">{p.required ? t("required") : t("optional")}</Badge>
                </span>
                <Switch checked={!!ticks[p.id]} onCheckedChange={(v) => setTicks((m) => ({ ...m, [p.id]: v }))} className="scale-125" aria-label={p.label} />
              </label>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t("version")}: {notice.version}</p>
          {!requiredOk && <p className="rounded-md border border-action bg-action/15 px-3 py-2 text-sm" role="status">{t("mustTick")}</p>}
          <FixedBar><Button className="h-12 w-full text-base" disabled={!requiredOk || busy} onClick={agree}>{t("agree")}</Button></FixedBar>
        </section>
      )}

      {step === "registration" && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">{t("haveGstin")}</h2>
          <div className="flex flex-col gap-2">
            <Button variant={hasGstin === true ? "default" : "outline"} className="h-12 justify-start text-base" onClick={() => { setHasGstin(true); setLookup(null); setIdNumber(""); }}>{t("yes")}</Button>
            <Button variant={hasGstin === false ? "default" : "outline"} className="h-12 justify-start text-base" onClick={() => { setHasGstin(false); setLookup(null); setIdNumber(""); }}>{t("no")}</Button>
            <Button variant="outline" className="h-12 justify-start text-base" disabled>{t("panSoon")}</Button>
          </div>
          {hasGstin !== null && (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1.5 text-sm font-medium">
                {hasGstin ? t("gstinLabel") : t("udyamLabel")}
                <Input value={idNumber} onChange={(e) => setIdNumber(e.target.value.toUpperCase())} maxLength={hasGstin ? 15 : 24} autoCapitalize="characters"
                  className="h-11 text-base tracking-wide" placeholder={hasGstin ? "27AAAXX1234A1ZX" : "UDYAM-MH-00-1234567"} />
                <span className="text-xs font-normal text-muted-foreground">{hasGstin ? t("gstinHint") : t("udyamHint")}</span>
              </label>
              <Button className="h-11" disabled={busy || idNumber.length < 5} onClick={doLookup}>{busy ? t("looking") : t("lookup")}</Button>
            </div>
          )}
          {lookup && (
            <div className="flex flex-col gap-3 rounded-xl border p-3">
              <ul className="flex flex-col gap-2">{lookup.checks.map((c) => <CheckRow key={c.code} c={c} />)}</ul>
              {lookup.record && (
                <dl className="flex flex-col gap-1 border-t pt-2 text-sm">
                  {(lookup.record.legal_name ?? lookup.record.enterprise_name) && <div><dt className="text-muted-foreground">{t("legalName")}</dt><dd className="font-medium">{lookup.record.legal_name ?? lookup.record.enterprise_name}</dd></div>}
                  {lookup.record.address && <div><dt className="text-muted-foreground">{t("address")}</dt><dd>{lookup.record.address}</dd></div>}
                  {lookup.record.status && <div className="flex items-center gap-2"><dt className="text-muted-foreground">{t("status")}</dt><dd><Badge variant={lookup.record.status === "Active" ? "secondary" : "destructive"}>{lookup.record.status}</Badge></dd></div>}
                </dl>
              )}
            </div>
          )}
          <FixedBar><Button className="h-12 w-full text-base" disabled={!lookup?.record} onClick={goDocuments}>{t("continue")}</Button></FixedBar>
        </section>
      )}

      {step === "documents" && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">{t("docsTitle")}</h2>
          <p className="text-sm text-muted-foreground">{t("docsHint")}</p>
          {slots.map((slot) => (
            <SlotCard key={slot} slot={slot} optional={!required.includes(slot)} busy={slotBusy === slot} uploaded={!!view?.uploaded.includes(slot)}
              results={slotResults[slot]} onFile={(f) => onFile(slot, f)} />
          ))}
          <p className="text-xs text-muted-foreground">{t("retention")}</p>
          <FixedBar><Button className="h-12 w-full text-base" disabled={!allDone || busy || slotBusy !== null} onClick={check}>{busy ? t("checking") : t("check")}</Button></FixedBar>
        </section>
      )}

      {step === "result" && view?.decision && (
        <section className="flex flex-col gap-4">
          <div className={`rounded-xl p-4 text-base font-medium ${{ APPROVED: "bg-green-50 text-green-900", ACTION_REQUIRED: "bg-amber-50 text-amber-900", MANUAL_REVIEW: "bg-blue-50 text-blue-900", REJECTED: "bg-red-50 text-red-900" }[view.decision.status]}`} role="status">
            {view.decision.message}
          </div>
          <h2 className="text-lg font-semibold">{t("resultTitle")}</h2>
          <ul className="flex flex-col gap-3">{view.checks.filter((c) => c.status !== "PASS").map((c, i) => <CheckRow key={c.code + i} c={c} />)}</ul>
          <details className="rounded-xl border p-3">
            <summary className="cursor-pointer text-sm font-medium">{t("passed", { n: view.checks.filter((c) => c.status === "PASS").length })}</summary>
            <ul className="mt-3 flex flex-col gap-3">{view.checks.filter((c) => c.status === "PASS").map((c, i) => <CheckRow key={c.code + i} c={c} />)}</ul>
          </details>
          {view.decision.status === "ACTION_REQUIRED" && (
            <>
              <p className="text-sm text-muted-foreground">{t("reupload")}</p>
              <FixedBar><Button className="h-12 w-full text-base" onClick={() => setStep("documents")}>{t("fixRetry")}</Button></FixedBar>
            </>
          )}
          {view.decision.status !== "ACTION_REQUIRED" && view.decision.status !== "REJECTED" && (
            <FixedBar><Link href={`/${locale}/track/${orderId}`} className={`${buttonVariants({ size: "lg" })} h-12 w-full text-base`}>{t("track")}</Link></FixedBar>
          )}
        </section>
      )}
    </main>
  );
}

function FixedBar({ children }: { children: React.ReactNode }) {
  return <div className="fixed inset-x-0 bottom-0 border-t bg-background p-4"><div className="mx-auto max-w-md">{children}</div></div>;
}

function SlotCard({ slot, optional, busy, uploaded, results, onFile }: {
  slot: string; optional: boolean; busy: boolean; uploaded: boolean; results?: CheckView[]; onFile: (f: File | undefined) => void;
}) {
  const t = useTranslations("kyc");
  const ref = useRef<HTMLInputElement>(null);
  const failed = results?.some((r) => r.status === "FAIL");
  return (
    <div className={`rounded-xl border p-3 ${failed ? "border-red-300" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="font-medium">{t(`slot_${slot}` as "slot_gst_certificate")} {optional && <Badge variant="outline" className="ml-1">{t("optional")}</Badge>}</div>
        {uploaded && !failed && <CheckCircle2 className="size-5 text-green-600" aria-label={t("readOk")} />}
      </div>
      <input ref={ref} type="file" accept="image/png,image/jpeg,application/pdf" capture="environment" className="sr-only" data-slot={slot}
        onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      <button type="button" onClick={() => ref.current?.click()} disabled={busy}
        className="mt-2 flex h-14 w-full items-center justify-center gap-2 rounded-lg border border-dashed text-sm active:bg-muted disabled:opacity-50">
        <FileUp className="size-5" /> {busy ? t("uploading") : uploaded ? t("replace") : t("tap")}
      </button>
      {results && <ul className="mt-3 flex flex-col gap-2">{results.filter((r) => r.status !== "PASS").map((c, i) => <CheckRow key={c.code + i} c={c} />)}</ul>}
    </div>
  );
}
