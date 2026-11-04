import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Material, type PurchaseOrder, type PurchaseReceipt, type Schemas, type Supplier } from "../api";
import { getLocale, msg, t, type UiMessage } from "../i18n";
import { displayUnit, isZeroQuantity, quantityExceeds } from "../units";
import { MaterialSelect } from "./MaterialSelect";
import { SupplierSelect } from "./SupplierSelect";
import { PurchaseOrderEntry } from "./PurchaseOrderEntry";
import "./purchasing.css";

type Tab = "orders" | "receipts" | "suppliers";
type Mode = "supplier" | "direct" | "receive" | "close" | "void";
type OrderHeader = Schemas["PurchaseOrderHeader"];
type ReceiptHeader = Schemas["PurchaseReceiptHeader"];
type DraftLine = { material: Material; quantity: string };
const tabs: { id: Tab; label: string }[] = [{ id: "orders", label: "采购单" }, { id: "receipts", label: "收料单" }, { id: "suppliers", label: "供应商" }];
function today() { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`; }
function positive(value: string) { return /^\d+(?:\.\d{1,3})?$/.test(value) && !isZeroQuantity(value); }


export function Purchasing({ canWrite, onGuardChange, onUnsavedChange, onRawInventory, onRawMaterials, selectedReceipt }: {
  canWrite: boolean; onGuardChange: (value: boolean) => void; onUnsavedChange: (value: boolean) => void; onRawInventory: () => void; onRawMaterials: () => void; selectedReceipt?: string;
}) {
  const [tab, setTab] = useState<Tab>("orders");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [orders, setOrders] = useState<OrderHeader[]>([]);
  const [receipts, setReceipts] = useState<ReceiptHeader[]>([]);
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [receipt, setReceipt] = useState<PurchaseReceipt | null>(null);
  const [mode, setMode] = useState<Mode | null>(null);
  const [entry, setEntry] = useState<"manual" | "file" | null>(null);
  const [entryLocked, setEntryLocked] = useState(false);
  const [entryDirty, setEntryDirty] = useState(false);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [supplierDraft, setSupplierDraft] = useState<Schemas["SupplierInput"]>({ full_name: "" });
  const [active, setActive] = useState(true);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [receiveQuantities, setReceiveQuantities] = useState<Record<string, string>>({});
  const [day, setDay] = useState(today);
  const [number, setNumber] = useState("");
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  // The closure owns an immutable body and key. A failed replay never replaces it.
  const pending = useRef<{ key: string; execute: (key: string) => Promise<void> } | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const locked = busy || uncertain;
  const guarded = mode !== null || entryLocked || locked;
  useEffect(() => { onGuardChange(guarded); return () => onGuardChange(false); }, [guarded, onGuardChange]);
  useEffect(() => { onUnsavedChange(entryDirty); return () => onUnsavedChange(false); }, [entryDirty, onUnsavedChange]);
  useEffect(() => {
    if (!guarded && !entryDirty) return;
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", leave); return () => window.removeEventListener("beforeunload", leave);
  }, [guarded, entryDirty]);
  useEffect(() => { if (mode) heading.current?.focus(); }, [mode]);
  useEffect(() => {
    if (!selectedReceipt) return;
    let live = true; setBusy(true); setTab("receipts");
    api.purchaseReceipt(selectedReceipt).then(result => { if (live) setReceipt(result); })
      .catch(failure => { if (live) setError(message(failure)); }).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [selectedReceipt]);
  useEffect(() => {
    let live = true; setLoading(true); setError("");
    const read = tab === "orders" ? api.purchaseOrders(filter, offset).then(page => { if (live) { setOrders(page.items); setTotal(page.total); } })
      : tab === "receipts" ? api.purchaseReceipts(filter, offset).then(page => { if (live) { setReceipts(page.items); setTotal(page.total); } })
      : api.suppliers(filter, offset).then(page => { if (live) { setSuppliers(page.items); setTotal(page.total); } });
    read.catch(failure => { if (live) { setError(message(failure)); setOrders([]); setReceipts([]); setSuppliers([]); setTotal(0); } }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [tab, filter, offset, refresh]);

  function begin(next: Mode, current?: Supplier) {
    if (guarded) return;
    setMode(next); setEditing(current ?? null); setSupplier(null); setActive(current?.active ?? true);
    setSupplierDraft(current ? { full_name: current.full_name, contact: current.contact ?? null, phone: current.phone ?? null, address: current.address ?? null, note: current.note ?? null } : { full_name: "" });
    setLines([]); setReceiveQuantities({}); setDay(today()); setNumber(""); setNote(""); setReason(""); setError(""); setNotice(""); pending.current = null;
  }
  async function detail(kind: "order" | "receipt", id: string) {
    if (guarded || loading) return;
    setBusy(true); setError(""); setNotice("");
    try { if (kind === "order") { setOrder(await api.purchaseOrder(id)); setReceipt(null); } else { setReceipt(await api.purchaseReceipt(id)); setOrder(null); } }
    catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  function addMaterial(material: Material) {
    if (locked || lines.length >= 200) return;
    if (lines.some(line => line.material.id === material.id)) { setError(msg("这条原料已在明细中，请修改对应数量。")); return; }
    setLines(old => [...old, { material, quantity: "" }]); setError("");
  }
  const receiptLines = order?.lines.filter(line => (receiveQuantities[line.id] ?? "").trim() !== "") ?? [];
  const valid = mode === "supplier" ? !!supplierDraft.full_name.trim()
    : mode === "close" || mode === "void" ? !!reason.trim()
    : mode === "receive" ? receiptLines.length > 0 && receiptLines.every(line => positive(receiveQuantities[line.id] ?? "") && !quantityExceeds(receiveQuantities[line.id] ?? "", line.remaining_quantity))
    : !!supplier?.active && lines.length > 0 && lines.every(line => positive(line.quantity) && !!line.material.unit);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy || !canWrite || !mode || (!uncertain && !valid)) return;
    if (!uncertain) {
      const key = crypto.randomUUID();
      if (mode === "supplier") {
        const body = { ...supplierDraft, full_name: supplierDraft.full_name.trim() };
        const update = editing ? { ...body, active, expected_version: editing.version } : null;
        const id = editing?.id;
        pending.current = { key, execute: async replayKey => { if (id && update) await api.updateSupplier(id, update, replayKey); else await api.createSupplier(body, replayKey); } };
      } else if ((mode === "direct" && supplier) || (mode === "receive" && order)) {
        const body: Schemas["PurchaseReceiptInput"] = { supplier_id: mode === "receive" ? order!.supplier_id : supplier!.id, purchase_order_id: mode === "receive" ? order!.id : null, business_date: day, number: number.trim() || null, note: note.trim() || null,
          lines: mode === "receive" ? receiptLines.map(line => ({ purchase_line_id: line.id, quantity: receiveQuantities[line.id]! })) : lines.map(line => ({ material_id: line.material.id, quantity: line.quantity })) };
        pending.current = { key, execute: async replayKey => { setReceipt(await api.createPurchaseReceipt(body, replayKey)); setOrder(null); setTab("receipts"); setOffset(0); setFilter(""); setQuery(""); } };
      } else if (mode === "close" && order) {
        const id = order.id; const body = { expected_version: order.version, reason: reason.trim() };
        pending.current = { key, execute: async replayKey => { setOrder(await api.closePurchaseOrder(id, body, replayKey)); } };
      } else if (mode === "void" && receipt) {
        const id = receipt.id; const body = { expected_version: receipt.version, reason: reason.trim() };
        pending.current = { key, execute: async replayKey => { setReceipt(await api.voidPurchaseReceipt(id, body, replayKey)); } };
      }
    }
    const command = pending.current; if (!command) return;
    setBusy(true); setError("");
    try { await command.execute(command.key); pending.current = null; setUncertain(false); setMode(null); setNotice(msg("采购记录已保存。")); setRefresh(value => value + 1); }
    catch (failure) { setError(message(failure)); setUncertain(previous => previous || !(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }
  const formTitle = mode === "supplier" ? editing ? t("维护供应商") : t("新建供应商")  : mode === "direct" ? t("直接收料") : mode === "receive" ? t("按采购单收料") : mode === "close" ? t("关闭采购余量") : t("作废收料单");
  const count = tab === "orders" ? orders.length : tab === "receipts" ? receipts.length : suppliers.length;
  return <section className="work-page purchasing-page">
    <div className="page-heading"><div><h1>{t("采购与收料")}</h1><p>{t("采购记录订购数量，收料才增加原料库存。")}</p></div><div className="actions"><button className="secondary" disabled={guarded} onClick={onRawInventory}>{t("原料库存")}</button><button className="text-button" disabled={guarded} onClick={onRawMaterials}>{t("原料档案")}</button></div></div>
    <div className="actions purchasing-tabs" aria-label={t("采购分类")}>{tabs.map(item => <button key={item.id} className={tab === item.id ? "" : "secondary"} aria-pressed={tab === item.id} disabled={guarded || loading} onClick={() => { if (entryDirty && !window.confirm(t("离开后，未保存的采购内容会丢失。确定离开吗？"))) return; setEntry(null); setTab(item.id); setOrder(null); setReceipt(null); setQuery(""); setFilter(""); setOffset(0); setNotice(""); }}>{t(item.label)}</button>)}</div>
    {error && <p role="alert" className="error">{t(error)}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
    {entry && <PurchaseOrderEntry start={entry} onLockedChange={setEntryLocked} onDirtyChange={setEntryDirty} onCancel={() => { setEntry(null); setError(""); }} onSaved={(result, existing) => { setOrder(result); setReceipt(null); setEntry(null); setNotice(existing ? msg("已打开这个原件对应的采购单。") : msg("采购单已保存，可打印或按需登记收料。")); setRefresh(value => value + 1); }} />}
    {(order || receipt) && <button className="back-button" disabled={guarded} onClick={() => { setOrder(null); setReceipt(null); setRefresh(value => value + 1); }}>{t("返回列表")}</button>}
    {!entry && order && <section className="work-panel purchasing-detail"><div className="row-between"><h2>{order.number}</h2><span>{order.status === "closed" ? t("已关闭") : t("采购中")}</span></div><p>{order.supplier_name} · {order.business_date}</p>{order.note && <p>{order.note}</p>}{order.close_reason && <p>{t("关闭原因：{0}", [order.close_reason])}</p>}
      <div className="table-wrap"><table><thead><tr><th>{t("原料")}</th><th>{t("单位")}</th><th className="numeric">{t("原订数量")}</th><th className="numeric">{t("有效已收")}</th><th className="numeric">{t("未收数量")}</th></tr></thead><tbody>{order.lines.map(line => <tr key={line.id}><td><strong>{line.own_code} · {line.material_name}</strong><small>{line.specification}</small></td><td>{displayUnit(line.canonical_unit)}</td><td className="numeric">{line.ordered_quantity}</td><td className="numeric">{line.received_quantity}</td><td className="numeric">{line.remaining_quantity}</td></tr>)}</tbody></table></div>
      <div className="actions"><a className="secondary button-link" href={`/api/v1/purchase-orders/${order.id}/print?locale=${getLocale()}`} target="_blank" rel="noreferrer">{t("打印采购单")}</a>{order.source_id && <a href={`/api/v1/sources/${order.source_id}/download`}>{t("下载原件")}</a>}</div>
      <details className="purchase-saved-prices"><summary>{t("采购金额与抬头")}</summary>{order.buyer_name && <p>{t("采购方：{0}", [order.buyer_name])}</p>}<p>{t("币种：{0}", [order.currency ?? t("未填写")])}</p><div className="table-wrap"><table><thead><tr><th>{t("原料")}</th><th>{t("单价")}</th><th>{t("金额")}</th></tr></thead><tbody>{order.lines.map(line => <tr key={line.id}><td>{line.material_name}</td><td>{line.source_unit_price ?? "—"}</td><td>{line.source_amount ?? "—"}</td></tr>)}</tbody></table></div><p>{t("合计：{0}", [order.total_amount ?? t("含未定金额项目")])}</p></details>
      {order.status === "closed" && <p className="muted">{t("采购已关闭，未收数量不再接收新收料。")}</p>}{canWrite && order.status === "open" && <div className="actions"><button disabled={guarded || order.lines.every(line => isZeroQuantity(line.remaining_quantity))} onClick={() => begin("receive")}>{t("按采购单收料")}</button><button className="secondary" disabled={guarded} onClick={() => begin("close")}>{t("关闭采购余量")}</button></div>}
    </section>}
    {receipt && <section className="work-panel purchasing-detail"><div className="row-between"><h2>{receipt.number}</h2><span>{receipt.status === "void" ? t("已作废") : t("有效")}</span></div><p>{receipt.supplier_name} · {receipt.business_date} · {receipt.purchase_order_id ? t("按采购单收料") : t("直接收料")}</p>{receipt.note && <p>{receipt.note}</p>}{receipt.void_reason && <p>{t("作废原因：{0}", [receipt.void_reason])}</p>}
      {receipt.purchase_order_id && <button className="text-button" disabled={guarded} onClick={() => void detail("order", receipt.purchase_order_id!)}>{t("查看关联采购单")}</button>}
      <div className="table-wrap"><table className="purchasing-receipt-lines"><thead><tr><th>{t("原料")}</th><th className="numeric">{t("收料数量")}</th><th>{t("单位")}</th></tr></thead><tbody>{receipt.lines.map(line => <tr key={line.id}><td><strong>{line.own_code} · {line.material_name}</strong><small>{line.specification}</small></td><td className="numeric">{line.quantity}</td><td>{displayUnit(line.canonical_unit)}</td></tr>)}</tbody></table></div>
      {canWrite && receipt.status === "active" && <button className="secondary" disabled={guarded} onClick={() => begin("void")}>{t("作废收料单")}</button>}
    </section>}
    {mode && <section className="work-panel purchasing-form"><h2 ref={heading} tabIndex={-1}>{formTitle}</h2><form onSubmit={submit}>
      {mode === "supplier" ? <><div className="form-grid">{([{ key: "full_name", label: "供应商名称", max: 200 }, { key: "contact", label: "联系人", max: 200 }, { key: "phone", label: "电话", max: 100 }, { key: "address", label: "地址", max: 500 }] as const).map(field => <label key={field.key}>{t(field.label)}<input value={supplierDraft[field.key] ?? ""} required={field.key === "full_name"} maxLength={field.max} disabled={locked} onChange={e => setSupplierDraft(old => ({ ...old, [field.key]: e.target.value }))} /></label>)}</div><label>{t("备注")}<textarea maxLength={1000} value={supplierDraft.note ?? ""} disabled={locked} onChange={e => setSupplierDraft(old => ({ ...old, note: e.target.value }))} /></label>{editing && <label className="checkbox"><input type="checkbox" checked={active} disabled={locked} onChange={e => setActive(e.target.checked)} />{t("允许新采购和收料选择此供应商")}</label>}</>
      : mode === "close" || mode === "void" ? <>{mode === "void" && <p className="warning">{t("整张收料单将全量冲回库存。余额不足时整单拒绝；此操作仅用于录错更正。")}</p>}<label>{t("原因")}<textarea value={reason} maxLength={500} required disabled={locked} onChange={e => setReason(e.target.value)} /></label></>
      : <>
        {mode === "direct" && <SupplierSelect selected={supplier} disabled={locked} onSelect={setSupplier} />}
        <div className="form-grid"><label>{t("业务日期")}<input type="date" required disabled={locked} value={day} onChange={e => setDay(e.target.value)} /></label><label>{t("单号")}<input value={number} maxLength={100} disabled={locked} placeholder={t("留空自动编号")} onChange={e => setNumber(e.target.value)} /></label></div>
        {mode === "receive" && order ? <><p>{t("供应商：{0}", [order.supplier_name])}</p><p className="muted">{t("只填写本次实际收到的数量；空白行本次不收。")}</p><div className="table-wrap"><table><thead><tr><th>{t("原料")}</th><th>{t("单位")}</th><th className="numeric">{t("未收数量")}</th><th>{t("本次收料")}</th></tr></thead><tbody>{order.lines.map(line => <tr key={line.id}><td>{line.own_code} · {line.material_name}<small>{line.specification}</small></td><td>{displayUnit(line.canonical_unit)}</td><td className="numeric">{line.remaining_quantity}</td><td><input aria-label={t("{0} 本次收料数量", [line.own_code])} inputMode="decimal" maxLength={64} value={receiveQuantities[line.id] ?? ""} disabled={locked || isZeroQuantity(line.remaining_quantity)} onChange={e => setReceiveQuantities(old => ({ ...old, [line.id]: e.target.value }))} aria-invalid={!!receiveQuantities[line.id] && (!positive(receiveQuantities[line.id]!) || quantityExceeds(receiveQuantities[line.id]!, line.remaining_quantity))} /></td></tr>)}</tbody></table></div></>
        : <><h3>{t("原料明细")}</h3>{!lines.length && <p className="muted">{t("请从下方选择原料。没有档案时，先取消并到原料档案建档。")}</p>}{lines.map((line, index) => <div className="purchasing-draft-line" key={line.material.id}><div><strong>{line.material.own_code} · {line.material.name}</strong><small>{line.material.specification}</small></div><label>{t("数量（{0}）", [displayUnit(line.material.unit)])}<input inputMode="decimal" maxLength={64} required value={line.quantity} disabled={locked} onChange={e => setLines(old => old.map((item, i) => i === index ? { ...item, quantity: e.target.value } : item))} aria-invalid={!!line.quantity && !positive(line.quantity)} /></label><button type="button" className="text-button" disabled={locked} aria-label={t("移除原料 {0}", [line.material.own_code])} onClick={() => setLines(old => old.filter((_, i) => i !== index))}>{t("移除")}</button></div>)}<MaterialSelect materialKind="raw" disabled={locked || lines.length >= 200} onSelect={addMaterial} actionLabel={t("加入明细")} /></>}
        {(mode === "direct" || mode === "receive") && <p className="muted">{t("收料前须在原料库存明确开账，允许零开账。未开账不代表零库存。")}</p>}
        <label>{t("备注")}<textarea value={note} maxLength={1000} disabled={locked} onChange={e => setNote(e.target.value)} /></label>
      </>}
      {uncertain && <p className="warning" role="status">{t("结果待确认，请保留此页并重试同一次保存。")}</p>}
      <div className="actions"><button disabled={busy || !canWrite || (!uncertain && !valid)}>{busy ? t("保存中…") : uncertain ? t("重试本次保存") : t("确认保存")}</button><button type="button" className="secondary" disabled={locked} onClick={() => { setMode(null); setError(""); pending.current = null; }}>{t("取消")}</button></div>
    </form></section>}
    {!order && !receipt && !mode && !entry && <section className="work-panel">
      <div className="row-between"><form className="material-search" onSubmit={e => { e.preventDefault(); setFilter(query.trim()); setOffset(0); setRefresh(value => value + 1); }}><label>{t("查找")}<input value={query} disabled={locked} onChange={e => setQuery(e.target.value)} /></label><button className="secondary" disabled={locked || loading}>{t("查找")}</button></form>{canWrite && <div className="actions">{tab === "orders" && <button className="secondary" disabled={locked || loading} onClick={() => { setEntry("file"); setNotice(""); }}>{t("导入采购单")}</button>}<button disabled={locked || loading} onClick={() => { if (tab === "orders") { setEntry("manual"); setNotice(""); } else begin(tab === "receipts" ? "direct" : "supplier"); }}>{tab === "orders" ? t("新建采购单") : tab === "receipts" ? t("直接收料") : t("新建供应商")}</button></div>}</div>
      {loading ? <p role="status">{t("正在读取…")}</p> : !count ? <p className="empty-copy">{filter ? t("没有找到匹配记录。") : tab === "suppliers" ? t("还没有供应商，请先建档。") : t("还没有采购或收料记录。可以直接新建。")}</p> : <div className="table-wrap"><table><thead><tr><th>{tab === "suppliers" ? t("供应商") : t("单号")}</th><th>{tab === "suppliers" ? t("联系人 / 电话") : t("供应商")}</th>{tab !== "suppliers" && <th>{t("业务日期")}</th>}<th>{t("状态")}</th><th>{t("操作")}</th></tr></thead><tbody>
        {tab === "suppliers" ? suppliers.map(item => <tr key={item.id}><td><strong>{item.full_name}</strong><small>{item.address}</small><small>{item.note}</small></td><td>{item.contact}<small>{item.phone}</small></td><td>{item.active ? t("可用") : t("已停用")}</td><td>{canWrite && <button className="text-button" disabled={locked} onClick={() => begin("supplier", item)}>{t("维护")}</button>}</td></tr>)
        : tab === "orders" ? orders.map(item => <tr key={item.id}><td>{item.number}</td><td>{item.supplier_name}</td><td>{item.business_date}</td><td>{item.status === "closed" ? t("已关闭") : t("采购中")}</td><td><button className="text-button" disabled={locked} onClick={() => void detail("order", item.id)}>{t("查看")}</button></td></tr>)
        : receipts.map(item => <tr key={item.id}><td>{item.number}<small>{item.purchase_order_id ? t("按采购单收料") : t("直接收料")}</small></td><td>{item.supplier_name}</td><td>{item.business_date}</td><td>{item.status === "void" ? t("已作废") : t("有效")}</td><td><button className="text-button" disabled={locked} onClick={() => void detail("receipt", item.id)}>{t("查看")}</button></td></tr>)}
      </tbody></table></div>}
      <div className="actions">{offset > 0 && <button className="secondary" disabled={locked || loading} onClick={() => setOffset(Math.max(0, offset - 50))}>{t("上一页")}</button>}{offset + count < total && <button className="secondary" disabled={locked || loading} onClick={() => setOffset(offset + 50)}>{t("下一页")}</button>}{!loading && error && <button className="secondary" disabled={locked} onClick={() => setRefresh(value => value + 1)}>{t("重新读取")}</button>}</div>
    </section>}
    {busy && <p className="muted" role="status">{t("正在处理…")}</p>}
  </section>;
}
