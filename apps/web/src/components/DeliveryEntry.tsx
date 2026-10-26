import { msg, t, type UiMessage } from "../i18n";
import { ItemIdentity } from "./ItemIdentity";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type DeliveryInput, type InventoryAccount, type OrderDetail } from "../api";
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
  const [positions, setPositions] = useState<Record<string, InventoryAccount | null>>({});
  const [inventoryLoading, setInventoryLoading] = useState(initial.lines.some(line => !!line.material_id));
  const [inventoryError, setInventoryError] = useState<UiMessage>("");
  const [inventoryRefresh, setInventoryRefresh] = useState(0);
  const [syncInventory, setSyncInventory] = useState(true);
  const [confirmShortage, setConfirmShortage] = useState(false);
  const [serverShortage, setServerShortage] = useState(false);
  const materialIds = [...new Set(order.lines.flatMap(line => line.material_id ? [line.material_id] : []))].sort().join(",");
  const pending = useRef<{ body: DeliveryInput; key: string } | null>(null);
  useEffect(() => {
    let live = true;
    setPositions({}); setInventoryError("");
    if (!materialIds) { setInventoryLoading(false); return; }
    setInventoryLoading(true);
    api.inventoryPreview(materialIds.split(",")).then(result => { if (live) setPositions(Object.fromEntries(result.items.map(item => [item.material_id, item.account]))); })
      .catch(failure => { if (live) setInventoryError(message(failure)); }).finally(() => { if (live) setInventoryLoading(false); });
    return () => { live = false; };
  }, [materialIds, inventoryRefresh]);
  useEffect(() => { onGuardChange(true); return () => onGuardChange(false); }, [onGuardChange]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, []);

  function scaled(value: string): bigint | null {
    if (!/^-?\d+(?:\.\d{1,3})?$/.test(value)) return null;
    const negative = value.startsWith("-");
    const [whole = "0", fraction = ""] = (negative ? value.slice(1) : value).split(".");
    const amount = BigInt(whole) * 1000n + BigInt(fraction.padEnd(3, "0"));
    return negative ? -amount : amount;
  }
  const selectedManaged = order.lines.filter(line => quantities[line.id]?.trim() && line.material_id && positions[line.material_id]);
  const totals = new Map<string, bigint>();
  for (const line of selectedManaged) { const amount = scaled(quantities[line.id]?.trim() ?? ""); if (amount !== null && amount > 0n) totals.set(line.material_id!, (totals.get(line.material_id!) ?? 0n) + amount); }
  const shortage = serverShortage || [...totals].some(([id, total]) => { const balance = scaled(positions[id]!.balance); return balance !== null && total > balance; });
  const unitMismatch = selectedManaged.some(line => !line.canonical_unit || line.canonical_unit !== positions[line.material_id!]!.canonical_unit);
  function inventoryLabel(line: OrderDetail["lines"][number]) {
    if (!line.material_id) return t("未关联物料");
    if (inventoryLoading || inventoryError) return t("库存状态待读取");
    const account = positions[line.material_id];
    return account ? t("账面 {0} {1}{2}", [account.balance, account.canonical_unit, account.has_skipped ? t(" · 待核对") : ""]) : t("库存未管理");
  }

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
    if (!uncertain || !pending.current) pending.current = { key: crypto.randomUUID(), body: { order_id: order.id, customer_id: order.customer_id, revision_id: order.revision_id, expected_version: order.version, delivery_date: day, lines, inventory_mode: syncInventory ? "sync" : "skip", confirm_inventory_shortage: syncInventory && confirmShortage } };
    setBusy(true); setError("");
    const command = pending.current;
    if (!command) { setBusy(false); return; }
    try { const result = await api.createDelivery(command.body, command.key); pending.current = null; setUncertain(false); onSaved(result.id); }
    catch (failure) { setError(message(failure)); setUncertain(previous => previous || !(failure instanceof ApiError) || failure.status >= 500); if (failure instanceof ApiError && failure.code === "INVENTORY_SHORTAGE") setServerShortage(true); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError("");
    try {
      const current = await api.detail(order.id);
      setOrder(current);
      setInventoryRefresh(value => value + 1);
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
      <div className="table-wrap"><table><thead><tr><th>{t("货物信息")}</th><th>{t("单位")}</th><th className="numeric">{t("还需交付")}</th><th>{t("本次送货")}</th></tr></thead><tbody>{order.lines.map(line => <tr key={line.id}><td><ItemIdentity line={line} /><small className="delivery-inventory-line">{inventoryLabel(line)}</small>{line.quantity_policy.warning_codes.length > 0 && <small className="warning-text">{t("单位待核对，请核实数量")}</small>}</td><td>{displayUnit(line.source_unit)}</td><td className="numeric">{line.remaining_quantity}</td><td><input aria-label={t("{0} 本次送货", [line.description])} aria-invalid={!!lineErrors[line.id]} aria-describedby={lineErrors[line.id] ? `delivery-error-${line.id}` : undefined} inputMode="decimal" maxLength={64} placeholder={t("不送则留空")} value={quantities[line.id] ?? ""} onChange={event => { setQuantities(previous => ({ ...previous, [line.id]: event.target.value })); setConfirmShortage(false); setServerShortage(false); setLineErrors(previous => { const next = { ...previous }; delete next[line.id]; return next; }); setError(""); }} disabled={busy || uncertain || line.remaining_quantity === "0"} />{lineErrors[line.id] && <small className="danger-text" id={`delivery-error-${line.id}`}>{t(lineErrors[line.id]!)}</small>}</td></tr>)}</tbody></table></div>
      {inventoryLoading && <p role="status" className="muted">{t("正在读取库存状态…")}</p>}
      {inventoryError && <div className="error" role="alert">{t("库存状态未读到，请重试后核对本次处理。")}{t(inventoryError)}<button type="button" className="text-button" disabled={busy || uncertain} onClick={() => setInventoryRefresh(value => value + 1)}>{t("重试读取库存")}</button></div>}
      {!!selectedManaged.length && <fieldset className="delivery-inventory-choice" disabled={busy || uncertain}><legend>{t("本次库存处理")}</legend>
        <label><input type="checkbox" checked={syncInventory} onChange={event => { setSyncInventory(event.target.checked); setConfirmShortage(false); }} />{t("同时扣减库存")}</label>
        {!syncInventory && <p className="warning">{t("本次只记送货，不扣库存；相关成品会标为待核对。")}</p>}
        {syncInventory && unitMismatch && <p className="warning">{t("有明细的订单单位与库存单位不一致或未知。请核对，或取消本次同步。")}</p>}
        {syncInventory && shortage && <label className="warning"><input type="checkbox" checked={confirmShortage} onChange={event => setConfirmShortage(event.target.checked)} />{t("实物已发出，入库尚未登记；确认按本次数量扣减，账面可为负。")}</label>}
      </fieldset>}
      {error && <div className="error" role="alert">{t(error)}{!uncertain && <button type="button" className="text-button" disabled={busy} onClick={() => void refresh()}>{t("重新读取订单（保留已填数量）")}</button>}</div>}
      {uncertain && <p role="status" className="warning">{t("结果待确认。请重试本次送货，系统会核对是否已经保存。")}</p>}
      <div className="actions delivery-actions"><button disabled={busy || order.status !== "active" || !uncertain && (inventoryLoading || !!inventoryError)}>{busy ? t("保存中…") : uncertain ? t("重试本次送货") : t("确认实际送货")}</button><button type="button" className="secondary" onClick={onCancel} disabled={busy || uncertain}>{t("取消")}</button></div>
    </form>
  </section>;
}
