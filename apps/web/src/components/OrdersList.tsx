import { t, type UiMessage } from "../i18n";
import { ItemIdentity } from "./ItemIdentity";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, message, type Customer, type OpenLine } from "../api";
import { deliveredShare, displayUnit, isZeroQuantity } from "../units";
import { FileDrop } from "./FileDrop";
import "./orders.css";

function Progress({ line }: { line: OpenLine }) {
  const share = deliveredShare(line.delivered_quantity, line.quantity);
  if (share === null) return null;
  return <span className="delivery-progress" aria-hidden="true"><span style={{ width: `${share}%` }} /></span>;
}

/** Shown before anything has been entered: start from one order, no imports required. */
function StartPanel({ canWrite, onNew, onUpload, onMaterials, onCustomers }: { canWrite: boolean; onNew: () => void; onUpload: (file?: File) => void; onMaterials: () => void; onCustomers: () => void }) {
  return <section className="first-order" aria-labelledby="first-order-title">
    <div className="first-order-intro"><h1 id="first-order-title">{t("从第一张订单开始")}</h1><p>{t("不用先导入客户和物料。录单时添加客户，确认后可按需收录物料、记住客户料号。")}</p></div>
    {canWrite ? <div className="first-order-start">
      <FileDrop file={null} onFile={file => { if (file) onUpload(file); }} />
      <div className="first-order-manual"><h2>{t("手上只有纸质单？")}</h2><p>{t("直接照着填也行。新客户在录单页顺手新建，下次直接选。")}</p><button className="secondary" onClick={onNew}>{t("直接填写订单")}</button>
        <p className="first-order-import">{t("已经有物料表或客户名单？")} <button className="text-button" onClick={onMaterials}>{t("导入物料表")}</button> <button className="text-button" onClick={onCustomers}>{t("添加客户")}</button><span>{t("不导入也完全可以用。")}</span></p></div>
    </div> : <p className="muted">{t("还没有订单。有录入权限的同事录入后，这里会显示仍需交付的明细。")}</p>}
    <ol className="first-order-steps" aria-label={t("一张订单会这样走完")}>
      <li><span>1</span><div><strong>{t("收订单")}</strong><small>{t("对照原件确认数量、单位和单价")}</small></div></li>
      <li><span>2</span><div><strong>{t("分批送货")}</strong><small>{t("每送一批，待交数量自动减掉")}</small></div></li>
      <li><span>3</span><div><strong>{t("跟客户对账")}</strong><small>{t("按期间汇总送货，导出对账表")}</small></div></li>
    </ol>
  </section>;
}

