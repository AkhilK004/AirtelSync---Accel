"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ALargeSmall } from "lucide-react";
import { localeNames, locales } from "@/lib/i18n";

const LARGE = "118%";

export function SiteHeader() {
  const locale = useLocale();
  const t = useTranslations("common");
  const pathname = usePathname() ?? `/${locale}`;
  const rest = pathname.split("/").slice(2).join("/");
  const [large, setLarge] = useState(false);

  // "Larger text" is remembered per browser; it scales every rem-based size on the page.
  useEffect(() => {
    try {
      if (localStorage.getItem("udyam-large-text") === "1") {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- read after mount so server and client markup match
        setLarge(true);
        document.documentElement.style.fontSize = LARGE;
      }
    } catch {
      /* storage blocked */
    }
  }, []);
  function toggleLarge() {
    const next = !large;
    setLarge(next);
    document.documentElement.style.fontSize = next ? LARGE : "";
    try {
      localStorage.setItem("udyam-large-text", next ? "1" : "0");
    } catch {
      /* storage blocked */
    }
  }

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-md items-center justify-between gap-2 px-4">
        <Link href={`/${locale}`} className="flex flex-col leading-none">
          <span className="text-lg font-bold tracking-tight text-primary">Accel</span>{" "}
          <span className="mt-0.5 flex items-center gap-1.5 text-[0.8rem] text-muted-foreground">
            <span className="h-[3px] w-5 rounded-full bg-action" aria-hidden />
            Business
          </span>
        </Link>
        <div className="flex items-center gap-1.5">
          <nav aria-label={t("language")} className="flex rounded-full bg-muted p-0.5">
            {locales.map((l) => (
              <Link
                key={l}
                href={`/${l}${rest ? `/${rest}` : ""}`}
                hrefLang={l}
                lang={l}
                aria-current={l === locale ? "true" : undefined}
                className={`inline-flex h-10 min-w-11 items-center justify-center rounded-full px-3 text-sm font-medium ${
                  l === locale ? "bg-primary text-primary-foreground" : "text-foreground"
                }`}
              >
                {localeNames[l]}
              </Link>
            ))}
          </nav>
          <button
            type="button"
            onClick={toggleLarge}
            aria-pressed={large}
            aria-label={large ? t("normalText") : t("largerText")}
            title={large ? t("normalText") : t("largerText")}
            className={`inline-flex size-11 items-center justify-center rounded-full ${large ? "bg-action text-action-foreground" : "bg-muted text-foreground"}`}
          >
            <ALargeSmall className="size-5" aria-hidden />
          </button>
        </div>
      </div>
    </header>
  );
}
