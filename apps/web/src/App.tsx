import { getLocale, msg, setLocale, subscribeLocale, t, type Locale, type UiMessage } from "./i18n";
import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { api, ApiError, message, setCSRF, type Customer, type OrderDetail as Detail, type Session } from "./api";
import { Production } from "./components/Production";
import { Purchasing } from "./components/Purchasing";
import { Inventory } from "./components/Inventory";
import { Materials } from "./components/Materials";
import { Customers } from "./components/Customers";
import { OrdersList } from "./components/OrdersList";
import { OrderEntry } from "./components/OrderEntry";
import { OrderDetail } from "./components/OrderDetail";
import { DeliveryEntry } from "./components/DeliveryEntry";
import { Deliveries } from "./components/Deliveries";
import { Statements } from "./components/Statements";
import { Sources } from "./components/Sources";
import { Archives } from "./components/Archives";
import type { Extraction } from "./api";
import { Brand, NavIcon } from "./components/Brand";
import { PasswordInput } from "./components/PasswordInput";

type View = { name: "production"; orderId?: string; selected?: string } | { name: "purchasing"; selectedReceipt?: string } | { name: "materials"; initialKind?: "finished" | "raw" } | { name: "delivery-entry"; order: Detail } | { name: "deliveries"; selected?: string | undefined } | { name: "sources"; file?: File | undefined } | { name: "orders" | "customers" | "statements" | "archives" | "inventory" | "raw-inventory" } | { name: "entry"; existing?: Detail; extraction?: Extraction } | { name: "detail"; id: string };
const roleNames = { admin: "管理员", operator: "操作员", viewer: "只读" };

function LanguageSelector({ locale }: { locale: Locale }) {
  return <select className="language-selector" aria-label="Language / 语言" value={locale} onChange={event => setLocale(event.target.value as Locale)}><option value="zh-CN">简体中文</option><option value="en">English</option></select>;
}

