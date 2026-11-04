import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Material, type OrderDetail, type ProductionOrder, type ProductionIssue, type ProductionCompletion, type Schemas } from "../api";
import { msg, t, type UiMessage } from "../i18n";
import { displayUnit, isZeroQuantity, quantityExceeds } from "../units";
import { MaterialSelect } from "./MaterialSelect";
import "./production.css";

type Mode = "create" | "issue" | "return" | "complete" | "void" | "close";
const titles: Record<Mode, string> = { create: "安排生产", issue: "生产领料", return: "生产退料", complete: "登记完工", void: "作废完工", close: "关闭生产单" };
const exact = (value: string) => /^\d+(?:\.\d{1,3})?$/.test(value);
const positive = (value: string) => exact(value) && !isZeroQuantity(value);
function today() { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`; }

export function Production({ canWrite, onGuardChange, onOrder, onOrders, onInventory, onRawInventory, orderId, selected }: {
  canWrite: boolean; onGuardChange: (value: boolean) => void; onOrder: (id: string) => void;
  onOrders: () => void; onInventory: () => void; onRawInventory: () => void; orderId?: string; selected?: string;
}) {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [items, setItems] = useState<ProductionOrder[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<UiMessage>("");
  const [selectedId, setSelectedId] = useState<string | null>(selected ?? null);
  const [detail, setDetail] = useState<ProductionOrder | null>(null);
  const [issues, setIssues] = useState<Schemas["ProductionIssuePage"] | null>(null);
  const [completions, setCompletions] = useState<Schemas["ProductionCompletionPage"] | null>(null);
  const [issueOffset, setIssueOffset] = useState(0);
  const [completionOffset, setCompletionOffset] = useState(0);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<UiMessage>("");
  const [mode, setMode] = useState<Mode | null>(null);
  const [lineId, setLineId] = useState("");
  const [material, setMaterial] = useState<Material | null>(null);
  const [returning, setReturning] = useState<ProductionIssue | null>(null);
  const [voiding, setVoiding] = useState<ProductionCompletion | null>(null);
  const [quantity, setQuantity] = useState("");
  const [scrap, setScrap] = useState("0");
  const [day, setDay] = useState(today);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const pending = useRef<{ key: string; execute: (key: string) => Promise<string> } | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const locked = busy || uncertain;
  const guarded = mode !== null || locked;
  const ready = detail !== null && !detailLoading && !detailError;
  const open = ready && detail.status === "open" && detail.source_current;

  useEffect(() => { onGuardChange(guarded); return () => onGuardChange(false); }, [guarded, onGuardChange]);
  useEffect(() => {
    if (!guarded) return;
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", leave); return () => window.removeEventListener("beforeunload", leave);
  }, [guarded]);
  useEffect(() => { if (mode) { heading.current?.focus(); heading.current?.scrollIntoView({ block: "center" }); } }, [mode]);
  useEffect(() => {
    let live = true; setLoading(true); setListError("");
    Promise.all([api.productionOrders(filter, offset, orderId), orderId ? api.detail(orderId) : Promise.resolve(null)])
      .then(([page, source]) => { if (live) { setItems(page.items); setTotal(page.total); setOrder(source); } })
      .catch(failure => { if (live) { setItems([]); setTotal(0); setOrder(null); setListError(message(failure)); } })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [filter, offset, orderId, refresh]);
  useEffect(() => {
    let live = true; setDetail(null); setIssues(null); setCompletions(null); setDetailError("");
    if (!selectedId) { setDetailLoading(false); return; }
    setDetailLoading(true);
    Promise.all([api.productionOrder(selectedId), api.productionIssues(selectedId, issueOffset), api.productionCompletions(selectedId, completionOffset)])
      .then(([current, raw, completed]) => { if (live) { setDetail(current); setIssues(raw); setCompletions(completed); } })
      .catch(failure => { if (live) setDetailError(message(failure)); })
      .finally(() => { if (live) setDetailLoading(false); });
    return () => { live = false; };
  }, [selectedId, issueOffset, completionOffset, refresh]);

  function select(id: string) { if (guarded) return; setSelectedId(id); setIssueOffset(0); setCompletionOffset(0); setError(""); setNotice(""); }
  function begin(next: Mode, source?: ProductionIssue | ProductionCompletion) {
    if (guarded || !canWrite || (next !== "create" && !ready)) return;
    setMode(next); setMaterial(null); setLineId(""); setQuantity(""); setScrap("0"); setDay(today());
    setReason(""); setNote(""); setError(""); setNotice(""); pending.current = null;
    setReturning(next === "return" ? source as ProductionIssue : null);
    setVoiding(next === "void" ? source as ProductionCompletion : null);
  }
  const line = order?.lines.find(item => item.id === lineId);
  const requiresReason = mode === "issue" || mode === "return" || mode === "close" || mode === "void";
  const valid = mode === "create" ? !!line?.material?.active && !!line.canonical_unit && positive(quantity)
    : mode === "complete" ? exact(quantity) && exact(scrap) && (positive(quantity) || positive(scrap)) && !!detail && !quantityExceeds(quantity, detail.remaining_quantity)
    : mode === "issue" ? !!material && positive(quantity) && !!reason.trim()
    : mode === "return" ? !!returning && positive(quantity) && !quantityExceeds(quantity, returning.outstanding_quantity) && !!reason.trim()
    : !!reason.trim();

  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy || !mode || !canWrite || (!uncertain && !valid)) return;
    if (!uncertain) {
      const key = crypto.randomUUID();
      if (mode === "create" && order && line) {
        const body: Schemas["ProductionInput"] = { order_id: order.id, revision_id: order.revision_id, order_line_id: line.id, expected_order_version: order.version, planned_quantity: quantity, business_date: day, note: note.trim() || null };
        pending.current = { key, execute: async replayKey => (await api.createProduction(body, replayKey)).id };
      } else if (detail) {
        const id = detail.id;
        if (mode === "issue" && material) {
          const body = { material_id: material.id, quantity, business_date: day, reason: reason.trim() };
          pending.current = { key, execute: async replayKey => { await api.issueProduction(id, body, replayKey); return id; } };
        } else if (mode === "return" && returning) {
          const issueId = returning.entry_id; const body = { quantity, business_date: day, reason: reason.trim() };
          pending.current = { key, execute: async replayKey => { await api.returnProduction(id, issueId, body, replayKey); return id; } };
        } else if (mode === "complete") {
          const body = { quantity, scrap_quantity: scrap, business_date: day, note: note.trim() || null };
          pending.current = { key, execute: async replayKey => { await api.completeProduction(id, body, replayKey); return id; } };
        } else if (mode === "void" && voiding) {
          const completionId = voiding.id; const body = { expected_version: voiding.version, reason: reason.trim() };
          pending.current = { key, execute: async replayKey => { await api.voidProduction(id, completionId, body, replayKey); return id; } };
        } else if (mode === "close") {
          const body = { expected_version: detail.version, reason: reason.trim() };
          pending.current = { key, execute: async replayKey => (await api.closeProduction(id, body, replayKey)).id };
        }
      }
    }
    const command = pending.current; if (!command) return;
    setBusy(true); setError("");
    try {
      const id = await command.execute(command.key);
      pending.current = null; setUncertain(false); setMode(null); setNotice(msg("生产记录已保存。"));
      // Clear actionable totals before the separate refresh; a read failure cannot undo a successful write.
      setDetail(null); setIssues(null); setCompletions(null); setSelectedId(id);
      setIssueOffset(0); setCompletionOffset(0); setRefresh(value => value + 1);
    } catch (failure) {
      setError(message(failure));
      const unknown = uncertain || !(failure instanceof ApiError) || failure.status >= 500;
      setUncertain(unknown); if (!unknown) pending.current = null;
    } finally { setBusy(false); }
  }

  function pages(pageOffset: number, count: number, pageTotal: number, change: (value: number) => void) {
    return <div className="actions">{pageOffset > 0 && <button type="button" className="text-button" disabled={guarded || loading || detailLoading} onClick={() => change(Math.max(0, pageOffset - 50))}>{t("上一页")}</button>}{pageOffset + count < pageTotal && <button type="button" className="text-button" disabled={guarded || loading || detailLoading} onClick={() => change(pageOffset + 50)}>{t("下一页")}</button>}</div>;
  }

  return <section className="work-page production-page">
    <div className="page-heading"><div><h1>{t("生产记录")}</h1><p>{t("按订单安排生产，跟踪领退料与完工入库。")}</p></div><div className="actions"><button className="secondary" disabled={guarded} onClick={onRawInventory}>{t("原料库存")}</button><button className="secondary" disabled={guarded} onClick={onInventory}>{t("成品库存")}</button></div></div>
    {notice && <p role="status" className="success">{t(notice)}</p>}
    {listError && <p role="alert" className="error">{t(listError)}<button className="text-button" disabled={guarded || loading} onClick={() => setRefresh(value => value + 1)}>{t("重新读取")}</button></p>}
    {orderId ? <section className="work-panel production-source"><div><h2>{order?.order_number ?? t("来源订单")}</h2><p>{order?.customer_name}</p></div><div className="actions"><button className="text-button" disabled={guarded} onClick={() => onOrder(orderId)}>{t("查看订单")}</button>{canWrite && <button disabled={guarded || loading || order?.status !== "active"} onClick={() => begin("create")}>{t("安排生产")}</button>}</div></section>
      : <p className="production-entry-hint"><button className="text-button" disabled={guarded} onClick={onOrders}>{t("从订单安排生产")}</button></p>}
    {mode && <form className="work-panel production-form" onSubmit={submit} aria-label={t(titles[mode])}>
      <h2 ref={heading} tabIndex={-1}>{t(titles[mode])}</h2>
      {mode === "create" && <><label>{t("订单明细")}<select aria-label={t("订单明细")} value={lineId} onChange={e => setLineId(e.target.value)} required disabled={locked}><option value="">{t("选择订单明细")}</option>{order?.lines.map(item => <option key={item.id} value={item.id} disabled={!item.material?.active || !item.canonical_unit}>{item.line_number}. {item.material?.name ?? item.item_name ?? item.description} · {item.quantity} {displayUnit(item.canonical_unit)}{!item.material_id ? ` · ${t("请先关联物料")}` : !item.material?.active ? ` · ${t("已停用")}` : !item.canonical_unit ? ` · ${t("单位待核对")}` : ""}</option>)}</select></label><p className="muted">{t("计划数量由你填写；请核对下方已有生产单，避免重复安排。")}</p>{line && <p>{line.material?.own_code} · {line.material?.specification || line.specification || "—"}</p>}</>}
      {mode === "issue" && <>{material && <p role="status"><strong>{material.own_code} · {material.name}</strong> · {displayUnit(material.unit)}</p>}<MaterialSelect materialKind="raw" disabled={locked} onSelect={setMaterial} /></>}
      {returning && <p>{returning.own_code} · {returning.material_name} · {t("尚未退回：{0} {1}", [returning.outstanding_quantity, displayUnit(returning.canonical_unit)])}</p>}
      {mode === "complete" && <p className="muted">{t("合格数量增加成品库存。报废只记录数量；待处理品请核实后登记。")}</p>}
      {voiding && <p className="warning">{t("整笔冲回合格 {0}、报废 {1} {2}，保留原记录。", [voiding.quantity, voiding.scrap_quantity, displayUnit(detail?.canonical_unit)])}</p>}
      {mode === "close" && <p className="warning">{t("关闭后停止新增领料和完工；已有库存保留，仍可退料或作废完工。")}</p>}
      <div className="form-grid">
        {!["close", "void"].includes(mode) && <label>{t("业务日期")}<input type="date" required value={day} disabled={locked} onChange={e => setDay(e.target.value)} /></label>}
        {!["close", "void"].includes(mode) && <label>{mode === "create" ? t("计划数量") : mode === "complete" ? t("合格数量") : t("数量")} <span className="muted">{displayUnit(mode === "create" ? line?.canonical_unit : mode === "issue" ? material?.unit : mode === "return" ? returning?.canonical_unit : detail?.canonical_unit)}</span><input inputMode="decimal" required value={quantity} maxLength={64} disabled={locked} onChange={e => setQuantity(e.target.value)} /></label>}
        {mode === "complete" && <label>{t("报废数量")} · {displayUnit(detail?.canonical_unit)}<input inputMode="decimal" required value={scrap} maxLength={64} disabled={locked} onChange={e => setScrap(e.target.value)} /></label>}
        {requiresReason ? <label>{t("操作原因")}<textarea required value={reason} maxLength={500} disabled={locked} onChange={e => setReason(e.target.value)} /></label> : <label>{t("备注")}<textarea value={note} maxLength={500} disabled={locked} onChange={e => setNote(e.target.value)} /></label>}
      </div>
      {error && <p role="alert" className="error">{t(error)}</p>}
      {uncertain && <p role="status" className="warning">{t("结果待确认，请保留此页并重试同一次操作。")}</p>}
      <div className="actions"><button disabled={busy || !canWrite || (!uncertain && !valid)}>{busy ? t("保存中…") : uncertain ? t("重试本次操作") : t("确认保存")}</button><button type="button" className="secondary" disabled={locked} onClick={() => { setMode(null); setError(""); pending.current = null; }}>{t("取消")}</button></div>
    </form>}
    {!mode && error && <p role="alert" className="error">{t(error)}</p>}
    <section className="work-panel production-list" aria-label={t("生产单列表")}>
      <div className="material-search"><label>{t("查找生产单")}<input value={query} disabled={guarded} placeholder={t("生产单号、订单号或成品名称")} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !guarded) { setOffset(0); setFilter(query.trim()); setRefresh(value => value + 1); } }} /></label><button className="secondary" disabled={guarded || loading} onClick={() => { setOffset(0); setFilter(query.trim()); setRefresh(value => value + 1); }}>{t("查找")}</button></div>
      {loading ? <p role="status">{t("正在读取生产单…")}</p> : !items.length ? <p className="empty-state">{t("暂无生产单。请从订单明细安排生产。")}</p> : <div className="table-wrap"><table><thead><tr><th>{t("生产单 / 订单")}</th><th>{t("成品")}</th><th className="numeric">{t("计划 / 已完工")}</th><th>{t("状态")}</th><th>{t("操作")}</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.number}<small>{item.order_number} · {item.business_date}</small></td><td>{item.material_name}<small>{item.own_code} · {item.specification || "—"}</small></td><td className="numeric">{item.planned_quantity} / {item.completed_quantity}<small>{displayUnit(item.canonical_unit)}</small></td><td>{item.status === "closed" ? t("已关闭") : t("进行中")}{!item.source_current && <small className="warning-text">{t("订单来源已变化")}</small>}</td><td><button className="text-button" disabled={guarded || detailLoading} onClick={() => select(item.id)} aria-label={t("查看生产单 {0}", [item.number])}>{t("查看")}</button></td></tr>)}</tbody></table></div>}
      {pages(offset, items.length, total, setOffset)}
    </section>
    {selectedId && <section className="work-panel production-detail" aria-label={t("生产单详情")}>
      {detailLoading && <p role="status">{t("正在读取生产记录…")}</p>}
      {detailError && <p role="alert" className="error">{t("详情未能更新，请重新读取后再操作。")}{t(detailError)}<button className="text-button" disabled={guarded || detailLoading} onClick={() => setRefresh(value => value + 1)}>{t("重新读取")}</button></p>}
      {ready && <><div className="page-heading"><div><h2>{detail.number}</h2><p>{detail.material_name} · {detail.own_code} · {detail.specification || "—"}</p></div><button className="text-button" disabled={guarded} onClick={() => onOrder(detail.order_id)}>{t("来源订单：{0}", [detail.order_number])}</button></div>
        <dl className="production-totals"><div><dt>{t("计划")}</dt><dd>{detail.planned_quantity} <small>{displayUnit(detail.canonical_unit)}</small></dd></div><div><dt>{t("已完工")}</dt><dd>{detail.completed_quantity} <small>{displayUnit(detail.canonical_unit)}</small></dd></div><div><dt>{t("剩余计划")}</dt><dd>{detail.remaining_quantity} <small>{displayUnit(detail.canonical_unit)}</small></dd></div><div><dt>{t("报废")}</dt><dd>{detail.scrap_quantity} <small>{displayUnit(detail.canonical_unit)}</small></dd></div></dl>
        <p className="muted">{t("完工、在库与已送货分别记录；净领出不代表实际消耗。")}</p>
        {!detail.source_current && <p className="warning">{t("订单已修订、删除或改绑物料。原生产记录保留，请核对后另行安排；仍可退料与纠错。")}</p>}
        {detail.status === "closed" && <p className="muted">{t("已关闭")} · {detail.close_reason}</p>}{detail.note && <p>{detail.note}</p>}
        {canWrite && <div className="actions production-actions"><button disabled={guarded || !open} onClick={() => begin("issue")}>{t("生产领料")}</button><button disabled={guarded || !open} onClick={() => begin("complete")}>{t("登记完工")}</button>{detail.status === "open" && <button className="text-button danger-text" disabled={guarded} onClick={() => begin("close")}>{t("关闭生产单")}</button>}</div>}
        <h3>{t("领退料记录")}</h3>{!issues?.items.length ? <p className="empty-state">{t("暂无领料记录。")}</p> : <div className="table-wrap"><table><thead><tr><th>{t("原料 / 日期")}</th><th className="numeric">{t("领出")}</th><th className="numeric">{t("已退")}</th><th className="numeric">{t("净领出")}</th><th>{t("单位")}</th><th>{t("操作")}</th></tr></thead><tbody>{issues.items.map(item => <tr key={item.entry_id}><td>{item.material_name}<small>{item.own_code} · {item.business_date}</small><small>{item.reason}</small></td><td className="numeric">{item.quantity}</td><td className="numeric">{item.returned_quantity}</td><td className="numeric">{item.outstanding_quantity}</td><td>{displayUnit(item.canonical_unit)}</td><td>{canWrite && positive(item.outstanding_quantity) && <button className="text-button" disabled={guarded} onClick={() => begin("return", item)}>{t("登记退料")}</button>}</td></tr>)}</tbody></table></div>}
        {issues && pages(issueOffset, issues.items.length, issues.total, setIssueOffset)}
        <h3>{t("完工记录")}</h3>{!completions?.items.length ? <p className="empty-state">{t("暂无完工记录。")}</p> : <div className="table-wrap"><table><thead><tr><th>{t("业务日期")}</th><th className="numeric">{t("合格数量")}</th><th className="numeric">{t("报废数量")}</th><th>{t("单位")}</th><th>{t("状态 / 备注")}</th><th>{t("操作")}</th></tr></thead><tbody>{completions.items.map(item => <tr key={item.id}><td>{item.business_date}</td><td className="numeric">{item.quantity}</td><td className="numeric">{item.scrap_quantity}</td><td>{displayUnit(detail.canonical_unit)}</td><td>{item.status === "active" ? t("有效") : t("已作废")}<small>{item.void_reason || item.note || "—"}</small></td><td>{canWrite && item.status === "active" && <button className="text-button danger-text" disabled={guarded} onClick={() => begin("void", item)}>{t("作废完工")}</button>}</td></tr>)}</tbody></table></div>}
        {completions && pages(completionOffset, completions.items.length, completions.total, setCompletionOffset)}
      </>}
    </section>}
  </section>;
}
