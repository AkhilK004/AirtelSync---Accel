import type { Metadata, Viewport } from "next";
import { Mukta, Tiro_Devanagari_Hindi } from "next/font/google";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Toaster } from "@/components/ui/sonner";
import { SiteHeader } from "@/components/site-header";
import { isLocale, locales } from "@/lib/i18n";
import "../globals.css";

// Mukta: UI and body (Devanagari + Latin, designed together). Tiro Devanagari Hindi: print-style serif for headlines and the rupee totals.
const mukta = Mukta({ variable: "--font-mukta", subsets: ["devanagari", "latin"], weight: ["400", "500", "600", "700"], display: "swap" });
const tiro = Tiro_Devanagari_Hindi({ variable: "--font-tiro", subsets: ["devanagari", "latin"], weight: "400", display: "swap" });

export const metadata: Metadata = {
  title: "Accel Business — find your plan",
  description: "Find the right business bundle, see one clear price and get activated. Demo prototype with synthetic data.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#1b2a6b" };

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  const messages = (await import(`../../messages/${locale}.json`)).default;
  return (
    <html lang={locale} className={`${mukta.variable} ${tiro.variable} h-full antialiased`}>
      <body className="min-h-dvh bg-background text-foreground">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-action focus:px-4 focus:py-3 focus:text-action-foreground">
            {messages.common.skip}
          </a>
          <SiteHeader />
          <div id="main" tabIndex={-1} className="mx-auto w-full max-w-md outline-none">{children}</div>
          <Toaster position="top-center" />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
