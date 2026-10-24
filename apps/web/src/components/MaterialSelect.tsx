import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Material, type MaterialInput, type MaterialCode, type OrderDetail, type Schemas } from "../api";

export function MaterialFields({ value, onChange, disabled, fixed }: {
  value: MaterialInput; onChange: (value: MaterialInput) => void; disabled: boolean; fixed?: Material;
}) {
  return <div className="form-grid material-fields">
    <label>{t("我方料号")}<input value={value.own_code ?? ""} onChange={e => onChange({ ...value, own_code: e.target.value })} maxLength={100} disabled={disabled} placeholder={t("留空自动编号")} required={!!fixed} /></label>
    <label>{t("物料名称")}<input value={value.name} onChange={e => onChange({ ...value, name: e.target.value })} maxLength={500} required disabled={disabled} /></label>
    <label>{t("物料规格")}<textarea value={value.specification ?? ""} onChange={e => onChange({ ...value, specification: e.target.value })} maxLength={1000} disabled={disabled || !!fixed?.specification} rows={2} placeholder={t("可暂缺")} /></label>
    <label>{t("基本单位")}<input value={value.unit ?? ""} onChange={e => onChange({ ...value, unit: e.target.value })} maxLength={40} disabled={disabled || !!fixed?.unit} placeholder={t("可暂缺，如 PCS、KG")} /></label>
  </div>;
}

export function MaterialSelect({ onSelect, disabled = false, initialQuery = "", actionLabel = t("选择") }: {
  onSelect: (material: Material) => void; disabled?: boolean; initialQuery?: string; actionLabel?: string;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [filter, setFilter] = useState(initialQuery);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [items, setItems] = useState<Material[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<UiMessage>("");
  useEffect(() => {
    let live = true; setLoading(true); setError("");
    api.materials(filter, offset).then(result => { if (live) { setItems(result.items); setNext(result.next_offset); } })
      .catch(failure => { if (live) { setItems([]); setError(message(failure)); } }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [filter, offset, refresh]);
  function search() { setOffset(0); setFilter(query.trim()); setRefresh(value => value + 1); }
  return <section className="material-picker" aria-label={t("查找已有物料")}>
    <div className="material-search"><label>{t("查找物料")}<input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); search(); } }} placeholder={t("我方料号、客户料号、名称或规格")} disabled={disabled} /></label><button type="button" className="secondary" onClick={search} disabled={disabled}>{t("查找")}</button></div>
    {error && <p role="alert" className="error">{t(error)}</p>}
    {loading ? <p role="status">{t("正在查找…")}</p> : !items.length ? <p className="muted">{t("没有找到物料，可调整关键词或新建。")}</p> : <ul className="material-options">{items.map(item => <li key={item.id}><div><strong>{item.own_code}</strong> · {item.name}<small>{item.specification || t("规格暂缺")} · {item.unit || t("单位待核对")}{!item.active && t(" · 已停用")}</small>{item.matched_customer_codes?.map(code => <small key={`${code.customer_name}:${code.customer_code}`}>{t("客户：{0} · 料号：{1}", [(code.customer_name) ?? "", (code.customer_code) ?? ""])}</small>)}</div><button type="button" className="secondary" disabled={disabled || !item.active} onClick={() => onSelect(item)} aria-label={`${actionLabel} ${item.own_code}`}>{actionLabel}</button></li>)}</ul>}
    <div className="actions">{offset > 0 && <button type="button" className="text-button" onClick={() => setOffset(Math.max(0, offset - 50))} disabled={loading || disabled}>{t("上一页")}</button>}{next !== null && <button type="button" className="text-button" onClick={() => setOffset(next)} disabled={loading || disabled}>{t("下一页")}</button>}</div>
  </section>;
}

export function materialFromOrderLine(line: OrderDetail["lines"][number]): MaterialInput {
  return { name: line.item_name || line.description, own_code: "", specification: line.specification ?? null, unit: line.source_unit };
}