export function OrdersList({ customers, canWrite, onNew, onUpload, onOpen, onMaterials, onCustomers }: {
  customers: Customer[]; canWrite: boolean; onNew: () => void; onUpload: (file?: File) => void; onOpen: (id: string) => void; onMaterials: () => void; onCustomers: () => void;
}) {
  const [customer, setCustomer] = useState("");
  const [status, setStatus] = useState<"active" | "deleted">("active");
  const [items, setItems] = useState<OpenLine[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<UiMessage>("");
  const serial = useRef(0);
  const load = useCallback(async (next?: string) => {
    const request = ++serial.current;
    setBusy(true); setError("");
    try {
      const result = await api.openLines(customer, next, status);
      if (request === serial.current) { setItems(previous => next ? [...previous, ...result.items] : result.items); setCursor(result.next_cursor); }
    } catch (failure) { if (request === serial.current) setError(message(failure)); }
    finally { if (request === serial.current) setBusy(false); }
  }, [customer, status]);
  useEffect(() => { setItems([]); setCursor(null); void load(); return () => { serial.current++; }; }, [load]);

  const groups = new Map<string, { order: OpenLine; lines: OpenLine[] }>();
  for (const line of items) {
    const group = groups.get(line.order_id);
    if (group) group.lines.push(line);
    else groups.set(line.order_id, { order: line, lines: [line] });
  }

  if (status === "active" && !customer && !busy && !error && !items.length && !customers.length)
    return <section className="work-page orders-page"><StartPanel canWrite={canWrite} onNew={onNew} onUpload={onUpload} onMaterials={onMaterials} onCustomers={onCustomers} /></section>;

  return <section className="work-page orders-page">
    <div className="page-heading"><div><h1>{t("待交清单")}</h1></div>
      {canWrite && <div className="actions"><button className="secondary" onClick={() => onUpload()}>{t("上传订单照片 / 文件")}</button><button onClick={onNew}>{t("直接填写订单")}</button></div>}</div>
    <section className="work-panel work-list-panel" aria-label={t("订单筛选与交付明细")}>
    <div className="list-toolbar">
      <div className="tabs" aria-label={t("订单状态")}><button className={status === "active" ? "selected" : ""} onClick={() => setStatus("active")} aria-pressed={status === "active"}>{t("待交明细")}</button>
        <button className={status === "deleted" ? "selected" : ""} onClick={() => setStatus("deleted")} aria-pressed={status === "deleted"}>{t("已删除")}</button></div>
      <label className="filter">{t("筛选客户")}<select value={customer} onChange={e => setCustomer(e.target.value)}><option value="">{t("全部客户")}</option>{customers.map(c => <option value={c.id} key={c.id}>{c.full_name}</option>)}</select></label>
      <button className="secondary" disabled={busy} onClick={() => void load()}>{t("刷新明细")}</button>
    </div>
    {error && <p role="alert" className="error">{t(error)}</p>}
    {busy && !items.length ? <div role="status" className="loading"><div /><div /><div /><span>{t("正在读取订单…")}</span></div> : !items.length && !error ? <section className="empty">
      <h2>{status === "deleted" ? t("没有已删除订单") : customer ? t("这位客户目前没有待交明细") : t("目前没有待交明细")}</h2><p>{status === "deleted" ? t("删除的订单会保留确认凭证，并可在详情中恢复。") : t("新订单确认后，仍需交付的明细会出现在这里。")}</p>{status === "active" && canWrite && <div className="actions empty-actions"><button className="secondary" onClick={() => onUpload()}>{t("上传订单照片 / 文件")}</button><button onClick={onNew}>{t("直接填写订单")}</button></div>}
    </section> : <>
      <div className="table-wrap desktop-lines grouped-order-list"><table><thead><tr><th>{t("货物 / 规格")}</th><th className="numeric">{t("订购数量")}</th><th className="numeric delivered">{t("已交数量")}</th><th className="numeric remaining">{t("还需交付")}</th><th>{t("单位")}</th><th><span className="sr-only">{t("操作")}</span></th></tr></thead>
        {Array.from(groups.values()).map(({ order, lines }) => <tbody key={order.order_id}><tr className="order-group-heading"><th colSpan={6} scope="rowgroup"><div className="order-group-context"><span className="customer-initial" aria-hidden="true">{order.customer_name.slice(0, 1)}</span><strong>{order.customer_name}</strong><span className="order-reference">{order.order_number}</span>{status === "deleted" && <span className="order-group-state is-deleted">{t("已删除")}</span>}<time dateTime={order.business_date}>{order.business_date}</time></div></th></tr>
          {lines.map(line => <tr key={line.id}><td><div className="order-item"><span className="order-item-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="m4 7 8-4 8 4v10l-8 4-8-4ZM4 7l8 4 8-4M12 11v10" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg></span><div><ItemIdentity line={line} />{line.quantity_policy.warning_codes.length > 0 && <small className="warning-text">{t("单位待核对")}</small>}</div></div></td><td className="numeric">{line.quantity}</td><td className={`numeric ${isZeroQuantity(line.delivered_quantity) ? "muted" : "delivered"}`}>{line.delivered_quantity}<Progress line={line} /></td><td className="numeric remaining"><span>{line.remaining_quantity}</span></td><td className="quantity-unit" title={line.canonical_unit ?? line.source_unit ?? undefined}>{displayUnit(line.canonical_unit ?? line.source_unit)}</td><td><button className="text-button" onClick={() => onOpen(line.order_id)} aria-label={t("查看 {0} 第{1}行", [line.order_number, line.line_number])}>{t("查看订单 →")}</button></td></tr>)}</tbody>)}
      </table></div>
      <div className="mobile-lines">{Array.from(groups.values()).map(({ order, lines }) => <section className="mobile-order-group" key={order.order_id}><div className="mobile-order-heading"><strong>{order.customer_name}</strong><span>{order.order_number} · {order.business_date}</span>{status === "deleted" && <span className="danger-text">{t("已删除")}</span>}</div>{lines.map(line => <article key={line.id}><ItemIdentity line={line} /><div className="mobile-order-quantities"><span>{t("订购")}<strong>{line.quantity}</strong></span><span>{t("已交")}<strong className={isZeroQuantity(line.delivered_quantity) ? "muted" : "delivered"}>{line.delivered_quantity}</strong></span><span>{t("还需交付")}<strong className="remaining">{line.remaining_quantity} {displayUnit(line.canonical_unit ?? line.source_unit)}</strong></span></div><Progress line={line} />{line.quantity_policy.warning_codes.length > 0 && <p className="warning-text">{t("单位待核对")}</p>}<button className="text-button" onClick={() => onOpen(line.order_id)} aria-label={t("查看 {0} 第{1}行", [line.order_number, line.line_number])}>{t("查看订单 →")}</button></article>)}</section>)}</div>
      <div className="list-footer"><span>{t("已显示{0} 条明细", [(items.length) ?? ""])}</span>{cursor && <button className="secondary" disabled={busy} onClick={() => void load(cursor)}>{busy ? t("读取中…") : t("加载更多")}</button>}</div>
    </>}
    </section>
  </section>;
}
