import { t, type UiMessage } from "../i18n";
import { useEffect, useState } from "react";
import { api, message, type Customer, type Statement } from "../api";
import { StatementEditor } from "./StatementEditor";
import { StatementFollowUp } from "./StatementFollowUp";

function currentMonth() {
  const now = new Date();
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  return { start: `${month}-01`, end: `${month}-${new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()}` };
}

export function Statements({ customers, canWrite, onGuardChange }: {
  customers: Customer[]; canWrite: boolean; onGuardChange: (blocked: boolean) => void;
}) {
  const [customer, setCustomer] = useState("");
  const [period, setPeriod] = useState(currentMonth);
  const [currency, setCurrency] = useState<"CNY" | "USD">("CNY");
  const [items, setItems] = useState<Statement[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<Statement | "new" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  useEffect(() => {
    let active = true;
    setItems([]); setCursor(null); setError("");
    if (customer) {
      setBusy(true);
      Promise.all([api.statements(customer), api.statementSettings(customer)]).then(([page, preference]) => { if (active) {
        setItems(page.items); setCursor(page.next_cursor);
        const day = preference?.cycle_day;
        if (day) {
          const now = new Date(); const year = now.getFullYear(), month = now.getMonth();
          const previous = new Date(year, month - 1, Math.min(day, new Date(year, month, 0).getDate()));
          previous.setDate(previous.getDate() + 1);
          const finish = new Date(year, month, Math.min(day, new Date(year, month + 1, 0).getDate()));
          const iso = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
          setPeriod({ start: iso(previous), end: iso(finish) });
        } else setPeriod(currentMonth());
      } })
        .catch(failure => { if (active) setError(message(failure)); }).finally(() => { if (active) setBusy(false); });
    }
    return () => { active = false; };
  }, [customer]);
  async function load(more = false) {
    setBusy(true); setError("");
    try { const page = await api.statements(customer, more ? cursor ?? undefined : undefined); setItems(old => more ? [...old, ...page.items] : page.items); setCursor(page.next_cursor); }
    catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  async function openSource(statementId: string) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const statement = await api.statement(statementId);
      if (statement.customer_id !== customer) throw new Error(t("对账单不属于当前客户，请刷新后重试。"));
      setSelected(statement);
    } catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  if (selected) return <StatementEditor key={selected === "new" ? `${customer}-${period.start}-${period.end}-${currency}` : selected.id}
    customer={customers.find(c => c.id === customer)!} start={selected === "new" ? period.start : selected.period_start}
    end={selected === "new" ? period.end : selected.period_end} existing={selected === "new" ? null : selected} currency={selected === "new" ? currency : selected.currency ?? "CNY"}
    canWrite={canWrite} onGuardChange={onGuardChange} onBack={() => { setSelected(null); void load(); }} />;
  return <section className="statements-page work-page statement-list-page">
    <div className="page-heading"><div><h1>{t("客户对账")}</h1></div></div>
    <section className="work-panel"><h2>{t("选择客户与对账期间")}</h2>
    <form className="statement-filters" onSubmit={event => { event.preventDefault(); if (customer && !busy) setSelected("new"); }}>
      <label>{t("客户")}<select required value={customer} disabled={busy} onChange={e => setCustomer(e.target.value)}><option value="">{t("选择要对账的客户")}</option>{customers.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select></label>
      <label>{t("开始日期")}<input required type="date" value={period.start} onChange={e => setPeriod({ ...period, start: e.target.value })} /></label>
      <label>{t("结束日期")}<input required type="date" min={period.start} value={period.end} onChange={e => setPeriod({ ...period, end: e.target.value })} /></label>
      <label>{t("币种")}<select value={currency} disabled={busy} onChange={e => setCurrency(e.target.value as "CNY" | "USD")}><option value="CNY">{t("CNY 人民币")}</option><option value="USD">{t("USD 美元")}</option></select></label>
      {canWrite && <button disabled={!customer || busy}>{t("开始本期对账")}</button>}
    </form>
    </section>
    {error && <p role="alert" className="error">{t(error)}<button className="text-button" disabled={busy} onClick={() => void load()}>{t("重新读取")}</button></p>}
    {customer && <StatementFollowUp key={customer} customerId={customer} disabled={busy} onOpen={id => void openSource(id)} />}
    <section className="work-panel" aria-label={t("已有对账记录")}><h2>{t("已有对账记录")}</h2>
    {busy && <p role="status">{t("正在读取对账记录…")}</p>}
    {!customer && <p className="empty-state">{t("先选客户，就能查看已有对账单或开始本期对账。")}</p>}
    {customer && !busy && !items.length && !error && <p className="empty-state">{t("该客户还没有对账记录。选择期间，从送货明细开始。")}</p>}
    {!!items.length && <><div className="table-wrap"><table><thead><tr><th>{t("对账期间")}</th><th>{t("状态")}</th><th>{t("版本")}</th><th className="numeric">{t("本期金额")}</th><th>{t("操作")}</th></tr></thead><tbody>{items.map(item => <tr key={item.id}>
      <td>{t("{0} 至{1}", [(item.period_start) ?? "", (item.period_end) ?? ""])}</td><td>{item.status === "draft" ? t("草稿") : item.status === "confirmed" ? t("正式结算") : item.status === "void" ? t("已作废") : t("已放弃")}</td><td>v{item.version}</td><td className="numeric">{item.calculation.total ?? t("待核对")} {item.currency ?? "CNY"}</td><td><button className="text-button" disabled={busy} onClick={() => setSelected(item)}>{t("打开对账单")}</button></td>
    </tr>)}</tbody></table></div>{cursor && <button className="secondary" disabled={busy} onClick={() => void load(true)}>{t("加载更多对账记录")}</button>}</>}
    </section>
  </section>;
}
