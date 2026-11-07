"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, SendHorizonal } from "lucide-react";
import { toast } from "sonner";
import { HandoffDialog } from "@/components/handoff-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
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
    let first: string | null = null;
    try {
      partner = sessionStorage.getItem("partner");
      first = sessionStorage.getItem("firstMessage"); // typed on the landing screen
      sessionStorage.removeItem("firstMessage");
    } catch {
      /* storage blocked */
    }
    startAdvisor(locale, partner)
      .then(async (r) => {
        apply(r);
        if (first) {
          setMsgs((m) => [...m, { id: ++idRef.current, role: "user", text: first }]);
          setChips([]);
          apply(await sendAdvisor(r.session_id, first));
        }
      })
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

  function toggle(id: number) {
    setExpanded((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  const shownChips = quoteId ? chips.filter((c) => c.value !== "see price") : chips; // the plan card already has the price button
  const dots = Array.from({ length: progress.total }, (_, i) => i < progress.asked);
  return (
    <main className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <h1 className="sr-only">{t("heading")}</h1>
      <div className="px-4 pb-2 pt-3">
        <div className="mb-2 flex items-center justify-between text-sm text-muted-foreground">
          <span>{t("answered", { asked: progress.asked, total: progress.total })}</span>
          <button className="min-h-11 px-1 text-primary underline underline-offset-4" onClick={() => setHandoffOpen(true)} disabled={!sid}>
            {t("talk")}
          </button>
        </div>
        <div className="flex gap-1.5" role="progressbar" aria-valuenow={progress.asked} aria-valuemin={0} aria-valuemax={progress.total} aria-label={t("answered", { asked: progress.asked, total: progress.total })}>
          {dots.map((done, i) => (
            <span key={i} className={`h-1.5 flex-1 rounded-full ${done ? "bg-primary" : "bg-border"}`} />
          ))}
        </div>
      </div>

      <div role="log" aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-2">
        {msgs.map((m) => {
          const lines = m.text.split("\n");
          const short = m.rec ? lines[0] : m.text;
          const more = m.rec ? lines.slice(1).join("\n").trim() : "";
          const open = expanded.has(m.id);
          return (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className="flex max-w-[90%] flex-col gap-2">
                <div
                  className={`whitespace-pre-line px-4 py-2.5 text-[1.0rem] leading-relaxed ${
                    m.role === "user"
                      ? "rounded-2xl rounded-br-sm bg-primary text-primary-foreground"
                      : "rounded-2xl rounded-bl-sm border bg-card"
                  }`}
                >
                  {short}
                  {open && more ? "\n" + more : ""}
                  {more && (
                    <button
                      type="button"
                      onClick={() => toggle(m.id)}
                      aria-expanded={open}
                      className="mt-1 flex min-h-11 items-center gap-1 text-sm font-medium text-primary underline underline-offset-4"
                    >
                      {open ? t("hideDetails") : t("details")}
                      <ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
                    </button>
                  )}
                </div>
                {m.rec && (
                  <div className="slip px-4 pt-4">
                    <div className="text-sm text-muted-foreground">{t("planReady")}</div>
                    <div className="font-display text-2xl leading-tight text-primary">{m.rec.bundle_name}</div>
                    <hr className="slip-rule my-3" />
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm text-muted-foreground">{t("perMonth")}</span>
                      <span className="font-display tabular text-3xl text-primary">{m.rec.monthly_total_display}</span>
                    </div>
                    {m.rec.assisted && (
                      <div className="mt-3 flex flex-col gap-2 rounded-md bg-muted p-3 text-sm">
                        {t("expertCalls")}
                        <Button variant="outline" className="h-11" onClick={() => setHandoffOpen(true)}>
                          {t("shareNumber")}
                        </Button>
                      </div>
                    )}
                    <Button className="mb-1 mt-4 h-12 w-full text-base" onClick={goQuote}>
                      {t("seePrice")}
                    </Button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {busy && (
          <div className="flex justify-start" role="status">
            <span className="sr-only">{t("typing")}</span>
            <div className="flex gap-1.5 rounded-2xl rounded-bl-sm border bg-card px-4 py-3.5" aria-hidden>
              <span className="typing-dot size-2 rounded-full bg-primary" />
              <span className="typing-dot size-2 rounded-full bg-primary" />
              <span className="typing-dot size-2 rounded-full bg-primary" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t bg-card px-4 pb-4 pt-3">
        {shownChips.length > 0 && (
          <div className="mb-3 flex max-h-32 flex-wrap gap-2 overflow-y-auto">
            {shownChips.map((c) => (
              <button
                key={c.value + c.label}
                onClick={() => send(c.value, c.label)}
                disabled={busy}
                className="min-h-11 rounded-full border border-input bg-background px-4 py-1.5 text-left text-[0.95rem] font-medium text-primary active:bg-secondary disabled:opacity-50"
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
            className="h-12 flex-1 border-2 border-input text-base"
            aria-label={t("placeholder")}
            enterKeyHint="send"
          />
          <Button type="submit" size="icon-lg" className="size-12" disabled={busy || !text.trim()} aria-label={t("send")}>
            <SendHorizonal />
          </Button>
        </form>
      </div>
      {sid && <HandoffDialog sessionId={sid} open={handoffOpen} onOpenChange={setHandoffOpen} />}
    </main>
  );
}