export function OrderMaterialLink({ order, line, initialMode = "existing", initialError = "", initialRemember = !!line.item_code, onClose, onSaved }: {
  order: OrderDetail; line: OrderDetail["lines"][number]; initialMode?: "existing" | "new"; initialError?: UiMessage; initialRemember?: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [mode, setMode] = useState<"existing" | "new" | "clear">(initialMode);
  const [selected, setSelected] = useState<Material | null>(line.material ?? null);
  const [draft, setDraft] = useState<MaterialInput>(() => materialFromOrderLine(line));
  const [remember, setRemember] = useState(initialRemember);
  const [code, setCode] = useState(line.item_code ?? "");
  const [mapping, setMapping] = useState<MaterialCode | null>(null);
  const [mappingLoading, setMappingLoading] = useState(initialRemember && !!line.item_code?.trim());
  const [mappingRefresh, setMappingRefresh] = useState(0);
  const [mappingError, setMappingError] = useState<UiMessage>("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>(initialError);
  const [review, setReview] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const pending = useRef<{ key: string; body: Schemas["OrderMaterialLinksInput"] } | null>(null);
  useEffect(() => { heading.current?.focus(); heading.current?.closest("section")?.scrollIntoView({ block: "start" }); }, []);
  useEffect(() => {
    let live = true; setMapping(null); setMappingError("");
    if (!remember || !code.trim() || mode === "clear") { setMappingLoading(false); return; }
    setMappingLoading(true);
    api.materialCodes(undefined, order.customer_id, code.trim()).then(result => { if (live) setMapping(result.items[0] ?? null); })
      .catch(failure => { if (live) setMappingError(message(failure)); }).finally(() => { if (live) setMappingLoading(false); });
    return () => { live = false; };
  }, [code, remember, mode, order.customer_id, mappingRefresh]);
  const currentMapping = remember && mode !== "clear" && mapping?.customer_code === code.trim() ? mapping : null;
  function correctionNeeded(target: Material | null) {
    if (mode === "existing" && !target) return false;
    return !!line.material_id && (mode !== "existing" || target?.id !== line.material_id) || !!currentMapping && (mode === "new" || target?.id !== currentMapping.material_id || currentMapping.item_name !== (line.item_name?.trim() || null) || currentMapping.specification !== (line.specification?.trim() || null) || currentMapping.canonical_unit !== line.canonical_unit);
  }
  const needsReason = correctionNeeded(selected);
  async function choose(target: Material) {
    if (busy || uncertain || mappingLoading || mappingError || remember && !code.trim()) return;
    setSelected(target); setReason("");
    if (correctionNeeded(target)) {
      setReview(true); setError(msg("这次选择会更正已有的订单关联或客户料号对应，请核对并填写更正原因。")); heading.current?.focus(); return;
    }
    setReview(false); await save(target, null);
  }
  async function save(target = selected, changeReason = reason.trim() || null) {
    if (busy || !uncertain && (mappingLoading || !!mappingError || mode === "existing" && !target || mode !== "clear" && remember && !code.trim() || correctionNeeded(target) && !changeReason)) return;
    if (!uncertain) pending.current = { key: crypto.randomUUID(), body: { expected_version: order.version, reason: changeReason, lines: [{
      line_id: line.id, ...(mode === "new" ? { new_material: draft } : mode === "existing" && target ? { material_id: target.id, expected_material_version: target.version } : {}),
      remember_code: mode !== "clear" && remember, customer_code: code.trim() || null, expected_mapping_version: currentMapping?.version ?? 0,
    }] } };
    if (!pending.current) return;
    setBusy(true); setError("");
    try { await api.linkOrderMaterials(order.id, pending.current.body, pending.current.key); setUncertain(false); onSaved(); }
    catch (failure) {
      setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); setReview(true); heading.current?.focus();
      if (failure instanceof ApiError && failure.code === "MATERIAL_MAPPING_CONFLICT") setMappingRefresh(value => value + 1);
      if (failure instanceof ApiError && failure.code === "MATERIAL_VERSION_CONFLICT") setSelected(null);
    }
    finally { setBusy(false); }
  }
  return <section className="work-panel material-link-panel" aria-label={t("归入物料池")}>
    <div className="row-between"><h2 ref={heading} tabIndex={-1}>{t("第{0} 行 ·{1}", [(line.line_number) ?? "", (line.material_id ? t("维护物料关联") : mode === "new" ? t("核对后收录") : t("关联已有物料")) ?? ""])}</h2><button className="text-button" onClick={onClose} disabled={busy || uncertain}>{t("取消")}</button></div>
    {mode !== "existing" && <p className="muted">{t("原单料号：{0}。此次只整理物料对应，订单凭证和交付数量保持原样。", [(line.item_code || t("未提供")) ?? ""])}</p>}
    {error && <p className="error" role="alert">{t(error)}</p>}
    <div className="actions">{mode !== "existing" && <button type="button" className="text-button" onClick={() => { setMode("existing"); setReview(false); setError(""); }} disabled={busy || uncertain}>{t("改选已有物料")}</button>}{mode !== "new" && <button type="button" className="text-button" onClick={() => { setMode("new"); setReview(false); setError(""); }} disabled={busy || uncertain}>{t("改为新建物料")}</button>}{line.material_id && mode !== "clear" && <button type="button" className="text-button danger-text" onClick={() => { setMode("clear"); setError(""); }} disabled={busy || uncertain}>{t("解除关联")}</button>}</div>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      {mode === "new" && <MaterialFields value={draft} onChange={setDraft} disabled={busy || uncertain} />}
      {mode === "clear" ? <p>{t("解除本行关联；已建立的物料和客户料号对应保留。")}</p> : <>
        <label className="checkbox"><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} disabled={busy || uncertain} />{t("把这次确认的客户料号对应记住，供以后订单使用")}</label>
        {remember && <><label>{t("{0} 的料号", [(order.customer_name) ?? ""])}<input value={code} onChange={e => setCode(e.target.value)} maxLength={100} required disabled={busy || uncertain} /></label>{(mode === "new" || selected) && <p className="muted">{t("客户：{0} · 客户料号：{1} → {2}", [(order.customer_name) ?? "", (code || t("待填写")) ?? "", (mode === "new" ? draft.own_code || t("保存时生成我方料号") : selected?.own_code) ?? ""])}</p>}{mode === "new" && currentMapping && <p className="muted">{t("这个客户料号已有对应；更正时需要核对。")}</p>}{mappingLoading && <p role="status" className="muted">{t("正在核对客户料号…")}</p>}{mappingError && <p role="alert" className="error">{t(mappingError)}<button type="button" className="text-button" onClick={() => setMappingRefresh(value => value + 1)} disabled={busy || uncertain}>{t("重试核对")}</button></p>}</>}
      </>}
      {mode === "existing" && <><p className="muted">{t("选中即完成关联；需要更正时先核对。")}</p><MaterialSelect onSelect={target => void choose(target)} actionLabel={t("关联")} initialQuery={line.item_name ?? ""} disabled={busy || uncertain || mappingLoading || !!mappingError || remember && !code.trim()} />{selected && <p role="status">{t("已选：")}<strong>{selected.own_code}</strong> · {selected.name}</p>}</>}
      {needsReason && <label>{t("更正原因")}<textarea value={reason} onChange={e => setReason(e.target.value)} maxLength={500} required disabled={busy || uncertain} /></label>}
      {uncertain && <p className="warning" role="status">{t("结果待确认，请保留此页并重试同一次保存。")}</p>}
      <div className="actions">{(mode !== "existing" || review || busy || uncertain) && <button disabled={busy || !uncertain && (mappingLoading || !!mappingError || needsReason && !reason.trim() || mode === "existing" && !selected || mode === "new" && (!draft.name.trim() || draft.name.length > 500))}>{busy ? t("保存中…") : uncertain ? t("重试本次保存") : mode === "clear" ? t("确认解除关联") : mode === "existing" ? t("核对后关联") : t("保存物料关联")}</button>}<button type="button" className="secondary" onClick={onClose} disabled={busy || uncertain}>{t("取消")}</button></div>
    </form>
  </section>;
}
