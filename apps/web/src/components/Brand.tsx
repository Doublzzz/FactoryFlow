import { t } from "../i18n";
export function Brand() {
  return <div className="product-brand"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 28 28" fill="none"><path d="M5 6h18v16H5V6Z M9 11h10 M9 16h6 M19 16v6" stroke="currentColor" strokeWidth="2" strokeLinecap="square" /></svg></span><div><strong>{t("交有数")}</strong><span>{t("工厂订单与送货管理")}</span></div></div>;
}

export function NavIcon({ name }: { name: "orders" | "sources" | "deliveries" | "customers" | "statements" | "archives" }) {
  const paths = {
    orders: "M5 3h14v18H5V3M9 8h6M9 12h6M9 16h4",
    sources: "M12 16V3m-4 4 4-4 4 4M4 15v6h16v-6",
    deliveries: "M3 6h11v12H3V6m11 4h4l3 4v4h-7M8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0m12 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0",
    statements: "M4 3h16v18H4V3M8 8h8M8 12h3m3 0h2M8 16h3m3 0h2",
    archives: "M3 7h18v14H3V7M3 7V3h7l3 4M8 12h8M8 16h5",
    customers: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-3a8 8 0 0 1 16 0v3",
  };
  return <svg className="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={paths[name]} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
