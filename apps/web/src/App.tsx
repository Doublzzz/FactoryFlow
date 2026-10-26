import { getLocale, msg, setLocale, subscribeLocale, t, type Locale, type UiMessage } from "./i18n";
import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { api, ApiError, message, setCSRF, type Customer, type OrderDetail as Detail, type Session } from "./api";
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

type View = { name: "delivery-entry"; order: Detail } | { name: "deliveries"; selected?: string | undefined } | { name: "sources"; file?: File | undefined } | { name: "orders" | "customers" | "statements" | "archives" | "materials" | "inventory" } | { name: "entry"; existing?: Detail; extraction?: Extraction } | { name: "detail"; id: string };
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
    setBusy(true); setError("");
    try { await api.logout(); setSession(null); setCSRF(""); setCustomers([]); setView({ name: "orders" }); setNotice(""); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  function addCustomer(customer: Customer) {
    setCustomers(previous => [...previous.filter(c => c.id !== customer.id), customer].sort((a, b) => a.full_name.localeCompare(b.full_name, locale)));
    setNotice(msg("客户已创建。"));
  }
  function navigate(next: View) { setView(next); setError(""); setNotice(""); setMoreOpen(false); }
  const canWrite = session?.user.role !== "viewer";

  if (!session) return <div className="login-layout"><header className="login-header"><Brand /><span>{t("订单到送货，每笔都有数")}</span><LanguageSelector locale={locale} /></header><main className="login-main">
    <section className="login-intro"><h1>{t("客户的货，")}<br />{t("还差多少没交？")}</h1><p>{t("收下订单，核对明细，分批送货。")}<br />{t("已交和待交数量，随每笔送货更新。")}</p><div className="example-sheet" aria-label={t("合成订单示例")}><div className="example-caption"><strong>{t("一笔订单，交到哪里一眼看清")}</strong><span>{t("合成示例")}</span></div><div className="example-item"><span>{t("工业铝型材")}<small>{t("6063 · 银白氧化")}</small></span><span className="unit-tag">KG</span></div><div className="example-quantities"><div><span>{t("客户订购")}</span><strong>125.5</strong></div><div><span>{t("累计已交")}</span><strong>25.5</strong></div><div><span>{t("还需交付")}</span><strong>100</strong></div></div><div className="example-foot">{t("每次登记送货，余量自动扣减；作废按原数量回退。")}</div></div></section>
    <section className="login-panel"><h2>{t("登录交有数")}</h2><p className="muted">{t("使用工厂本机设置的账号和密码。")}</p>
      {checking ? <p role="status" className="muted">{t("正在连接本地服务…")}</p> : <form onSubmit={login}>
        <label>{t("账号")}<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required maxLength={100} disabled={busy} /></label>
        <label>{t("密码")}<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required maxLength={128} disabled={busy} /></label>
        <button className="full-width" disabled={busy}>{busy ? t("登录中…") : t("登录")}</button>{error && <p role="alert" className="error">{t(error)}</p>}
        <button type="button" className="text-button" onClick={() => void checkSession()} disabled={busy}>{t("重新连接")}</button>
      </form>}
    </section>
  </main><footer>{t("交有数 / FactoryFlow")}<span>{t("订单原件与确认记录，保存在本机")}</span></footer></div>;

  return <div className="workspace"><aside className="sidebar"><Brand /><nav aria-label={t("工作区")} className={moreOpen ? "more-open" : undefined}>{([['orders', t("待交清单"), t("待交")], ['sources', t("收订单"), t("收单")], ['deliveries', t("送货记录"), t("送货")], ['statements', t("客户对账"), t("对账")], ['archives', t("文件整理"), t("文件整理")], ['customers', t("客户"), t("客户")], ['materials', t("物料池"), t("物料池")], ['inventory', t("成品库存"), t("库存")]] as const).map(([name, label, short], index) => <button key={name} aria-label={label} className={index > 3 ? "nav-secondary" : undefined} aria-current={(name === 'orders' ? ['orders', 'entry', 'detail', 'delivery-entry'].includes(view.name) : view.name === name) ? 'page' : undefined} onClick={() => navigate({ name })} disabled={view.name === 'entry' || navigationBlocked}><NavIcon name={(name === "materials" || name === "inventory") ? "archives" : name} /><span className="nav-label">{label}</span><span className="nav-short" aria-hidden="true">{short}</span></button>)}<button type="button" className="nav-more" aria-expanded={moreOpen} aria-current={['archives', 'customers', 'materials', 'inventory'].includes(view.name) ? 'page' : undefined} disabled={view.name === 'entry' || navigationBlocked} onClick={() => setMoreOpen(value => !value)}><svg className="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h.01M12 12h.01M19 12h.01" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" /></svg>{t("更多")}</button></nav></aside><div className="workspace-body"><header className="app-header"><span className="breadcrumb">{t("交有数")}<span>/</span> {({ orders: t("待交清单"), sources: t("收订单"), deliveries: t("送货记录"), statements: t("客户对账"), archives: t("文件整理"), customers: t("客户"), materials: t("物料池"), inventory: t("成品库存"), entry: t("核对与录入"), detail: t("订单详情"), 'delivery-entry': t("登记送货") })[view.name]}</span><span className="local-badge" title={t("订单、送货和对账资料都存在这台电脑的本地数据库里，不经过云端。")}><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 5h18v11H3zM8 20h8M12 16v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg><span className="local-badge-full">{t("数据保存在这台电脑")}</span><span className="local-badge-short">{t("只在本机")}</span></span><div className="account"><LanguageSelector locale={locale} /><span className="account-avatar" aria-hidden="true">{session.user.username.slice(0, 1).toUpperCase()}</span><span>{session.user.username}<small>{t(roleNames[session.user.role])}</small></span><button className="text-button" disabled={busy || view.name === "entry" || navigationBlocked} onClick={() => void logout()}>{t("退出")}</button></div></header>
    <dialog ref={reauthDialog} className="reauth-dialog" aria-labelledby="reauth-title" onCancel={event => event.preventDefault()}><h2 id="reauth-title">{t("重新登录")}</h2><p className="muted">{t("登录已过期。当前录入仍保留，请用原账号继续。")}</p><form onSubmit={login}><label>{t("账号")}<input value={session.user.username} readOnly autoComplete="username" /></label><label>{t("密码")}<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required maxLength={128} disabled={busy} /></label>{error && <p role="alert" className="error">{t(error)}</p>}<button disabled={busy}>{busy ? t("登录中…") : t("重新登录")}</button></form></dialog>
    <main ref={main} tabIndex={-1} className="app-main">
      {error && <p role="alert" className="error">{t(error)}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
      {view.name === "orders" && <OrdersList customers={customers} canWrite={canWrite} onNew={() => navigate({ name: "entry" })} onUpload={file => navigate({ name: "sources", file })} onOpen={id => navigate({ name: "detail", id })} onMaterials={() => navigate({ name: "materials" })} onCustomers={() => navigate({ name: "customers" })} />}
      {view.name === "statements" && <Statements customers={customers} canWrite={canWrite} onGuardChange={setNavigationBlocked} />}
      {view.name === "archives" && <Archives canWrite={canWrite} onGuardChange={setNavigationBlocked} />}
      {view.name === "inventory" && <Inventory canWrite={canWrite} onGuardChange={setNavigationBlocked} onDelivery={selected => navigate({ name: "deliveries", selected })} />}
      {view.name === "materials" && <Materials customers={customers} canWrite={canWrite} onGuardChange={setNavigationBlocked} />}
      {view.name === "customers" && <Customers customers={customers} canWrite={canWrite} onCreated={addCustomer} />}
      {view.name === "sources" && <Sources canWrite={canWrite} initialFile={view.file} onManual={() => navigate({ name: "entry" })} onReview={extraction => navigate({ name: "entry", extraction })} onOrder={id => navigate({ name: "detail", id })} onGuardChange={setNavigationBlocked} />}
      {view.name === "entry" && <OrderEntry customers={customers} existing={view.existing} extraction={view.extraction} onCustomer={addCustomer} onCancel={() => navigate({ name: view.extraction ? "sources" : "orders" })} onSaved={id => { setNotice(view.existing ? msg("订单修订已保存，原确认凭证保留。") : msg("订单已确认并保存。")); setView({ name: "detail", id }); }} />}
      {view.name === "detail" && <OrderDetail key={view.id} id={view.id} canWrite={canWrite} onGuardChange={setNavigationBlocked} onDeliver={order => navigate({ name: "delivery-entry", order })} onBack={() => navigate({ name: "orders" })} onEdit={existing => navigate({ name: "entry", existing })} />}
      {view.name === "delivery-entry" && <DeliveryEntry order={view.order} onGuardChange={setNavigationBlocked} onCancel={() => navigate({ name: "detail", id: view.order.id })} onSaved={selected => navigate({ name: "deliveries", selected })} />}
      {view.name === "deliveries" && <Deliveries key={view.selected ?? "list"} customers={customers} selected={view.selected} canWrite={canWrite} onGuardChange={setNavigationBlocked} onSelect={selected => navigate({ name: "deliveries", selected })} onOrder={id => navigate({ name: "detail", id })} />}
    </main></div>
  </div>;
}
