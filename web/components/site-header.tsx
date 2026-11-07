"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { localeNames, locales } from "@/lib/i18n";

export function SiteHeader() {
  const locale = useLocale();
  const t = useTranslations("common");
  const pathname = usePathname() ?? `/${locale}`;
  const rest = pathname.split("/").slice(2).join("/");
  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-md items-center justify-between px-4">
        <Link href={`/${locale}`} className="text-base font-semibold tracking-tight">
          {t("brand")}
        </Link>
        <nav aria-label={t("language")} className="flex gap-1">
          {locales.map((l) => (
            <Link
              key={l}
              href={`/${l}${rest ? `/${rest}` : ""}`}
              hrefLang={l}
              aria-current={l === locale ? "true" : undefined}
              className={`inline-flex h-9 min-w-11 items-center justify-center rounded-full px-3 text-sm ${
                l === locale ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
              }`}
            >
              {localeNames[l]}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
