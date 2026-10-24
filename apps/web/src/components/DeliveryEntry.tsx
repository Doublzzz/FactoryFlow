import { msg, t, type UiMessage } from "../i18n";
import { ItemIdentity } from "./ItemIdentity";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type DeliveryInput, type OrderDetail } from "../api";
import { displayUnit, quantityExceeds } from "../units";

function localDay() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function DeliveryEntry({ order: initial, onSaved, onCancel, onGuardChange }: {
  order: OrderDetail; onSaved: (id: string) => void; onCancel: () => void; onGuardChange: (value: boolean) => void;
}) {
  const [order, setOrder] = useState(initial);
  const [day, setDay] = useState(localDay);
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [error, setError] = useState<UiMessage>("");
  const [lineErrors, setLineErrors] = useState<Record<string, UiMessage>>({});
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<{ body: DeliveryInput; key: string } | null>(null);
  useEffect(() => { onGuardChange(true); return () => onGuardChange(false); }, [onGuardChange]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, []);

  function quantityProblems(current: OrderDetail) {
    const problems: Record<string, UiMessage> = {};
    for (const line of current.lines) {
      const quantity = quantities[line.id]?.trim() ?? "";
      if (quantityExceeds(quantity, line.remaining_quantity)) problems[line.id] = msg("当前显示还能送 {0} {1}，本次填了 {2}，请核对。", [line.remaining_quantity, line.source_unit, quantity]);
    }
    return problems;
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    if (!uncertain) {
      const problems = quantityProblems(order);
      setLineErrors(problems);
      if (Object.keys(problems).length) { setError(msg("本次送货数量超过剩余数量，请修改标红的位置。")); return; }
    }
    const lines = order.lines.filter(line => quantities[line.id]?.trim()).map(line => ({ order_line_id: line.id, quantity: quantities[line.id] ?? "" }));
    if (!lines.length) { setError(msg("请填写至少一条本次送货数量；不送的明细留空。")); return; }
    if (!uncertain || !pending.current) pending.current = { key: crypto.randomUUID(), body: { order_id: order.id, customer_id: order.customer_id, revision_id: order.revision_id, expected_version: order.version, delivery_date: day, lines } };
    setBusy(true); setError("");
    const command = pending.current;
    if (!command) { setBusy(false); return; }
    try { const result = await api.createDelivery(command.body, command.key); pending.current = null; setUncertain(false); onSaved(result.id); }
    catch (failure) { setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError("");
    try {
      const current = await api.detail(order.id);
      setOrder(current);
      const problems = quantityProblems(current);
      setLineErrors(problems);
      if (Object.keys(problems).length) setError(msg("已更新订单，请核对标红数量。"));
      pending.current = null;
    }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <section className="work-page delivery-entry-page">
    <button className="back-button" onClick={onCancel} disabled={busy || uncertain}>{t("返回订单详情")}</button>
    <div className="page-heading"><div><h1>{t("登记送货")}</h1><p>{order.customer_name} · {order.order_number}</p></div></div>
    <form onSubmit={submit} className="work-panel delivery-entry-form">
      <h2>{t("本次送货明细")}</h2>
      <p className="muted">{t("填写这次实际送出的数量。不送的明细留空；保存后立即减少未交数量。")}</p>
      <label className="delivery-date">{t("送货日期")}<input type="date" required value={day} onChange={event => setDay(event.target.value)} disabled={busy || uncertain} /></label>
      <div className="table-wrap"><table><thead><tr><th>{t("货物信息")}</th><th>{t("单位")}</th><th className="numeric">{t("还需交付")}</th><th>{t("本次送货")}</th></tr></thead><tbody>{order.lines.map(line => <tr key={line.id}><td><ItemIdentity line={line} />{line.quantity_policy.warning_codes.length > 0 && <small className="warning-text">{t("单位待核对，请核实数量")}</small>}</td><td>{displayUnit(line.source_unit)}</td><td className="numeric">{line.remaining_quantity}</td><td><input aria-label={t("{0} 本次送货", [line.description])} aria-invalid={!!lineErrors[line.id]} aria-describedby={lineErrors[line.id] ? `delivery-error-${line.id}` : undefined} inputMode="decimal" maxLength={64} placeholder={t("不送则留空")} value={quantities[line.id] ?? ""} onChange={event => { setQuantities(previous => ({ ...previous, [line.id]: event.target.value })); setLineErrors(previous => { const next = { ...previous }; delete next[line.id]; return next; }); setError(""); }} disabled={busy || uncertain || line.remaining_quantity === "0"} />{lineErrors[line.id] && <small className="danger-text" id={`delivery-error-${line.id}`}>{t(lineErrors[line.id]!)}</small>}</td></tr>)}</tbody></table></div>
      {error && <div className="error" role="alert">{t(error)}{!uncertain && <button type="button" className="text-button" disabled={busy} onClick={() => void refresh()}>{t("重新读取订单（保留已填数量）")}</button>}</div>}
      {uncertain && <p role="status" className="warning">{t("结果待确认。请重试本次送货，系统会核对是否已经保存。")}</p>}
      <div className="actions delivery-actions"><button disabled={busy || order.status !== "active"}>{busy ? t("保存中…") : uncertain ? t("重试本次送货") : t("确认实际送货")}</button><button type="button" className="secondary" onClick={onCancel} disabled={busy || uncertain}>{t("取消")}</button></div>
    </form>
  </section>;
}
