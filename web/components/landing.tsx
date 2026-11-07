"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Landing() {
  const t = useTranslations("landing");
  const c = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // capture ?partner=CODE for attribution (passed to the advisor session)
  useEffect(() => {
    const p = params.get("partner");
    if (p) {
      try {
        sessionStorage.setItem("partner", p.slice(0, 40));
      } catch {
        /* storage blocked */
      }
    }
  }, [params]);

  // The first sentence typed here becomes the advisor's first message, so the owner starts the conversation on this screen.
  function start(e: React.FormEvent) {
    e.preventDefault();
    const v = text.trim();
    if (v) {
      try {
        sessionStorage.setItem("firstMessage", v.slice(0, 500));
      } catch {
        /* storage blocked */
      }
    }
    router.push(`/${locale}/advisor`);
  }

  return (
    <main className="flex flex-col gap-7 px-4 pb-10 pt-8">
      <div className="flex flex-col gap-3">
        <h1 className="font-display text-[2.1rem] leading-[1.2] text-primary">{t("title")}</h1>
        <p className="text-base text-muted-foreground">{t("subtitle")}</p>
      </div>

      <form onSubmit={start} className="flex flex-col gap-3 rounded-lg border bg-card p-4 shadow-[0_1px_0_var(--border)]">
        <label htmlFor="biz" className="text-base font-semibold">
          {t("askLabel")}
        </label>
        <input
          id="biz"
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("askPlaceholder")}
          maxLength={500}
          autoComplete="off"
          enterKeyHint="go"
          className="h-12 w-full rounded-md border-2 border-input bg-background px-3 text-base placeholder:text-muted-foreground focus-visible:border-primary"
        />
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("askLabel")}>
          {(["ex1", "ex2", "ex3"] as const).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => {
                setText(t(k));
                inputRef.current?.focus();
              }}
              className="min-h-11 rounded-full border border-input bg-background px-3.5 py-1.5 text-left text-sm text-primary active:bg-secondary"
            >
              {t(k)}
            </button>
          ))}
        </div>
        <Button type="submit" className="mt-1 h-12 w-full text-base">
          {t("cta")}
        </Button>
        <Link href={`/${locale}/advisor`} className="inline-flex min-h-11 items-center justify-center text-sm text-primary underline underline-offset-4">
          {t("stepByStep")}
        </Link>
      </form>

      <ul className="flex flex-col gap-3">
        {(["b1", "b2", "b3"] as const).map((k) => (
          <li key={k} className="flex gap-3 text-base">
            <CheckCircle2 className="mt-1 size-5 shrink-0 text-success" aria-hidden />
            <span>{t(k)}</span>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">{t("trust")}</p>
      <p className="text-xs text-muted-foreground">{c("demo")}</p>
    </main>
  );
}
