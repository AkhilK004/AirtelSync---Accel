export const locales = ["en", "hi", "mr"] as const;
export type Locale = (typeof locales)[number];
export const localeNames: Record<Locale, string> = { en: "English", hi: "हिन्दी", mr: "मराठी" };
export const isLocale = (l: string): l is Locale => (locales as readonly string[]).includes(l);
