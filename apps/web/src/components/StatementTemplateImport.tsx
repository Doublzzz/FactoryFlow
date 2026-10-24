import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Schemas, type Statement, type StatementTemplate, type TemplateMapping } from "../api";
import "./statement-templates.css";

const detailFields = [
  ["item_name", "货物名称", false], ["item_name_specification", "品名／规格合并", false], ["unit", "单位", true], ["quantity", "数量", true],
  ["unit_price", "单价", true], ["amount", "金额", true], ["ordinal", "序号", false],
  ["delivery_date", "送货日期", false], ["item_code", "货物编号", false],
  ["specification", "规格型号", false], ["reason", "说明", false],
  ["external_document_number", "客户外部送货／退货单号（映射后须填写）", false],
  ["order_number", "订单号", false], ["delivery_reference", "系统送货标识", false],
] as const;
const cellFields = [
  ["customer_name", "客户名称", true], ["period", "期间", true], ["status", "草稿／正式状态", false],
  ["total", "最终金额", true], ["priced_subtotal", "已定价小计", false],
  ["tax_base", "计税基数", false], ["tax_amount", "税额", false], ["adjustments", "调整说明", false],
  ["total_label", "总额税制说明", false],
] as const;
function columnName(index: number): string { return index < 26 ? String.fromCharCode(65 + index) : `A${String.fromCharCode(65 + index - 26)}`; }
function fileBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = reject; reader.onload = () => resolve(String(reader.result).split(",")[1] ?? ""); reader.readAsDataURL(file); });
}
function savePreview(content: string) {
  const bytes = Uint8Array.from(atob(content), value => value.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  const link = document.createElement("a"); link.href = url; link.download = t("客户模板-未保存预览.xlsx");
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function CellGrid({ rows, select, selected, start, end }: { rows: string[][]; select?: (row: number, col: number) => void; selected?: string; start?: number; end?: number }) {
  const columns = Math.max(0, ...rows.map(row => row.length));
  return <div className="template-grid-wrap" tabIndex={0} aria-label={select ? t("上传模板单元格，可点击指定位置") : t("填入对账数据后的预览")}><table className="template-grid"><thead><tr><th aria-label={t("行号")} />{Array.from({ length: columns }, (_, index) => <th key={index}>{columnName(index)}</th>)}</tr></thead><tbody>{rows.map((cells, row) => <tr key={row} className={start && end && row + 1 >= start && row + 1 <= end ? "template-detail-row" : ""}><th scope="row">{row + 1}</th>{Array.from({ length: columns }, (_, col) => { const address = `${columnName(col)}${row + 1}`; return <td key={col} className={selected === address || selected === columnName(col) ? "template-selected-cell" : ""}>{select ? <button type="button" title={`${address} ${cells[col] ?? ""}`} aria-label={t("选择 {0}{1}", [address, cells[col] ? `：${cells[col]}` : t("（空白）")])} onClick={() => select(row + 1, col)}>{cells[col] || <span className="template-empty-cell">·</span>}</button> : cells[col]}</td>; })}</tr>)}</tbody></table></div>;
}

export function StatementTemplateImport({ statement, disabled, onImported, onGuardChange }: {
  statement: Statement; disabled: boolean; onImported: (template: StatementTemplate) => void; onGuardChange: (blocked: boolean) => void;
}) {
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const [file, setFile] = useState<Schemas["TemplateFileInput"] | null>(null);
  const [inspection, setInspection] = useState<Schemas["TemplateInspection"] | null>(null);
  const [mapping, setMapping] = useState<TemplateMapping | null>(null);
  const [name, setName] = useState(""), [error, setError] = useState<UiMessage>("");
  const [target, setTarget] = useState("cells.customer_name");
  const [preview, setPreview] = useState<Schemas["TemplatePreview"] | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const inflight = useRef(false);
  const pending = useRef<{ key: string; body: Schemas["TemplateImportInput"] } | null>(null);
  const locked = disabled || busy || uncertain;
  useEffect(() => { onGuardChange(busy || !!file || uncertain); return () => onGuardChange(false); }, [busy, file, uncertain, onGuardChange]);
  useEffect(() => { setPreview(null); setConfirmed(false); }, [statement.version]);
  function clear() { setFile(null); setInspection(null); setMapping(null); setPreview(null); setConfirmed(false); setError(""); pending.current = null; setUncertain(false); setOpen(false); }
  function changeMapping(next: TemplateMapping) { setMapping(next); setPreview(null); setConfirmed(false); pending.current = null; }
  function bind(group: "columns" | "cells", field: string, value: string) {
    if (!mapping || locked) return;
    const updated = { ...mapping[group] };
    if (value.trim()) updated[field] = value.trim().toUpperCase(); else delete updated[field];
    changeMapping({ ...mapping, [group]: updated });
  }
  async function chooseFile(chosen: File | undefined) {
    if (!chosen || locked || inflight.current) return;
    if (!chosen.name.toLowerCase().endsWith(".xlsx") || chosen.size > 2 * 1024 * 1024) { setError(msg("请选择不超过 2 MiB 的 .xlsx 文件。")); return; }
    inflight.current = true; setBusy(true); setError(""); setPreview(null); setConfirmed(false); pending.current = null;
    try {
      const body = { filename: chosen.name, content_base64: await fileBase64(chosen) };
      const result = await api.inspectStatementTemplate(statement.customer_id, body);
      setFile(body); setInspection(result); setName(chosen.name.replace(/\.xlsx$/i, "").slice(0, 80));
      setMapping(result.suggested_mapping ?? { sheet_name: result.sheet_name, detail_start_row: 2, detail_end_row: 2, columns: {}, cells: {} });
    } catch (failure) { setFile(null); setInspection(null); setMapping(null); setError(templateError(failure)); }
    finally { inflight.current = false; setBusy(false); }
  }
  function templateError(failure: unknown) {
    const locations: Record<string, UiMessage> = { required_fields: msg("必填字段"), detail_rows: msg("明细起止行"), summary_gap: msg("合计须在明细区后，最多隔一行"), duplicate_bindings: msg("重复的位置"), columns: msg("明细列"), cells: msg("固定单元格"), worksheet_features: msg("工作表中的复杂格式"), workbook_features: msg("工作簿中的复杂格式"), relationships: msg("外部链接或对象"), named_ranges: msg("自定义名称"), sheets: msg("工作表数量或状态"), print_title_rows: msg("重复打印的标题行"), freeze_panes: msg("冻结窗格"), row_groups: msg("分组行"), column_groups: msg("分组列") };
    return msg("{0}{1}", [message(failure), failure instanceof ApiError && failure.field ? msg(" 位置：{0}", [locations[failure.field] ?? failure.field]) : ""]);
  }
  async function generatePreview() {
    if (locked || inflight.current || !file || !inspection || !mapping) return;
    inflight.current = true; setBusy(true); setError(""); setPreview(null); setConfirmed(false);
    try { setPreview(await api.previewStatementTemplate(statement.customer_id, { ...file, inspected_sha256: inspection.file_hash, mapping, statement_id: statement.id, expected_version: statement.version })); }
    catch (failure) { setError(templateError(failure)); }
    finally { inflight.current = false; setBusy(false); }
  }
  async function save(retry = false) {
    if (inflight.current || disabled || (!retry && (locked || !confirmed || !preview || !name.trim() || !file || !inspection || !mapping))) return;
    if (!retry) pending.current = { key: crypto.randomUUID(), body: { ...file!, inspected_sha256: inspection!.file_hash, mapping: mapping!, name: name.trim() } };
    const command = pending.current;
    if (!command) return;
    inflight.current = true; setBusy(true); setError("");
    try { const result = await api.importStatementTemplate(statement.customer_id, command.body, command.key); clear(); onImported(result); }
    catch (failure) { setError(templateError(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { inflight.current = false; setBusy(false); }
  }
  function selectCell(row: number, col: number) {
    if (!mapping || locked) return;
    if (target === "start" || target === "end") changeMapping({ ...mapping, [target === "start" ? "detail_start_row" : "detail_end_row"]: row });
    else { const [group, field] = target.split("."); if (field && (group === "cells" || group === "columns")) bind(group, field, group === "columns" ? columnName(col) : `${columnName(col)}${row}`); }
  }
  const [selectedGroup, selectedField] = target.split(".");
  const selected = mapping && selectedField && (selectedGroup === "cells" || selectedGroup === "columns") ? mapping[selectedGroup][selectedField] ?? "" : "";
  const complete = mapping && (mapping.columns.item_name || mapping.columns.item_name_specification) && detailFields.every(([field, , required]) => !required || mapping.columns[field]) && cellFields.every(([field, , required]) => !required || mapping.cells[field]);
  return <div className="template-import">
    {!open ? <button className="secondary" disabled={disabled} onClick={() => setOpen(true)}>{t("导入客户 Excel 模板")}</button> : <div className="template-import-panel">
      <div className="template-import-heading"><div><h3>{t("导入客户模板")}</h3><p>{t("保留客户的表头和排版，系统填入本单数据。保存后可在上方选择使用。")}</p></div><button className="text-button" disabled={busy || uncertain} onClick={clear}>{t("取消本次导入")}</button></div>
      <label className="template-upload">{t("1. 选择模板文件")}<input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={locked} onChange={event => { void chooseFile(event.target.files?.[0]); event.target.value = ""; }} /></label>
      <p className="muted">{t("一个有内容的工作表，可带空白工作表；.xlsx 最多 2 MiB、300 行、30 列。不支持图片、宏、外链或复杂表格对象。表内每条明细占一行，合计和页尾会随实际条数移动。")}</p>
      {error && <p role="alert" className="error">{t(error)}</p>}
      {uncertain && <div className="warning"><p>{t("保存结果尚未确认。请重试同一次保存，系统会避免重复导入。")}</p><button disabled={busy || disabled} onClick={() => void save(true)}>{t("核实并重试保存")}</button></div>}
      {busy && <p role="status">{t("正在处理模板…")}</p>}
      {file && inspection && mapping && <>
        <div className="template-name-row"><label>{t("模板名称")}<input value={name} maxLength={80} disabled={locked} onChange={e => setName(e.target.value)} /></label><p>{t("{0} · {1} · {2} 行 ×{3} 列", [(file.filename) ?? "", (inspection.sheet_name) ?? "", (inspection.rows) ?? "", (inspection.columns) ?? ""])}</p></div>
        <h4>{t("2. 确认字段位置")}</h4><p>{t("先点左侧的位置输入框，再点右侧表格，也可直接填 A、H10 等位置。带 * 的位置必填；货物名称与品名／规格合并至少选一项。系统识别的列只是建议。")}</p>
        <div className="template-mapping-layout"><div className="template-bindings"><fieldset disabled={locked}><legend>{t("明细范围（含样例和预留空行）")}</legend>
          <label>{t("第一条明细行 *")}<input type="number" min={2} max={300} value={mapping.detail_start_row} onFocus={() => setTarget("start")} onChange={e => changeMapping({ ...mapping, detail_start_row: Number(e.target.value) })} /></label>
          <label>{t("最后一条预留行 *")}<input type="number" min={2} max={300} value={mapping.detail_end_row} onFocus={() => setTarget("end")} onChange={e => changeMapping({ ...mapping, detail_end_row: Number(e.target.value) })} /></label>
        </fieldset><fieldset disabled={locked}><legend>{t("每条明细填入哪一列")}</legend>{detailFields.map(([field, label, required]) => <label key={field} className={target === `columns.${field}` ? "template-active-binding" : ""}>{t(label)}{required ? " *" : ""}<input aria-label={t("{0}列{1}", [t(label), required ? t("（必填）") : ""])} value={mapping.columns[field] ?? ""} maxLength={2} placeholder={t("例如 C")} onFocus={() => setTarget(`columns.${field}`)} onChange={e => bind("columns", field, e.target.value)} /></label>)}</fieldset>
        <fieldset disabled={locked}><legend>{t("表头和合计填入哪个单元格")}</legend>{cellFields.map(([field, label, required]) => <label key={field} className={target === `cells.${field}` ? "template-active-binding" : ""}>{t(label)}{required ? " *" : ""}<input aria-label={t("{0}位置{1}", [t(label), required ? t("（必填）") : ""])} value={mapping.cells[field] ?? ""} maxLength={5} placeholder={t("例如 H10")} onFocus={() => setTarget(`cells.${field}`)} onChange={e => bind("cells", field, e.target.value)} /></label>)}</fieldset><p className="muted">{t("客户、期间、状态放在明细上方；未填状态位置时随期间显示。合计放在明细下方，最多隔一行。有加税或调整时须有小计，调整另需说明；未指定税额和基数位置时随状态显示。系统送货标识不是客户原单号，旧单未记录的订单号不能自动补写。")}</p></div>
        <div className="template-sheet-pane"><p className="template-grid-hint">{t("当前填写：{0} · 浅蓝色为明细区", [(target === "start" ? t("第一条明细行") : target === "end" ? t("最后一条预留行") : t([...detailFields, ...cellFields].find(([field]) => field === selectedField)?.[1] ?? "")) ?? ""])}</p><CellGrid rows={inspection.grid} select={selectCell} selected={selected} start={mapping.detail_start_row} end={mapping.detail_end_row} /><p className="muted">{t("此表显示单元格内容，原文件的合并、字体和打印版式请在下载预览中核对。明细区的旧样例值会清空。")}</p></div></div>
        <div className="actions"><button className="secondary" disabled={locked || !complete} onClick={() => void generatePreview()}>{t("用本单数据预览")}</button>{!complete && <span className="muted">{t("填齐必填位置后可预览。")}</span>}</div>
        {preview && <section className="template-preview"><div className="template-import-heading"><div><h4>{t("3. 核对预览并保存")}</h4><p>{t("使用已保存的对账单 v{0}。这是未保存的模板预览。", [(preview.statement_version) ?? ""])}</p></div><button className="secondary" disabled={busy} onClick={() => savePreview(preview.content_base64)}>{t("下载预览 Excel")}</button></div><CellGrid rows={preview.grid} /><label className="template-confirm"><input type="checkbox" checked={confirmed} disabled={locked} onChange={e => setConfirmed(e.target.checked)} />{t("我已核对字段位置、明细范围与合计，可保存为该客户的模板。")}</label><button disabled={locked || !confirmed || !name.trim()} onClick={() => void save()}>{t("确认并保存客户模板")}</button><p className="muted">{t("每次保存都会保留为独立版本。需要默认使用时，再到「客户默认设置」保存。")}</p></section>}
      </>}
    </div>}
  </div>;
}
