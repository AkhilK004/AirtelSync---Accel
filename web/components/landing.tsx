"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { localeNames, locales } from "@/lib/i18n";

export function Landing() {
  const t = useTranslations("landing");
  const c = useTranslations("common");
  const locale = useLocale();
  const params = useSearchParams();

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

  return (
    <main className="flex flex-col gap-6 px-4 pb-28 pt-8">
      <h1 className="text-3xl font-bold leading-tight tracking-tight">{t("title")}</h1>
      <p className="text-base text-muted-foreground">{t("subtitle")}</p>
      <ul className="flex flex-col gap-3">
        {(["b1", "b2", "b3"] as const).map((k) => (
          <li key={k} className="flex gap-3 text-base">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
            <span>{t(k)}</span>
          </li>
        ))}
      </ul>
      <div className="flex flex-col gap-2">
        <span className="text-sm text-muted-foreground">{t("chooseLanguage")}</span>
        <div className="flex gap-2">
          {locales.map((l) => (
            <Link
              key={l}
              href={`/${l}`}
              className={`inline-flex h-11 flex-1 items-center justify-center rounded-lg border text-base ${
                l === locale ? "border-primary bg-primary/10 font-medium" : ""
              }`}
            >
              {localeNames[l]}
            </Link>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{c("demo")}</p>
      <div className="fixed inset-x-0 bottom-0 border-t bg-background p-4">
        <div className="mx-auto max-w-md">
          <Link href={`/${locale}/advisor`} className={`${buttonVariants({ size: "lg" })} h-12 w-full text-base`}>
            {t("cta")}
          </Link>
        </div>
      </div>
    </main>
  );
}
