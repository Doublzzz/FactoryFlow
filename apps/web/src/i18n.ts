import { english } from "./messages.en";

export type Locale = "zh-CN" | "en";
export type UiMessage = string | { key: string; values: readonly UiValue[] };
type UiValue = UiMessage | number | null | undefined;
const storageKey = "factoryflow.locale";
function savedLocale(): Locale {
  const requested = new URLSearchParams(globalThis.location?.search ?? "").get("lang");
  if (requested === "en" || requested === "zh-CN") return requested;
  try { return globalThis.localStorage?.getItem(storageKey) === "en" ? "en" : "zh-CN"; }
  catch { return "zh-CN"; }
}
let locale = savedLocale();
const listeners = new Set<() => void>();
export const getLocale = (): Locale => locale;
export function subscribeLocale(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function setLocale(value: Locale): void {
  if (value !== "zh-CN" && value !== "en") throw new Error("Unsupported locale");
  if (value === locale) return;
  locale = value;
  try { globalThis.localStorage?.setItem(storageKey, value); } catch { /* The current tab still works without storage. */ }
  if (globalThis.location?.search.includes("lang=")) {
    const url = new URL(globalThis.location.href);
    url.searchParams.set("lang", value);
    try { globalThis.history?.replaceState(null, "", url); } catch { /* Keep in-memory choice. */ }
  }
  for (const listener of listeners) listener();
}

// Keep notifications as a key plus values so an existing message follows a language change.
export const msg = (key: string, values: readonly UiValue[] = []): UiMessage => ({ key, values });
export function t(message: UiMessage, values: readonly UiValue[] = []): string {
  const key = typeof message === "string" ? message : message.key;
  const parameters = typeof message === "string" ? values : message.values;
  const pattern = locale === "en" ? english[key] ?? key : key;
  return pattern.replace(/\{(\d+)\}/g, (placeholder, index: string) => {
    const value = parameters[Number(index)];
    if (value === undefined) return placeholder;
    // Raw values are business data. Only an explicit message object is translated.
    return value && typeof value === "object" ? t(value) : String(value ?? "");
  });
}

export const outputLanguage = (value: Locale | "source"): string => value === "source" ? t("模板原文") : value === "en" ? t("英文") : t("中文");