export function App() {
  const locale = useSyncExternalStore(subscribeLocale, getLocale);
  useEffect(() => { document.documentElement.lang = locale; document.title = t("交有数 · 工厂订单与送货"); }, [locale]);
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [view, setView] = useState<View>({ name: "orders" });
  const [notice, setNotice] = useState<UiMessage>("");
  const [reauthenticate, setReauthenticate] = useState(false);
  const [navigationBlocked, setNavigationBlocked] = useState(false);
  const [unsavedPurchase, setUnsavedPurchase] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const reauthDialog = useRef<HTMLDialogElement>(null);
  const main = useRef<HTMLElement>(null);

  function acceptSession(value: Session) { setCSRF(value.csrf_token); setSession(value); setPassword(""); setReauthenticate(false); }
  async function checkSession() {
    setChecking(true); setError("");
    try { acceptSession(await api.session()); }
    catch (failure) { if (!(failure instanceof ApiError && failure.status === 401)) setError(message(failure)); }
    finally { setChecking(false); }
  }
  useEffect(() => { void checkSession(); }, []);
  useEffect(() => { const expire = () => { setReauthenticate(true); setPassword(""); }; window.addEventListener("factoryflow:session-expired", expire); return () => window.removeEventListener("factoryflow:session-expired", expire); }, []);
  useEffect(() => { if (reauthenticate && session) reauthDialog.current?.showModal(); else reauthDialog.current?.close(); }, [reauthenticate, session]);
  useEffect(() => { if (session) api.customers().then(setCustomers).catch(failure => setError(message(failure))); }, [session]);
  useEffect(() => { main.current?.focus({ preventScroll: true }); window.scrollTo(0, 0); }, [view, session?.user.id]);

  async function login(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError("");
    try { acceptSession(await api.login(session?.user.username ?? username, password)); }
    catch (failure) { setError(message(failure)); setPassword(""); }
    finally { setBusy(false); }
  }
  async function logout() {
    if (unsavedPurchase && !window.confirm(t("离开后，未保存的采购内容会丢失。确定离开吗？"))) return;
    setBusy(true); setError("");
    try { await api.logout(); setSession(null); setCSRF(""); setCustomers([]); setView({ name: "orders" }); setNotice(""); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  function addCustomer(customer: Customer) {
    setCustomers(previous => [...previous.filter(c => c.id !== customer.id), customer].sort((a, b) => a.full_name.localeCompare(b.full_name, locale)));
    setNotice(msg("客户已创建。"));
  }
  function navigate(next: View) {
    if (unsavedPurchase && !window.confirm(t("离开后，未保存的采购内容会丢失。确定离开吗？"))) return;
    setView(next); setError(""); setNotice(""); setMoreOpen(false);
  }
  const canWrite = session?.user.role !== "viewer";
  const navigationItems = [['orders', t("待交清单"), t("待交")], ['sources', t("收订单"), t("收单")], ['deliveries', t("送货记录"), t("送货")], ['statements', t("客户对账"), t("对账")], ['archives', t("文件整理"), t("文件整理")], ['customers', t("客户"), t("客户")], ['materials', t("物料池"), t("物料池")], ['inventory', t("成品库存"), t("库存")], ['purchasing', t("采购与收料"), t("采购")], ['raw-inventory', t("原料库存"), t("原料")], ['production', t("生产记录"), t("生产")]] as const;
  const navigationButton = ([name, label, short]: typeof navigationItems[number], secondary: boolean) => <button key={name} aria-label={label} className={secondary ? "nav-secondary" : undefined} aria-current={(name === 'orders' ? ['orders', 'entry', 'detail', 'delivery-entry'].includes(view.name) : view.name === name) ? 'page' : undefined} onClick={() => navigate({ name })} disabled={view.name === 'entry' || navigationBlocked}><NavIcon name={(name === "materials" || name === "inventory" || name === "purchasing" || name === "raw-inventory" || name === "production") ? "archives" : name} /><span className="nav-label">{label}</span><span className="nav-short" aria-hidden="true">{short}</span></button>;

  if (!session) return <div className="login-layout"><header className="login-header"><Brand /><LanguageSelector locale={locale} /></header><main className="login-main">
    <section className="login-panel" aria-labelledby="login-title"><h1 id="login-title">{t("登录交有数")}</h1><p className="muted">{t("使用工厂本机设置的账号和密码。")}</p>
      {checking ? <p role="status" className="muted">{t("正在连接本地服务…")}</p> : <form onSubmit={login}>
        <label>{t("账号")}<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required maxLength={100} disabled={busy} /></label>
        <PasswordInput value={password} onChange={setPassword} disabled={busy} />
        <button className="full-width" disabled={busy}>{busy ? t("登录中…") : t("登录")}</button><details className="login-help"><summary>{t("忘记密码？")}</summary><p>{t("忘记管理员密码时，在运行软件的电脑上打开安装文件夹，运行“重设登录密码.cmd”。账号和业务数据会保留。")}</p></details>{error && <p role="alert" className="error">{t(error)}</p>}
        <button type="button" className="text-button" onClick={() => void checkSession()} disabled={busy}>{t("重新连接")}</button>
      </form>}
    </section>
  </main></div>;

  return <div className="workspace"><aside className="sidebar"><Brand /><nav aria-label={t("工作区")} className={moreOpen ? "more-open" : undefined}>{navigationItems.slice(0, 4).map(item => navigationButton(item, false))}<div className="nav-additional">{navigationItems.slice(4).map(item => navigationButton(item, true))}</div><button type="button" className="nav-more" aria-expanded={moreOpen} aria-current={['archives', 'customers', 'materials', 'inventory', 'purchasing', 'raw-inventory', 'production'].includes(view.name) ? 'page' : undefined} disabled={view.name === 'entry' || navigationBlocked} onClick={() => setMoreOpen(value => !value)}><svg className="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h.01M12 12h.01M19 12h.01" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" /></svg>{t("更多")}</button></nav></aside><div className="workspace-body"><header className="app-header"><span className="breadcrumb">{t("交有数")}<span>/</span> {({ orders: t("待交清单"), sources: t("收订单"), deliveries: t("送货记录"), statements: t("客户对账"), archives: t("文件整理"), customers: t("客户"), materials: t("物料池"), inventory: t("成品库存"), purchasing: t("采购与收料"), production: t("生产记录"), "raw-inventory": t("原料库存"), entry: t("核对与录入"), detail: t("订单详情"), 'delivery-entry': t("登记送货") })[view.name]}</span><span className="local-badge" title={t("订单、送货和对账资料都存在这台电脑的本地数据库里，不经过云端。")}><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 5h18v11H3zM8 20h8M12 16v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg><span className="local-badge-full">{t("数据保存在这台电脑")}</span><span className="local-badge-short">{t("只在本机")}</span></span><div className="account"><LanguageSelector locale={locale} /><span className="account-avatar" aria-hidden="true">{session.user.username.slice(0, 1).toUpperCase()}</span><span className="account-identity"><span className="account-username" title={session.user.username}>{session.user.username}</span><small>{t(roleNames[session.user.role])}</small></span><button className="text-button" disabled={busy || view.name === "entry" || navigationBlocked} onClick={() => void logout()}>{t("退出")}</button></div></header>
    <dialog ref={reauthDialog} className="reauth-dialog" aria-labelledby="reauth-title" onCancel={event => event.preventDefault()}><h2 id="reauth-title">{t("重新登录")}</h2><p className="muted">{t("登录已过期。当前录入仍保留，请用原账号继续。")}</p><form onSubmit={login}><label>{t("账号")}<input value={session.user.username} readOnly autoComplete="username" /></label><PasswordInput value={password} onChange={setPassword} disabled={busy} />{error && <p role="alert" className="error">{t(error)}</p>}<button disabled={busy}>{busy ? t("登录中…") : t("重新登录")}</button></form></dialog>
    <main ref={main} tabIndex={-1} className="app-main">
      {error && <p role="alert" className="error">{t(error)}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
      {view.name === "orders" && <OrdersList customers={customers} canWrite={canWrite} onNew={() => navigate({ name: "entry" })} onUpload={() => navigate({ name: "sources" })} onOpen={id => navigate({ name: "detail", id })} />}
      {view.name === "statements" && <Statements customers={customers} canWrite={canWrite} onGuardChange={setNavigationBlocked} />}
      {view.name === "archives" && <Archives canWrite={canWrite} onGuardChange={setNavigationBlocked} />}
      {view.name === "inventory" && <Inventory onProduction={selected => navigate({ name: "production", selected })} key="finished" canWrite={canWrite} onGuardChange={setNavigationBlocked} onDelivery={selected => navigate({ name: "deliveries", selected })} />}
      {view.name === "raw-inventory" && <Inventory onProduction={selected => navigate({ name: "production", selected })} key="raw" materialKind="raw" canWrite={canWrite} onGuardChange={setNavigationBlocked} onDelivery={selected => navigate({ name: "deliveries", selected })} onPurchasing={() => navigate({ name: "purchasing" })} onRawMaterials={() => navigate({ name: "materials", initialKind: "raw" })} onPurchaseReceipt={selectedReceipt => navigate({ name: "purchasing", selectedReceipt })} />}
      {view.name === "production" && <Production key={`${view.orderId ?? "all"}:${view.selected ?? "list"}`} {...(view.orderId ? { orderId: view.orderId } : {})} {...(view.selected ? { selected: view.selected } : {})} canWrite={canWrite} onGuardChange={setNavigationBlocked} onOrder={id => navigate({ name: "detail", id })} onOrders={() => navigate({ name: "orders" })} onInventory={() => navigate({ name: "inventory" })} onRawInventory={() => navigate({ name: "raw-inventory" })} />}
      {view.name === "purchasing" && <Purchasing key={view.selectedReceipt ?? "list"} {...(view.selectedReceipt ? { selectedReceipt: view.selectedReceipt } : {})} canWrite={canWrite} onGuardChange={setNavigationBlocked} onUnsavedChange={setUnsavedPurchase} onRawInventory={() => navigate({ name: "raw-inventory" })} onRawMaterials={() => navigate({ name: "materials", initialKind: "raw" })} />}
      {view.name === "materials" && <Materials key={view.initialKind ?? "finished"} {...(view.initialKind ? { initialKind: view.initialKind } : {})} customers={customers} canWrite={canWrite} onGuardChange={setNavigationBlocked} />}
      {view.name === "customers" && <Customers customers={customers} canWrite={canWrite} onCreated={addCustomer} />}
      {view.name === "sources" && <Sources canWrite={canWrite} customers={customers} onCustomer={addCustomer} onManual={() => navigate({ name: "entry" })} onOrder={id => navigate({ name: "detail", id })} onGuardChange={setNavigationBlocked} />}
      {view.name === "entry" && <OrderEntry customers={customers} existing={view.existing} extraction={view.extraction} onCustomer={addCustomer} onCancel={() => navigate({ name: view.extraction ? "sources" : "orders" })} onSaved={id => { setNotice(view.existing ? msg("订单修订已保存，原确认凭证保留。") : msg("订单已确认并保存。")); setView({ name: "detail", id }); }} />}
      {view.name === "detail" && <OrderDetail onProduction={orderId => navigate({ name: "production", orderId })} key={view.id} id={view.id} canWrite={canWrite} onGuardChange={setNavigationBlocked} onDeliver={order => navigate({ name: "delivery-entry", order })} onBack={() => navigate({ name: "orders" })} onEdit={existing => navigate({ name: "entry", existing })} />}
      {view.name === "delivery-entry" && <DeliveryEntry order={view.order} onGuardChange={setNavigationBlocked} onCancel={() => navigate({ name: "detail", id: view.order.id })} onSaved={selected => navigate({ name: "deliveries", selected })} />}
      {view.name === "deliveries" && <Deliveries key={view.selected ?? "list"} customers={customers} selected={view.selected} canWrite={canWrite} onGuardChange={setNavigationBlocked} onSelect={selected => navigate({ name: "deliveries", selected })} onOrder={id => navigate({ name: "detail", id })} />}
    </main></div>
  </div>;
}
