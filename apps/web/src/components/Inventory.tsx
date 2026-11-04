import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type InventoryDetail, type InventoryEntry, type InventoryItem, type RawInventoryEntry, type Schemas } from "../api";
import { getLocale, msg, t, type UiMessage } from "../i18n";
import { quantityExceeds } from "../units";
import { MaterialSelect } from "./MaterialSelect";
import "./inventory.css";

const kinds = { opening: "开账", receipt: "入库", count: "实盘调整", delivery: "送货扣减", skip: "送货未同步", delivery_void: "送货作废冲回", receipt_void: "入库作废冲回", purchase_receipt: "采购收料", purchase_receipt_void: "收料作废冲回", material_issue: "领用", material_return: "退料", production_receipt: "生产完工入库", production_receipt_void: "完工作废冲回" };
type Entry = InventoryEntry | RawInventoryEntry;
type StockDetail = Omit<InventoryDetail, "entries"> & { entries: Entry[] };
type Mode = "open" | "receipt" | "count" | "void" | "issue" | "return";
type Pending = { mode: Mode; materialId: string; entryId?: string; body: Schemas["InventoryCountInput"]; key: string };

function localDay() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function Inventory({ canWrite, onGuardChange, onDelivery, materialKind = "finished", onPurchasing, onRawMaterials, onPurchaseReceipt, onProduction }: {
  canWrite: boolean; onGuardChange: (value: boolean) => void; onDelivery: (id: string) => void;
  materialKind?: "finished" | "raw"; onPurchasing?: () => void; onRawMaterials?: () => void; onPurchaseReceipt?: (id: string) => void; onProduction?: (id: string) => void;
}) {
  const raw = materialKind === "raw";
  const readList = raw ? api.rawInventoryList : api.inventoryList;
  const readDetail = raw ? api.rawInventory : api.inventory;
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [detail, setDetail] = useState<StockDetail | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [mode, setMode] = useState<Mode | null>(null);
  const [entry, setEntry] = useState<Entry | null>(null);
  const [quantity, setQuantity] = useState("");
  const [day, setDay] = useState(localDay);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const pending = useRef<Pending | null>(null);
  const requestedMaterial = useRef<string | null>(null);
  const locked = busy || uncertain;

  useEffect(() => { onGuardChange(busy || mode !== null || uncertain); return () => onGuardChange(false); }, [busy, mode, uncertain, onGuardChange]);
  useEffect(() => {
    if (!mode && !uncertain) return;
    const leave = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [mode, uncertain]);
  useEffect(() => {
    let live = true;
    setBusy(true);
    readList().then(page => { if (live) { setItems(page.items); setCursor(page.next_cursor); } })
      .catch(failure => { if (live) setError(message(failure)); }).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [readList]);

  async function loadList(more = false) {
    setBusy(true); setError("");
    try { const page = await readList(more ? cursor ?? undefined : undefined); setItems(old => more ? [...old, ...page.items] : page.items); setCursor(page.next_cursor); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function loadDetail(id: string, more = false) {
    requestedMaterial.current = id;
    setBusy(true); setError(""); setNotice("");
    if (!more && detail?.material.id !== id) setDetail(null);
    try { const next = await readDetail(id, more ? detail?.next_cursor ?? undefined : undefined); setDetail(old => more && old ? { ...next, entries: [...old.entries, ...next.entries] } : next); setChoosing(false); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  function begin(next: Mode, original?: Entry) {
    setMode(next); setEntry(original ?? null); setQuantity(""); setReason(""); setDay(localDay()); setError(""); setNotice(""); pending.current = null;
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!detail || !mode || busy) return;
    if (!uncertain || !pending.current) pending.current = { mode, materialId: detail.material.id, ...(entry ? { entryId: entry.id } : {}), key: crypto.randomUUID(), body: { quantity, business_date: day, reason, expected_version: detail.account?.version ?? 1 } };
    const command = pending.current;
    setBusy(true); setError("");
    try {
      const { expected_version, ...basic } = command.body;
      const result = command.mode === "open" ? await (raw ? api.openRawInventory : api.openInventory)(command.materialId, basic, command.key)
        : command.mode === "receipt" ? await api.receiveInventory(command.materialId, basic, command.key)
        : command.mode === "count" ? await (raw ? api.countRawInventory : api.countInventory)(command.materialId, { ...basic, expected_version }, command.key)
        : command.mode === "issue" ? await api.issueRawInventory(command.materialId, { ...basic, reason: command.body.reason }, command.key)
        : command.mode === "return" ? await api.returnRawInventory(command.entryId!, { ...basic, reason: command.body.reason }, command.key)
        : await api.voidInventoryReceipt(command.entryId!, command.body.reason, command.key);
      setDetail(old => old ? { ...old, account: result.account, entries: [result.entry, ...old.entries.map(item => item.id === result.entry.reverses_id ? { ...item, reversed_by: result.entry.id } : item)] } : old);
      pending.current = null; setUncertain(false); setMode(null); setEntry(null); setNotice(msg("库存记录已保存。"));
      if (command.mode === "return") {
        try { setDetail(await readDetail(command.materialId)); }
        catch (failure) {
          // A saved return changes the original issue's remaining return allowance.
          // Require a fresh detail read before exposing another action on that issue.
          setDetail(null); setChoosing(true); setError(message(failure));
        }
      }
    } catch (failure) { setError(message(failure)); setUncertain(previous => previous || !(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }
  const title = mode === "open" ? t("按当前实物开账") : mode === "receipt" ? t("登记实际入库") : mode === "count" ? t("登记实盘数量") : mode === "issue" ? t("登记领用") : mode === "return" ? t("登记退料") : t("作废入库");

  return <section className="work-page inventory-page">
    {(detail || choosing) && <button className="back-button" disabled={locked || mode !== null} onClick={() => { requestedMaterial.current = null; setDetail(null); setChoosing(false); setNotice(""); void loadList(); }}>{raw ? t("返回原料库存") : t("返回成品库存")}</button>}
    <div className="page-heading"><div><h1>{raw ? t("原料库存") : t("成品库存")}</h1><p>{raw ? t("收料增加，领用减少；退料关联原领用。") : t("只记录你选择管理的成品。")}</p></div>{!detail && !choosing && canWrite && <button disabled={locked} onClick={() => { setChoosing(true); setError(""); }}>{raw ? t("开始记录一个原料") : t("开始记录一个成品")}</button>}</div>
    {error && <div role="alert" className="error">{t(error)}{!uncertain && <button type="button" className="text-button" disabled={busy} onClick={() => requestedMaterial.current ? void loadDetail(requestedMaterial.current) : void loadList()}>{t("重新读取库存")}</button>}</div>}
    {notice && <p role="status" className="success">{t(notice)}</p>}
    {busy && <p role="status" className="muted">{t("正在处理…")}</p>}
    {choosing && <section className="work-panel"><h2>{raw ? t("选择要管理的原料") : t("选择要管理的成品")}</h2>{raw && onRawMaterials && <button className="text-button" disabled={locked} onClick={onRawMaterials}>{t("原料建档")}</button>}<MaterialSelect materialKind={materialKind} disabled={locked} onSelect={material => void loadDetail(material.id)} actionLabel={t("查看库存")} /></section>}
    {!detail && !choosing && <section className="work-panel">
      {!busy && !error && !items.length && <p className="empty-state">{raw ? t("还没有原料开始记录库存。未记录不代表库存为零。") : t("还没有成品开始记录库存。未记录不代表库存为零。")}</p>}
      {!!items.length && <div className="table-wrap"><table><thead><tr><th>{raw ? t("原料") : t("成品")}</th><th className="numeric">{t("账面库存")}</th><th>{t("单位")}</th><th>{t("状态")}</th><th>{t("查看")}</th></tr></thead><tbody>{items.map(item => <tr key={item.material.id}><td><strong>{item.material.own_code}</strong><span className="inventory-item-name">{item.material.name}</span><small>{item.material.specification}</small></td><td className="numeric">{item.account?.balance ?? t("未管理")}</td><td>{item.account?.canonical_unit}</td><td>{item.account?.negative_balance ? t("账面为负") : item.account?.has_skipped ? t("待核对") : t("已记录")}</td><td><button className="text-button" disabled={locked} onClick={() => void loadDetail(item.material.id)}>{t("查看流水")}</button></td></tr>)}</tbody></table></div>}
      {cursor && <button className="secondary" disabled={locked} onClick={() => void loadList(true)}>{raw ? t("加载更多原料") : t("加载更多成品")}</button>}
    </section>}
    {detail && <>
      <section className="work-panel inventory-summary"><div><h2>{detail.material.name}</h2><p className="muted">{detail.material.own_code} · {detail.material.specification || t("规格暂缺")}</p></div>
        {detail.account ? <><p className="inventory-balance"><span>{t("账面库存")}</span><strong className={detail.account.negative_balance ? "danger-text" : undefined}>{detail.account.balance}</strong><span>{detail.account.canonical_unit}</span></p>
          {detail.account.has_skipped && <p className="warning" role="status">{t("有送货未同步，余额待核对。实盘可建立新的可信起点。")}</p>}
          {detail.account.negative_balance && <p className="warning" role="status">{t("账面为负，请按实际数量补登记尚未入账的入库。")}</p>}
          {canWrite && mode === null && <div className="actions">{raw ? <><button disabled={locked} onClick={() => begin("issue")}>{t("登记领用")}</button><button className="secondary" disabled={locked} onClick={onPurchasing}>{t("供应商收料")}</button></> : <button disabled={locked} onClick={() => begin("receipt")}>{t("登记入库")}</button>}<button className="secondary" disabled={locked} onClick={() => begin("count")}>{t("实盘核对")}</button></div>}</>
          : <><p className="muted">{t("尚未管理库存，当前数量未知。")}</p>{canWrite && mode === null && <button disabled={locked || !detail.material.active} onClick={() => begin("open")}>{t("按当前实物开始记录")}</button>}</>}
      </section>
      {mode && <form className="work-panel inventory-form" onSubmit={submit}><h2>{title}</h2>
        {mode === "open" && <p className="muted">{raw ? t("填写现在实际在库数量，可为零；已包含的旧收料不用再补。") : t("填写现在实际在库数量，可为零。以前的送货不会追扣，已包含的旧入库不用再补。")}</p>}
        {mode === "receipt" && <p className="muted">{t("只登记这次实际入库的数量，不自动填平负数。")}</p>}
        {mode === "count" && <p className="muted">{raw ? t("填写现在实盘总量，系统按差额调整，原出入库记录保留。") : t("填写现在实盘总量，系统按差额调整；先前跳过的送货记录仍保留。")}</p>}
        {mode === "issue" && <p className="muted">{t("填写本次领出的原料数量与用途，不能超过当前库存。")}</p>}
        {mode === "return" && <p className="muted">{t("原领用 {0}，已退 {1}。本次退料将回到库存。", [entry?.delta.replace("-", "") ?? "", entry && "returned_quantity" in entry ? entry.returned_quantity ?? "0" : "0"])}</p>}
        {mode === "void" && <p className="warning">{t("撤回这笔入库的 {0} {1}，原记录保留。不能用作废登记真实退货。", [entry?.delta ?? "", detail.account?.canonical_unit ?? ""])}</p>}
        {mode !== "void" && <div className="form-grid"><label>{mode === "receipt" ? t("本次入库数量") : mode === "issue" ? t("本次领用数量") : mode === "return" ? t("本次退料数量") : t("实际在库数量")}<input inputMode="decimal" required maxLength={64} value={quantity} onChange={e => setQuantity(e.target.value)} disabled={locked} /><small>{detail.account?.canonical_unit ?? detail.material.unit ?? t("单位待核对")}</small></label><label>{t("实际业务日期")}<input type="date" required value={day} onChange={e => setDay(e.target.value)} disabled={locked} /></label></div>}
        <label>{mode === "issue" ? t("用途 / 领用对象") : mode === "count" || mode === "void" || mode === "return" ? t("操作原因") : t("备注（可选）")}<textarea required={mode === "count" || mode === "void" || mode === "issue" || mode === "return"} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} disabled={locked} rows={2} /></label>
        {uncertain && <p className="warning" role="status">{t("结果待确认，请保留此页并重试同一次保存。")}</p>}
        <div className="actions"><button disabled={busy}>{busy ? t("保存中…") : uncertain ? t("重试本次保存") : title}</button><button type="button" className="secondary" disabled={locked} onClick={() => { setMode(null); setError(""); pending.current = null; }}>{t("取消")}</button></div>
      </form>}
      <section className="work-panel inventory-history"><h2>{t("库存流水")}</h2><p className="muted">{t("按登记顺序排列；补录的业务日期不会重排历史。")}</p>
        {!detail.entries.length ? <p className="empty-state">{t("暂无库存流水")}</p> : <div className="table-wrap"><table><thead><tr><th>{t("业务日期 / 登记时间")}</th><th>{t("动作")}</th><th className="numeric">{t("变动数量")}</th><th className="numeric">{t("记账后余额")}</th><th>{t("原因 / 关联记录")}</th><th>{t("操作")}</th></tr></thead><tbody>{detail.entries.map(item => <tr key={item.id} id={`movement-${item.id}`}><td>{raw && <small>{t("流水 #{0}", [item.account_version])}</small>}{item.business_date}<small>{new Date(item.recorded_at).toLocaleString(getLocale())}</small></td><td>{t(kinds[item.kind])}{item.reversed_by && <small>{t("已冲回")}</small>}</td><td className="numeric">{item.delta.startsWith("-") || item.delta === "0" ? item.delta : `+${item.delta}`}</td><td className="numeric">{item.balance_after}</td><td>{item.reason === "USER_SKIPPED" ? t("本次只记送货") : item.reason || "—"}{item.delivery_id && <small><button type="button" className="text-button" disabled={locked || mode !== null} onClick={() => onDelivery(item.delivery_id!)}>{t("查看送货")}</button></small>}{"purchase_receipt_id" in item && item.purchase_receipt_id && <small><button type="button" className="text-button" disabled={locked || mode !== null} onClick={() => onPurchaseReceipt?.(item.purchase_receipt_id!)}>{t("收料单 {0}", [item.purchase_receipt_number ?? ""])}</button></small>}{"returns_issue_id" in item && item.returns_issue_id && <small>{t("原领用流水 #{0}", [item.returns_issue_version ?? ""])}</small>}{item.kind === "material_issue" && <small>{t("已退料：{0}", [item.returned_quantity ?? "0"])}</small>}{item.production_order_id && onProduction && <small><button type="button" className="text-button" disabled={locked || mode !== null} onClick={() => onProduction(item.production_order_id!)}>{t("查看生产单")}</button></small>}{item.reverses_id && <small>{t("原记录保留")}</small>}</td><td>{canWrite && item.kind === "material_issue" && quantityExceeds(item.delta.slice(1), item.returned_quantity ?? "0") && <button className="text-button" disabled={locked || mode !== null} onClick={() => begin("return", item)}>{t("登记退料")}</button>}{canWrite && item.kind === "receipt" && !item.reversed_by && <button className="text-button danger-text" disabled={locked || mode !== null} onClick={() => begin("void", item)}>{t("作废入库")}</button>}</td></tr>)}</tbody></table></div>}
        {detail.next_cursor && <button className="secondary" disabled={locked || mode !== null} onClick={() => void loadDetail(detail.material.id, true)}>{t("加载更多流水")}</button>}
      </section>
    </>}
  </section>;
}
