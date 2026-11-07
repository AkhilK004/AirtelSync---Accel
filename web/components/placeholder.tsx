"use client";

import { useTranslations } from "next-intl";

/** Phase 5 (KYC) and Phase 6 (tracker) replace these screens. */
export function Placeholder({ titleKey, orderId }: { titleKey: "kycTitle" | "trackTitle"; orderId: string }) {
  const t = useTranslations("next");
  return (
    <main className="flex flex-col gap-2 p-4">
      <h1 className="text-xl font-semibold">{t(titleKey)}</h1>
      <p className="text-sm text-muted-foreground">
        {t("order")} {orderId.slice(-6).toUpperCase()}
      </p>
      <p>{t("soon")}</p>
    </main>
  );
}
