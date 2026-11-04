import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Extraction, type Material, type MaterialInput, type PurchaseOrder, type Schemas, type SourceSummary, type Supplier } from "../api";
import { msg, t, type UiMessage } from "../i18n";
import { displayUnit, isZeroQuantity } from "../units";
import { MaterialFields, MaterialSelect } from "./MaterialSelect";
import { SourceReview, sheetColumnName } from "./SourceReview";
import { SupplierSelect } from "./SupplierSelect";
import { FileDrop } from "./FileDrop";

type Candidate = Schemas["Candidate"];
type DraftLine = { id: string; material: Material | null; item_name: string; specification: string; unit: string; quantity: string; source_unit_price: string; source_amount: string };
type ImportAttempt = { file?: File; uploadKey: string; extractKey: string; sourceId?: string; runId?: string };
const positive = (value: string) => /^\d+(?:\.\d{1,3})?$/.test(value) && !isZeroQuantity(value);
const validPrice = (value: string) => value === "" || /^\d{1,18}(?:\.\d{1,6})?$/.test(value);
const uncertainResult = (failure: unknown) => !(failure instanceof ApiError) || failure.status >= 500 || failure.status === 401;
const emptyLine = (): DraftLine => ({ id: crypto.randomUUID(), material: null, item_name: "", specification: "", unit: "", quantity: "", source_unit_price: "", source_amount: "" });
const today = () => { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`; };

function NewSupplier({ onSaved, onCancel, onLock }: { onSaved: (supplier: Supplier) => void; onCancel: () => void; onLock: (value: boolean) => void }) {
  const [draft, setDraft] = useState<Schemas["SupplierInput"]>({ full_name: "" });
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState<UiMessage>("");
  const pending = useRef<{ key: string; body: Schemas["SupplierInput"] } | null>(null);
  useEffect(() => { onLock(busy || uncertain); return () => onLock(false); }, [busy, uncertain, onLock]);
  async function save() {
    if (busy || !draft.full_name.trim()) return;
    if (!uncertain) pending.current = { key: crypto.randomUUID(), body: { ...draft, full_name: draft.full_name.trim() } };
    const command = pending.current; if (!command) return;
    setBusy(true); setError("");
    try { onSaved(await api.createSupplier(command.body, command.key)); }
    catch (failure) { setError(message(failure)); setUncertain(previous => previous || uncertainResult(failure)); }
    finally { setBusy(false); }
  }
  return <section className="purchase-inline-editor" aria-label={t("新建供应商")}>
    <label>{t("供应商名称")}<input value={draft.full_name} maxLength={200} disabled={busy || uncertain} onChange={e => setDraft(old => ({ ...old, full_name: e.target.value }))} /></label>
    <details><summary>{t("联系方式（可选）")}</summary><div className="form-grid">{([{ key: "contact", label: "联系人", max: 200 }, { key: "phone", label: "电话", max: 100 }, { key: "address", label: "地址", max: 500 }] as const).map(field => <label key={field.key}>{t(field.label)}<input maxLength={field.max} value={draft[field.key] ?? ""} disabled={busy || uncertain} onChange={e => setDraft(old => ({ ...old, [field.key]: e.target.value }))} /></label>)}</div></details>
    {error && <p role="alert" className="error">{t(error)}</p>}{uncertain && <p className="warning">{t("结果待确认。请重试本次保存，不会重复建档。")}</p>}
    <div className="actions"><button type="button" disabled={busy || !draft.full_name.trim()} onClick={() => void save()}>{uncertain ? t("重试本次保存") : t("保存并选用供应商")}</button><button type="button" className="secondary" disabled={busy || uncertain} onClick={onCancel}>{t("取消建档")}</button></div>
  </section>;
}

function RawMaterialChoice({ line, onSelect, onCancel, onLock }: { line: DraftLine; onSelect: (material: Material) => void; onCancel: () => void; onLock: (value: boolean) => void }) {
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<MaterialInput>({ kind: "raw", name: line.item_name, specification: line.specification || null, unit: line.unit || null, own_code: "" });
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState<UiMessage>("");
  const pending = useRef<{ key: string; body: MaterialInput } | null>(null);
  useEffect(() => { onLock(busy || uncertain); return () => onLock(false); }, [busy, uncertain, onLock]);
  async function save() {
    if (busy || !draft.name.trim() || !draft.unit?.trim()) return;
    if (!uncertain) pending.current = { key: crypto.randomUUID(), body: { ...draft, kind: "raw" } };
    const command = pending.current; if (!command) return;
    setBusy(true); setError("");
    try { onSelect(await api.createMaterial(command.body, command.key)); }
    catch (failure) { setError(message(failure)); setUncertain(previous => previous || uncertainResult(failure)); }
    finally { setBusy(false); }
  }
  return <section className="purchase-inline-editor" aria-label={t("选择或新建原料")}>
    {!creating ? <><MaterialSelect materialKind="raw" initialQuery={line.item_name} disabled={busy || uncertain} onSelect={onSelect} /><div className="actions"><button type="button" className="secondary" onClick={() => setCreating(true)}>{t("新建原料档案")}</button><button type="button" className="text-button" onClick={onCancel}>{t("收起")}</button></div></>
      : <><h4>{t("新建原料档案")}</h4><MaterialFields value={draft} onChange={setDraft} disabled={busy || uncertain} /><p className="muted">{t("请核实基本单位。建档不会增加库存。")}</p>{error && <p role="alert" className="error">{t(error)}</p>}{uncertain && <p className="warning">{t("结果待确认。请重试本次保存，不会重复建档。")}</p>}<div className="actions"><button type="button" disabled={busy || !draft.name.trim() || !draft.unit?.trim()} onClick={() => void save()}>{uncertain ? t("重试本次保存") : t("保存并选用原料")}</button><button type="button" className="secondary" disabled={busy || uncertain} onClick={() => setCreating(false)}>{t("返回选择已有原料")}</button></div></>}
  </section>;
}

function SheetMapping({ extraction, disabled, onApply, onLock }: { extraction: Extraction; disabled: boolean; onApply: (candidate: Candidate) => void; onLock: (value: boolean) => void }) {
  const sheet = extraction.spreadsheet!;
  const [mapping, setMapping] = useState(sheet.suggested_mapping);
  const [busy, setBusy] = useState(false), [error, setError] = useState<UiMessage>("");
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => { onLock(busy); return () => onLock(false); }, [busy, onLock]);
  const fields = [{ key: "item_name", label: "品名", required: true }, { key: "quantity", label: "数量", required: true }, { key: "unit", label: "单位" }, { key: "specification", label: "规格" }, { key: "item_code", label: "原单料号" }, { key: "source_unit_price", label: "单价" }, { key: "source_amount", label: "金额" }] as const;
  async function apply() {
    if (busy || disabled) return;
    setBusy(true); setError("");
    try { const candidate = await api.previewPurchaseSheet(extraction.extraction_id, mapping); if (active.current) onApply(candidate); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <details className="purchase-sheet-mapping" open={extraction.candidate.lines.length === 0 ? true : undefined}><summary>{t("调整Excel明细范围与列")}</summary>
    <div className="form-grid">{([{ key: "header_row", label: "表头行", min: 1 }, { key: "first_row", label: "明细起始行", min: 2 }, { key: "last_row", label: "明细结束行", min: 2 }] as const).map(field => <label key={field.key}>{t(field.label)}<input type="number" min={field.min} max={field.key === "header_row" ? 50 : sheet.max_row} value={mapping[field.key]} disabled={busy || disabled} onChange={e => setMapping(old => ({ ...old, [field.key]: Number(e.target.value) }))} /></label>)}</div>
    <div className="form-grid">{fields.map(field => <label key={field.key}>{t(field.label)}<select value={mapping.columns[field.key] ?? ""} disabled={busy || disabled} onChange={e => setMapping(old => ({ ...old, columns: { ...old.columns, [field.key]: e.target.value ? Number(e.target.value) : null } }))}><option value="">{t("不带入")}</option>{Array.from({ length: sheet.max_column }, (_, index) => <option key={index} value={index + 1}>{sheetColumnName(index + 1)} · {sheet.rows.find(row => row.row_number === mapping.header_row)?.cells.find(cell => cell.column === index + 1)?.text ?? ""}</option>)}</select></label>)}</div>
    <p className="muted">{t("重新带入会替换当前明细，请先确认范围和列。")}</p>{error && <p role="alert" className="error">{t(error)}</p>}<button type="button" className="secondary" disabled={busy || disabled} onClick={() => void apply()}>{t("按这些列重新带入明细")}</button>
  </details>;
}

export function PurchaseOrderEntry({ start, onSaved, onCancel, onLockedChange, onDirtyChange }: {
  start: "manual" | "file"; onSaved: (order: PurchaseOrder, existing?: boolean) => void; onCancel: () => void;
  onLockedChange: (value: boolean) => void; onDirtyChange: (value: boolean) => void;
}) {
  const [stage, setStage] = useState<"source" | "edit">(start === "file" ? "source" : "edit");
  const [file, setFile] = useState<File | null>(null), [extraction, setExtraction] = useState<Extraction | null>(null);
  const [sources, setSources] = useState<SourceSummary[]>([]), [nextCursor, setNextCursor] = useState<string | null>(null), [sourceLoading, setSourceLoading] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [supplier, setSupplier] = useState<Supplier | null>(null), [choosingSupplier, setChoosingSupplier] = useState(true), [newSupplier, setNewSupplier] = useState(false);
  const [materialIndex, setMaterialIndex] = useState<number | null>(null), [childLocked, setChildLocked] = useState(false);
  const [mappingBusy, setMappingBusy] = useState(false);
  const [day, setDay] = useState(today), [number, setNumber] = useState(""), [currency, setCurrency] = useState<"" | "CNY" | "USD">(start === "manual" ? "CNY" : "");
  const [buyer, setBuyer] = useState(""), [note, setNote] = useState("");
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [showValidation, setShowValidation] = useState(false);
  const initialDay = useRef(day);
  const importing = useRef<ImportAttempt | null>(null);
  const pending = useRef<{ key: string; body: Schemas["PurchaseOrderInput"] } | null>(null);
  const locked = busy || uncertain || childLocked || mappingBusy;
  const dirty = !!file || !!extraction || !!supplier || newSupplier || materialIndex !== null || !!number || day !== initialDay.current || !!buyer || !!note || lines.some(line => line.material || line.quantity || line.source_unit_price || line.source_amount) || currency !== (start === "manual" ? "CNY" : "");
  useEffect(() => { onLockedChange(locked); return () => onLockedChange(false); }, [locked, onLockedChange]);
  useEffect(() => { onDirtyChange(dirty); return () => onDirtyChange(false); }, [dirty, onDirtyChange]);
  function cancel() { if (!dirty || window.confirm(t("离开后，未保存的采购内容会丢失。确定离开吗？"))) onCancel(); }
  useEffect(() => { if (start === "file") void loadSources(); }, [start]);
  async function loadSources(cursor?: string) {
    setSourceLoading(true);
    try { const result = await api.sources(cursor, "purchase_order"); setSources(old => cursor ? [...old, ...result.items] : result.items); setNextCursor(result.next_cursor); }
    catch (failure) { setError(message(failure)); }
    finally { setSourceLoading(false); }
  }
  function applyCandidate(candidate: Candidate, header = true) {
    setLines(candidate.lines.length ? candidate.lines.map(line => ({ ...emptyLine(), item_name: line.item_name || line.description, specification: line.specification ?? "", unit: line.unit ?? "", quantity: line.quantity, source_unit_price: line.source_unit_price ?? "", source_amount: line.source_amount ?? "" })) : [emptyLine()]);
    setMaterialIndex(null);
    if (header) { setDay(candidate.business_date); setNumber(candidate.order_number); setCurrency(candidate.currency === "CNY" || candidate.currency === "USD" ? candidate.currency : ""); }
  }
  async function importSource(source?: SourceSummary) {
    if (busy || childLocked) return;
    if (!uncertain) importing.current = { ...(source ? { sourceId: source.source_id, ...(source.extraction_id ? { runId: source.extraction_id } : {}) } : file ? { file } : {}), uploadKey: crypto.randomUUID(), extractKey: crypto.randomUUID() };
    const attempt = importing.current; if (!attempt || !attempt.file && !attempt.sourceId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (!attempt.sourceId && attempt.file) attempt.sourceId = (await api.upload(attempt.file, attempt.uploadKey, "purchase_order")).source_id;
      const sourceId = attempt.sourceId!;
      try { const existing = await api.purchaseOrderBySource(sourceId); onSaved(existing, true); return; }
      catch (failure) { if (!(failure instanceof ApiError) || failure.code !== "PURCHASE_ORDER_NOT_FOUND") throw failure; }
      if (!attempt.runId) attempt.runId = (await api.extract(sourceId, attempt.extractKey)).extraction_id;
      const detail = await api.extraction(attempt.runId);
      setExtraction(detail); setUncertain(false);
      if (detail.error_code === "PURCHASE_IMPORT_TOO_MANY_LINES") { setError(msg("采购单超过200条明细，请拆分文件后重新导入。")); importing.current = null; return; }
      if (detail.error_code === "PURCHASE_SHEET_MERGED_DETAIL") { setError(msg("Excel明细包含合并单元格，请展开为独立行后重新上传。")); importing.current = null; return; }
      applyCandidate(detail.candidate); setStage("edit"); setShowValidation(true); importing.current = null;
    } catch (failure) { setError(message(failure)); setUncertain(previous => previous || uncertainResult(failure)); }
    finally { setBusy(false); }
  }
  function changeLine(index: number, field: "quantity" | "source_unit_price" | "source_amount", value: string) {
    setLines(old => old.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }
  const needsCurrency = lines.some(line => line.source_unit_price !== "" || line.source_amount !== "");
  const valid = !!supplier?.active && !!day && lines.length > 0 && lines.every(line => line.material?.active && positive(line.quantity) && validPrice(line.source_unit_price) && validPrice(line.source_amount)) && (!needsCurrency || !!currency);
  const missing: UiMessage[] = [];
  if (!supplier?.active) missing.push(msg("请选择或新建供应商。"));
  if (!day) missing.push(msg("请填写采购日期。"));
  if (!lines.length) missing.push(msg("请添加至少一行原料。"));
  lines.forEach((line, index) => {
    if (!line.material?.active) missing.push(msg("第{0}行：请选择或新建原料。", [index + 1]));
    if (!positive(line.quantity)) missing.push(msg("第{0}行：数量须大于0，最多三位小数。", [index + 1]));
    if (!validPrice(line.source_unit_price) || !validPrice(line.source_amount)) missing.push(msg("第{0}行：单价或金额格式不正确，最多六位小数。", [index + 1]));
  });
  if (needsCurrency && !currency) missing.push(msg("填写价格或金额时，请明确选择币种。"));
  async function save(event: FormEvent) {
    event.preventDefault(); if (busy || childLocked || mappingBusy || materialIndex !== null || newSupplier) return;
    if (!uncertain && !valid) { setShowValidation(true); return; }
    if (!uncertain) pending.current = { key: crypto.randomUUID(), body: {
      supplier_id: supplier!.id, business_date: day, number: number.trim() || null, note: note.trim() || null,
      currency: currency || null, buyer_name: buyer.trim() || null,
      source_id: extraction?.source_id ?? null, extraction_id: extraction?.extraction_id ?? null,
      lines: lines.map(line => ({ material_id: line.material!.id, expected_material_version: line.material!.version, quantity: line.quantity, source_unit_price: line.source_unit_price || null, source_amount: line.source_amount || null })),
    } };
    const command = pending.current; if (!command) return;
    setBusy(true); setError("");
    try { const result = await api.createPurchaseOrder(command.body, command.key); pending.current = null; setUncertain(false); onSaved(result); }
    catch (failure) { setError(message(failure)); setUncertain(previous => previous || uncertainResult(failure)); }
    finally { setBusy(false); }
  }
  return <section className="purchase-entry">
    <div className="row-between"><h2>{start === "file" ? t("导入采购单") : t("新建采购单")}</h2><button type="button" className="text-button" disabled={locked} onClick={cancel}>{t("取消")}</button></div>
    {error && <p role="alert" className="error">{t(error)}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
    {stage === "source" ? <section className="work-panel"><FileDrop files={file ? [file] : []} purpose="purchase" disabled={locked} onFiles={next => { setFile(next[0] ?? null); setError(""); setExtraction(null); importing.current = null; }} />
      {uncertain && <p className="warning">{t("文件处理结果待确认，请重试本次导入。")}</p>}
      <button type="button" disabled={busy || !uncertain && !file} onClick={() => void importSource()}>{busy ? t("正在处理…") : uncertain ? t("重试本次导入") : t("读取并核对采购单")}</button>
      <details><summary>{t("已上传的采购原件")}</summary>{sourceLoading && <p role="status">{t("正在读取…")}</p>}<ul className="material-options">{sources.map(source => <li key={source.source_id}><span>{source.filename}</span><button type="button" className="secondary" disabled={locked} onClick={() => void importSource(source)}>{t("查看")}</button></li>)}</ul>{nextCursor && <button type="button" className="text-button" disabled={locked || sourceLoading} onClick={() => void loadSources(nextCursor)}>{t("更多")}</button>}<button type="button" className="text-button" disabled={locked || sourceLoading} onClick={() => void loadSources()}>{t("重新读取")}</button></details>
    </section> : <div className={extraction ? "source-entry-layout purchase-entry-layout" : "purchase-entry-layout"}>
      {extraction && <SourceReview extraction={extraction} />}
      <form className="work-panel purchase-order-form" onSubmit={save} noValidate>
        <h3>{t("供应商")}</h3>
        {supplier && <div className="row-between purchase-selected"><strong>{supplier.full_name}</strong><button type="button" className="text-button" disabled={locked} onClick={() => setChoosingSupplier(value => !value)}>{t("更换供应商")}</button></div>}
        {newSupplier ? <NewSupplier onLock={setChildLocked} onCancel={() => setNewSupplier(false)} onSaved={item => { setSupplier(item); setNewSupplier(false); setChoosingSupplier(false); setNotice(msg("供应商档案已保存。")); }} />
          : choosingSupplier && <><SupplierSelect selected={supplier} disabled={locked} onSelect={item => { setSupplier(item); setChoosingSupplier(false); }} /><button type="button" className="text-button" disabled={locked} onClick={() => setNewSupplier(true)}>{t("新建供应商")}</button></>}
        <fieldset disabled={locked || newSupplier || materialIndex !== null} className="purchase-header-fields"><div className="form-grid">
          <label>{t("采购日期")}<input type="date" value={day} required onChange={e => setDay(e.target.value)} /></label>
          <label>{t("采购单号")}<input value={number} maxLength={100} placeholder={t("留空自动编号")} onChange={e => setNumber(e.target.value)} /></label>
          <label>{t("币种")}<select aria-label={t("币种")} value={currency} onChange={e => setCurrency(e.target.value as typeof currency)}><option value="">{t("请选择")}</option><option value="CNY">CNY</option><option value="USD">USD</option></select></label>
        </div></fieldset>
        {extraction?.spreadsheet && <SheetMapping extraction={extraction} disabled={locked || newSupplier || materialIndex !== null} onLock={setMappingBusy} onApply={candidate => applyCandidate(candidate, false)} />}
        <h3>{t("原料明细")}</h3>
        <div className="purchase-entry-lines">{lines.map((line, index) => <section className="purchase-entry-line" key={line.id} aria-label={t("采购明细第{0}行", [index + 1])}>
          <div className="row-between"><strong>{t("第{0}行", [index + 1])}</strong><button type="button" className="text-button" disabled={locked || materialIndex !== null || newSupplier} onClick={() => setLines(old => old.filter((_, i) => i !== index))}>{t("移除")}</button></div>
          {line.item_name && <p className="muted">{t("原件：{0}", [[line.item_name, line.specification, line.unit].filter(Boolean).join(" · ")])}</p>}
          {line.material && <p className="purchase-material-snapshot"><strong>{line.material.name}</strong><small>{line.material.own_code} · {line.material.specification} · {displayUnit(line.material.unit)}</small></p>}
          {materialIndex === index ? <RawMaterialChoice key={line.id} line={line} onLock={setChildLocked} onCancel={() => setMaterialIndex(null)} onSelect={material => { setLines(old => old.map((item, i) => i === index ? { ...item, material } : item)); setMaterialIndex(null); }} />
            : <button type="button" className={line.material ? "text-button" : "secondary"} disabled={locked || materialIndex !== null || newSupplier} onClick={() => setMaterialIndex(index)}>{line.material ? t("更换原料") : t("选择或新建原料")}</button>}
          <div className="purchase-line-values"><label>{t("数量（{0}）", [displayUnit(line.material?.unit ?? line.unit)])}<input inputMode="decimal" maxLength={64} value={line.quantity} required disabled={locked || materialIndex !== null || newSupplier} onChange={e => changeLine(index, "quantity", e.target.value)} aria-invalid={!!line.quantity && !positive(line.quantity)} /></label>
            <label>{t("单价")}<input inputMode="decimal" maxLength={64} value={line.source_unit_price} placeholder={t("不知道可留空")} disabled={locked || materialIndex !== null || newSupplier} onChange={e => changeLine(index, "source_unit_price", e.target.value)} aria-invalid={!validPrice(line.source_unit_price)} /></label>
            <label>{t("金额")}<input inputMode="decimal" maxLength={64} value={line.source_amount} placeholder={t("不知道可留空")} disabled={locked || materialIndex !== null || newSupplier} onChange={e => changeLine(index, "source_amount", e.target.value)} aria-invalid={!validPrice(line.source_amount)} /></label></div>
        </section>)}</div>
        <button type="button" className="text-button" disabled={locked || lines.length >= 200 || materialIndex !== null || newSupplier} onClick={() => setLines(old => [...old, emptyLine()])}>{t("增加一行原料")}</button>
        <p className="muted">{t("金额按原单或约定填写；留空不会自动计算。")}</p>
        <details className="purchase-print-options"><summary>{t("采购方与备注（可选）")}</summary><label>{t("采购方名称")}<input maxLength={200} value={buyer} disabled={locked || newSupplier || materialIndex !== null} onChange={e => setBuyer(e.target.value)} /></label><label>{t("备注")}<textarea maxLength={1000} value={note} disabled={locked || newSupplier || materialIndex !== null} onChange={e => setNote(e.target.value)} /></label></details>
        {needsCurrency && !currency && !showValidation && <p className="warning">{t("填写价格或金额时，请明确选择币种。")}</p>}
        {showValidation && !uncertain && missing.length > 0 && <div className="warning purchase-validation" role="alert"><strong>{t("请补齐以下内容后保存：")}</strong><ul>{missing.map((item, index) => <li key={index}>{t(item)}</li>)}</ul></div>}
        {(newSupplier || materialIndex !== null) && <p className="muted" role="status">{t("请先完成当前档案的选择或新建，也可收起后继续填写。")}</p>}
        {uncertain && <p className="warning" role="status">{t("结果待确认，请保留此页并重试同一次保存。")}</p>}
        <div className="actions"><button disabled={busy || childLocked || mappingBusy || materialIndex !== null || newSupplier}>{busy ? t("保存中…") : uncertain ? t("重试本次保存") : t("确认保存采购单")}</button><button type="button" className="secondary" disabled={locked} onClick={cancel}>{t("取消")}</button></div>
      </form>
    </div>}
  </section>;
}
