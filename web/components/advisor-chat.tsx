"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { SendHorizonal } from "lucide-react";
import { toast } from "sonner";
import { HandoffDialog } from "@/components/handoff-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { type AdvisorReply, type QuickReply, type RecSummary, sendAdvisor, startAdvisor } from "@/lib/api";
import { useApiError } from "@/lib/use-api-error";

type Msg = { id: number; role: "bot" | "user"; text: string; rec?: RecSummary | null };

export function AdvisorChat() {
  const t = useTranslations("advisor");
  const locale = useLocale();
  const router = useRouter();
  const errText = useApiError();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [chips, setChips] = useState<QuickReply[]>([]);
  const [progress, setProgress] = useState({ asked: 0, total: 6 });
  const [sid, setSid] = useState<string | null>(null);
  const [quoteId, setQuoteId] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [text, setText] = useState("");
  const [handoffOpen, setHandoffOpen] = useState(false);
  const started = useRef(false);
  const idRef = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  const apply = useCallback((r: AdvisorReply) => {
    setSid(r.session_id);
    setChips(r.quick_replies);
    setProgress(r.progress);
    if (r.quote_id) setQuoteId(r.quote_id);
    setMsgs((m) => [...m, { id: ++idRef.current, role: "bot", text: r.message, rec: r.recommendation }]);
    if (r.action === "HANDOFF") setHandoffOpen(true);
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let partner: string | null = null;
    try {
      partner = sessionStorage.getItem("partner");
    } catch {
      /* storage blocked */
    }
    startAdvisor(locale, partner)
      .then(apply)
      .catch(() => toast.error(t("startError")))
      .finally(() => setBusy(false));
  }, [apply, locale, t]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  const goQuote = useCallback(() => quoteId && router.push(`/${locale}/quote/${quoteId}`), [quoteId, router, locale]);

  async function send(value: string, label?: string) {
    if (!sid || busy || !value.trim()) return;
    if (value === "see price" && quoteId) return goQuote();
    setMsgs((m) => [...m, { id: ++idRef.current, role: "user", text: label ?? value }]);
    setText("");
    setChips([]);
    setBusy(true);
    try {
      apply(await sendAdvisor(sid, value));
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  }

  const pct = Math.min(100, Math.round((progress.asked / progress.total) * 100));
  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="px-4 pb-2 pt-3">
        <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>{t("question", { asked: progress.asked, total: progress.total })}</span>
          <button className="underline underline-offset-2" onClick={() => setHandoffOpen(true)} disabled={!sid}>
            {t("talk")}
          </button>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-2" aria-live="polite">
        {msgs.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className="flex max-w-[88%] flex-col gap-2">
              <div
                className={`whitespace-pre-line rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${
                  m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                {m.text}
              </div>
              {m.rec && (
                <div className="rounded-2xl border bg-card p-4 shadow-sm">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("planReady")}</div>
                  <div className="text-lg font-semibold">{m.rec.bundle_name}</div>
                  <div className="mt-1 text-2xl font-bold">{m.rec.monthly_total_display}</div>
                  <div className="text-xs text-muted-foreground">{t("perMonth")}</div>
                  {m.rec.assisted && (
                    <div className="mt-2 flex flex-col gap-2 rounded-lg bg-muted p-2 text-sm">
                      {t("expertCalls")}
                      <Button variant="outline" className="h-10" onClick={() => setHandoffOpen(true)}>
                        {t("shareNumber")}
                      </Button>
                    </div>
                  )}
                  <Button className="mt-3 h-11 w-full text-base" onClick={goQuote}>
                    {t("seePrice")}
                  </Button>
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <Skeleton className="h-10 w-40 rounded-2xl" />
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t bg-background px-4 pb-4 pt-2">
        {chips.length > 0 && (
          <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
            {chips.map((c) => (
              <button
                key={c.value + c.label}
                onClick={() => send(c.value, c.label)}
                disabled={busy}
                className="h-11 shrink-0 rounded-full border bg-background px-4 text-sm active:bg-muted disabled:opacity-50"
              >
                {c.label}
              </button>
            ))}
          </div>
        )}
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
        >
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("placeholder")}
            maxLength={500}
            className="h-11 flex-1 text-base"
            aria-label={t("placeholder")}
          />
          <Button type="submit" size="icon-lg" className="size-11" disabled={busy || !text.trim()} aria-label={t("send")}>
            <SendHorizonal />
          </Button>
        </form>
      </div>
      {sid && <HandoffDialog sessionId={sid} open={handoffOpen} onOpenChange={setHandoffOpen} />}
    </div>
  );
}
