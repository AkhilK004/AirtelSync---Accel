import { getRequestConfig } from "next-intl/server";
import { isLocale } from "@/lib/i18n";

export default getRequestConfig(async ({ requestLocale }) => {
  const asked = await requestLocale;
  const locale = asked && isLocale(asked) ? asked : "en";
  return { locale, messages: (await import(`../messages/${locale}.json`)).default };
});
