"use client";

import { useTranslations } from "next-intl";
import { ApiError } from "@/lib/api";

/** Translates an API error code (PLAN 6.4) into the user's language. */
export function useApiError() {
  const t = useTranslations("errors");
  return (e: unknown): string => {
    const code = e instanceof ApiError ? e.code : "GENERIC";
    const params = (e instanceof ApiError ? e.params : {}) as Record<string, string | number>;
    return t.has(code) ? t(code, params) : t("GENERIC");
  };
}
