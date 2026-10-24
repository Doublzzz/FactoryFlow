import { getLocale, t } from "./i18n";

// Display labels only. Persisted units and quantities remain unchanged.
const labels: Record<string, string> = { PCS: "件", KG: "千克", M: "米", MM: "毫米", SET: "套" };
export function displayUnit(value: string | null | undefined): string {
  if (!value) return t("未填写");
  const canonical = value.toUpperCase();
  return labels[canonical] ? getLocale() === "en" ? canonical : labels[canonical]! : value;
}

export function isZeroQuantity(value: string): boolean {
  return /^0+(?:\.0+)?$/.test(value);
}

// Only a local typo check; the server still enforces the actual available quantity.
export function quantityExceeds(value: string, available: string): boolean {
  const valid = /^\d+(?:\.\d{1,3})?$/;
  if (!valid.test(value) || !valid.test(available)) return false;
  const scaled = (text: string) => { const [whole = "0", fraction = ""] = text.split("."); return BigInt(whole) * 1000n + BigInt(fraction.padEnd(3, "0")); };
  return scaled(value) > scaled(available);
}

// Display share of a delivered quantity, as a whole percentage for a progress bar.
// Exact decimal strings are compared as scaled integers; no binary floating point is used.
export function deliveredShare(delivered: string, quantity: string): number | null {
  const valid = /^\d+(?:\.\d+)?$/;
  if (!valid.test(delivered) || !valid.test(quantity)) return null;
  const places = Math.max(delivered.split(".")[1]?.length ?? 0, quantity.split(".")[1]?.length ?? 0);
  const scaled = (text: string) => { const [whole = "0", fraction = ""] = text.split("."); return BigInt(whole) * 10n ** BigInt(places) + BigInt(fraction.padEnd(places, "0") || "0"); };
  const total = scaled(quantity);
  if (total === 0n) return null;
  const share = scaled(delivered) * 100n / total;
  return Number(share > 100n ? 100n : share);
}
