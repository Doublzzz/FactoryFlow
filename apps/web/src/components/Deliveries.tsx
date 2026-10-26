import { getLocale, t, type UiMessage } from "../i18n";
import { displayUnit } from "../units";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Customer, type Delivery, type DeliverySummary } from "../api";
import { DeliveryLayout } from "./DeliveryLayout";

export function Deliveries({ customers, selected, canWrite, onSelect, onOrder, onGuardChange }: {
  customers: Customer[]; selected?: string | undefined; canWrite: boolean; onSelect: (id?: string) => void; onOrder: (id: string) => void; onGuardChange: (value: boolean) => void;
}) {
  const [items, setItems] = useState<DeliverySummary[]>([]);
  const [delivery, setDelivery] = useState<Delivery | null>(null);
  const [customer, setCustomer] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [voiding, setVoiding] = useState(false);
  const [reason, setReason] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [layoutOpen, setLayoutOpen] = useState(false);
  const [layoutGuard, setLayoutGuard] = useState(false);
  const pending = useRef<{ id: string; version: number; reason: string; key: string } | null>(null);
  useEffect(() => { onGuardChange(busy || voiding || uncertain || layoutGuard); return () => onGuardChange(false); }, [busy, voiding, uncertain, layoutGuard, onGuardChange]);
  async function load(more = false) {
    setBusy(true); setError("");
    try {
      if (selected) setDelivery(await api.delivery(selected));
      else { const page = await api.deliveries(customer || undefined, more ? cursor ?? undefined : undefined); setItems(previous => more ? [...previous, ...page.items] : page.items); setCursor(page.next_cursor); }
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    let active = true;
    setBusy(true); setError(""); setDelivery(null); setItems([]); setCursor(null);
    (selected ? api.delivery(selected).then(data => { if (active) setDelivery(data); }) : api.deliveries(customer || undefined).then(page => { if (active) { setItems(page.items); setCursor(page.next_cursor); } }))
      .catch(failure => { if (active) setError(message(failure)); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [selected, customer]);
  async function submitVoid(event: FormEvent) {
    event.preventDefault(); if (!delivery || busy) return;
    if (!uncertain || !pending.current) pending.current = { id: delivery.id, version: delivery.version, reason, key: crypto.randomUUID() };
    setBusy(true); setError("");
    try {
      const command = pending.current;
      setDelivery(await api.voidDelivery(command.id, command.version, command.reason, command.key));
      pending.current = null; setUncertain(false); setVoiding(false); setReason("");
    } catch (failure) { setError(message(failure)); setUncertain(previous => previous || !(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }
  if (layoutOpen && delivery) return <DeliveryLayout delivery={delivery} canWrite={canWrite} onClose={() => { setLayoutOpen(false); setLayoutGuard(false); }} onGuardChange={setLayoutGuard} />;
  return <section className="work-page deliveries-page">
    {selected && <button className="back-button" disabled={busy || voiding || uncertain} onClick={() => onSelect()}>{t("返回送货记录")}</button>}
    <div className="page-heading"><div><h1>{selected ? t("送货详情") : t("送货记录")}</h1><p>{t("每次实际送货与作废记录均保留。")}</p></div></div>
    {error && <div className="error" role="alert">{t(error)}{!uncertain && <button className="text-button" disabled={busy} onClick={() => void load()}>{t("重新读取送货")}</button>}</div>}
    {!selected && <section className="work-panel work-list-panel" aria-label={t("送货筛选与记录")}><div className="list-toolbar"><label className="filter">{t("客户")}<select value={customer} onChange={event => setCustomer(event.target.value)} disabled={busy}><option value="">{t("全部客户")}</option>{customers.map(item => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></label></div>
      {!busy && !error && !items.length && <p className="empty-state">{t("暂无送货记录。从订单详情选择“登记送货”开始。")}</p>}
      {!!items.length && <div className="table-wrap"><table><thead><tr><th>{t("送货日期")}</th><th>{t("客户")}</th><th>{t("来源订单")}</th><th>{t("状态")}</th><th>{t("查看")}</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.delivery_date}</td><td>{item.customer_name}</td><td>{item.order_number}</td><td>{item.status === "active" ? t("有效") : t("已作废")}</td><td><button className="text-button" disabled={busy} onClick={() => onSelect(item.id)}>{t("查看送货")}</button></td></tr>)}</tbody></table></div>}
      {cursor && <button className="secondary" disabled={busy} onClick={() => void load(true)}>{t("加载更多送货")}</button>}</section>}
    {busy && <p role="status" className="muted">{t("正在处理…")}</p>}
    {delivery && <><section className="detail-section delivery-detail work-panel"><div className="row-between work-panel-heading"><h2>{delivery.customer_name}</h2><span className={`state-label ${delivery.status === "void" ? "deleted" : "active"}`}>{delivery.status === "void" ? t("已作废") : t("有效送货")}</span></div><p>{t("{0} · 来源订单{1}", [(delivery.delivery_date) ?? "", (delivery.order_number) ?? ""])}</p>
      <div className="actions delivery-detail-actions"><a className="print-link" href={`/api/v1/deliveries/${delivery.id}/print?locale=${getLocale()}`} target="_blank" rel="noopener noreferrer">{t("打开打印页")}</a><button type="button" className="secondary" disabled={busy || voiding || uncertain} onClick={() => setLayoutOpen(true)}>{t("版面与模板")}</button><button className="text-button" disabled={busy || voiding || uncertain} onClick={() => onOrder(delivery.order_id)}>{t("查看来源订单")}</button>{canWrite && delivery.status === "active" && <button className="text-button danger-text" disabled={busy || voiding || uncertain} onClick={() => setVoiding(true)}>{t("作废送货")}</button>}</div>
      {delivery.status === "void" && <p className="warning" role="status">{t("已作废，数量已回到订单未交。原因：{0}", [(delivery.void_reason) ?? ""])}</p>}
      <h3 className="work-subheading">{t("本次送货明细")}</h3><div className="table-wrap"><table><thead><tr><th>{t("品名")}</th><th className="numeric">{t("本次数量")}</th><th>{t("单位")}</th><th>{t("库存处理")}</th></tr></thead><tbody>{delivery.lines.map(line => <tr key={line.order_line_id}><td>{line.description}{line.quantity_policy.warning_codes.length > 0 && <small className="warning-text">{t("单位待核对")}</small>}</td><td className="numeric">{line.quantity}</td><td>{displayUnit(line.source_unit)}</td><td>{!line.inventory ? t("历史未计库存") : line.inventory.state === "tracked" ? delivery.status === "void" ? t("原扣减已冲回") : line.inventory.reason === "MISSING_RECEIPT" ? t("已扣减；入库当时未登记") : t("已扣减库存") : line.inventory.state === "skipped" ? t("本次只记送货") : line.inventory.state === "unmanaged" ? t("库存未管理") : t("未关联物料")}</td></tr>)}</tbody></table></div><details className="work-secondary-details"><summary>{t("送货记录标识")}</summary><p className="hash">{delivery.id}</p></details></section>
      {voiding && <form className="status-form" onSubmit={submitVoid}><h2>{t("作废这次送货")}</h2><p>{t("将按原送货数量恢复订单未交；原先已扣库存的数量同时冲回，送货内容保留。")}</p><label>{t("作废原因")}<textarea autoFocus required maxLength={500} value={reason} disabled={busy || uncertain} onChange={event => setReason(event.target.value)} /></label>{uncertain && <p className="warning" role="status">{t("结果待确认，请重试同一次作废。")}</p>}<div className="actions"><button disabled={busy || !reason.trim()}>{busy ? t("处理中…") : uncertain ? t("重试本次作废") : t("确认作废送货")}</button><button type="button" className="secondary" disabled={busy || uncertain} onClick={() => setVoiding(false)}>{t("取消")}</button></div></form>}</>}
  </section>;
}
