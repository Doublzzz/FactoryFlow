import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Customer, type Material, type MaterialImportChoice, type MaterialImportFile, type MaterialImportInput, type MaterialImportInspection, type MaterialImportPreview, type MaterialImportResult, type Schemas } from "../api";
import { displayUnit } from "../units";
import { MaterialSelect } from "./MaterialSelect";
import "./material-import.css";

type Field = keyof Schemas["MaterialImportColumns"];
type Choice = MaterialImportChoice & { selected?: Material };
type Choices = Record<number, Choice>;
const fields: { key: Field; label: string; aliases: string[] }[] = [
  { key: "own_code", label: "我方料号", aliases: ["我方料号", "内部料号", "物料编号", "own", "own_code"] },
  { key: "name", label: "物料名称", aliases: ["名称", "物料名称", "品名", "name"] },
  { key: "specification", label: "规格", aliases: ["规格", "规格型号", "spec", "specification"] },
  { key: "unit", label: "基本单位", aliases: ["单位", "基本单位", "unit"] },
  { key: "customer_code", label: "客户料号", aliases: ["客户料号", "客户编号", "customer", "customer_code"] },
];
const issueLabels: Record<string, string> = {
  NAME_REQUIRED: "缺少物料名称，请在原文件补齐后重传，或跳过本行。",
  INVALID_NAME: "名称超过500字，请修正原文件或跳过。",
  INVALID_OWN_CODE: "我方料号超过100字，请修正原文件或跳过。",
  INVALID_CUSTOMER_CODE: "客户料号超过100字，请修正原文件或跳过。",
  INVALID_SPECIFICATION: "规格超过1,000字，请修正原文件或跳过。",
  INVALID_UNIT: "单位超过40字，请修正原文件或跳过。",
  UNSAFE_OWN_CODE: "我方料号不是可靠文本，或数字超过Excel精度；请在原文件改成正确文本。",
  UNSAFE_CUSTOMER_CODE: "客户料号不是可靠文本，或数字超过Excel精度；请在原文件改成正确文本。",
  NUMERIC_OWN_CODE_CONFIRM: "请核对并确认按读取到的数字导入我方料号。",
  NUMERIC_CUSTOMER_CODE_CONFIRM: "请核对并确认按读取到的数字导入客户料号。",
  TARGET_VERSION_CHANGED: "选中的物料已变化，请重新选择。",
  TARGET_CODE_DIFFERS: "选中物料的我方料号与文件不一致，请核对原文件或改选。",
  TARGET_INACTIVE: "这条物料已停用，请改选、修正原文件或跳过。",
  OWN_CODE_EXISTS: "我方料号已经存在，请核对后关联已有物料。",
  EXISTING_CODE_DIFFERS: "同一我方料号的资料不同。关联已有将保留库内资料，也可修正文件或跳过。",
  CANDIDATE_REVIEW: "已有同名或同规格物料，请选择关联已有、明确新建或跳过。",
  BATCH_CANDIDATE_REVIEW: "本批有同名或同规格的无编号物料，请明确选择新建、关联已有或跳过。",
  CUSTOMER_REQUIRED: "本行有客户料号，请在上方选择对应客户，或取消客户料号列。",
  CUSTOMER_CODE_CONFLICT: "客户料号已有不同对应或确认资料；本次不能覆盖，请修正原文件或跳过。",
  DUPLICATE_OWN_CODE: "文件内有重复的新我方料号，请保留一行，其余明确跳过。",
  DUPLICATE_CUSTOMER_CODE: "本批有重复客户料号，请保留一行，其余明确跳过。",
  DUPLICATE_ROW: "文件内有相同无编号明细，请明确选择新建、关联已有或跳过。",
};
const actionLabels = { create: "新建", reuse: "关联已有", skip: "跳过", pending: "待处理" };
const pageSize = 50;

async function encodeFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result.split(",")[1] ?? "") : reject(new Error("file"));
    reader.onerror = () => reject(new Error("file"));
    reader.readAsDataURL(file);
  });
}

export function MaterialImport({ customers, onClose, onImported }: {
  customers: Customer[]; onClose: () => void; onImported: (result: MaterialImportResult) => void;
}) {
  const [source, setSource] = useState<MaterialImportFile | null>(null);
  const [header, setHeader] = useState("1");
  const [inspection, setInspection] = useState<MaterialImportInspection | null>(null);
  const [columns, setColumns] = useState<Partial<Schemas["MaterialImportColumns"]>>({});
  const [customer, setCustomer] = useState("");
  const [choices, setChoices] = useState<Choices>({});
  const [preview, setPreview] = useState<{ data: MaterialImportPreview; choices: Choices } | null>(null);
  const [result, setResult] = useState<MaterialImportResult | null>(null);
  const [page, setPage] = useState(0);
  const [selectingRow, setSelectingRow] = useState<number | null>(null);
  const [busy, setBusy] = useState<"" | "inspect" | "preview" | "confirm">("");
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const picker = useRef<HTMLElement>(null);
  const pending = useRef<{ body: Schemas["MaterialImportConfirm"]; key: string } | null>(null);
  const locked = !!busy || uncertain;
  const current = !!preview && preview.choices === choices;
  useEffect(() => { if (selectingRow !== null) picker.current?.scrollIntoView({ block: "center" }); }, [selectingRow]);

  function clearPreview() { setPreview(null); setChoices({}); setPage(0); setSelectingRow(null); setError(""); }
  async function inspectFile(file: MaterialImportFile) {
    const value = await api.inspectMaterialImport(file);
    setSource(file); setInspection(value); clearPreview();
    const suggested: Partial<Schemas["MaterialImportColumns"]> = {};
    for (const field of fields) {
      const column = value.columns.find(item => field.aliases.includes(item.label.trim().toLowerCase()));
      if (column) suggested[field.key] = column.index;
    }
    setColumns(suggested);
  }
  async function selectFile(file: File | undefined) {
    if (!file || locked) return;
    setBusy("inspect"); setError(""); setSource(null); setInspection(null); clearPreview();
    try {
      if (!/\.(xlsx|csv)$/i.test(file.name)) { setError(msg("请选择 xlsx 或 UTF-8 CSV；旧xls请先另存为xlsx。")); return; }
      if (!file.size || file.size > 2 * 1024 * 1024) { setError(msg("文件须有内容，且不超过2 MiB。")); return; }
      const body = { filename: file.name, content_base64: await encodeFile(file), header_row: 1 };
      setSource(body); setHeader("1"); await inspectFile(body);
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(""); }
  }
  async function readHeader() {
    if (!source || locked) return;
    setBusy("inspect"); setError("");
    try { await inspectFile({ ...source, header_row: Number(header) }); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(""); }
  }
  function input(): MaterialImportInput | null {
    if (!source || !inspection || !columns.name) return null;
    return { ...source, columns: { ...columns, name: columns.name }, customer_id: customer || null, choices: Object.values(choices).map(({ selected: _selected, ...choice }) => choice) };
  }
  async function readPreview() {
    const body = input(); if (!body || locked) return;
    setBusy("preview"); setError("");
    try { setPreview({ data: await api.previewMaterialImport(body), choices }); setPage(0); }
    catch (failure) { setError(message(failure)); setPreview(null); }
    finally { setBusy(""); }
  }
  function choose(row: Schemas["MaterialImportPreviewRow"], action: string, selected?: Material) {
    setError("");
    if (!action) { setChoices(previous => { const next = { ...previous }; const confirmed = previous[row.row_number]?.confirmed_numeric_fields ?? []; if (confirmed.length) next[row.row_number] = { row_number: row.row_number, action: "default", confirmed_numeric_fields: confirmed }; else delete next[row.row_number]; return next; }); return; }
    const material = selected ?? choices[row.row_number]?.selected ?? row.material;
    if (action === "reuse" && !material) { setSelectingRow(row.row_number); return; }
    setChoices(previous => ({ ...previous, [row.row_number]: {
      row_number: row.row_number, action: action as MaterialImportChoice["action"],
      confirmed_numeric_fields: previous[row.row_number]?.confirmed_numeric_fields ?? [],
      ...(action === "reuse" && material ? { material_id: material.id, expected_material_version: material.version, selected: material } : {}),
    } }));
    setSelectingRow(null);
  }
  function confirmNumber(row: Schemas["MaterialImportPreviewRow"], field: "own_code" | "customer_code", checked: boolean) {
    const previous = choices[row.row_number];
    const material = previous?.selected ?? row.material;
    const action = previous?.action ?? "default";
    const confirmed = new Set(previous?.confirmed_numeric_fields ?? []);
    if (checked) confirmed.add(field); else confirmed.delete(field);
    setChoices(values => ({ ...values, [row.row_number]: {
      row_number: row.row_number, action, confirmed_numeric_fields: [...confirmed],
      ...(action === "reuse" && material ? { material_id: material.id, expected_material_version: material.version, selected: material } : {}),
    } }));
    setError("");
  }
  async function save() {
    if (busy) return;
    if (!uncertain) {
      const body = input(); if (!body || !preview || !current || !preview.data.ready) return;
      pending.current = { body: { ...body, preview_fingerprint: preview.data.preview_fingerprint }, key: crypto.randomUUID() };
    }
    if (!pending.current) return;
    setBusy("confirm"); setError("");
    try { setResult(await api.confirmMaterialImport(pending.current.body, pending.current.key)); setUncertain(false); setPage(0); }
    catch (failure) {
      setError(message(failure));
      // Authentication can fail before the command journal is consulted. It cannot
      // resolve an earlier unknown outcome: retain the original body and key.
      const resolved = failure instanceof ApiError && ["MATERIAL_IMPORT_STALE", "MATERIAL_IMPORT_UNRESOLVED"].includes(failure.code);
      const stillUncertain = !(failure instanceof ApiError) || failure.status >= 500 || uncertain && !resolved;
      setUncertain(stillUncertain);
      if (!stillUncertain && failure instanceof ApiError && failure.status === 409) setPreview(null);
    }
    finally { setBusy(""); }
  }
  const rows = result?.rows ?? preview?.data.rows ?? [];
  const pageRows = rows.slice(page * pageSize, (page + 1) * pageSize);
  const selecting = preview?.data.rows.find(row => row.row_number === selectingRow);
  return <section className="work-page material-import-page">
    <button className="back-button" onClick={() => result ? onImported(result) : onClose()} disabled={locked}>{t("返回物料池")}</button>
    <div className="page-heading"><div><h1>{result ? t("物料导入完成") : t("导入物料资料")}</h1><p>{result ? t("物料已保存，可用于以后订单；未增加库存。") : t("选择资料表，核对字段与重复项，再一次确认导入。")}</p></div></div>
    {result ? <><div className="work-panel import-result" role="status"><strong>{t("新建{0} 条 · 关联已有{1} 条 · 跳过{2} 行", [(result.created_count) ?? "", (result.reused_count) ?? "", (result.skipped_count) ?? ""])}</strong><p>{t("新增客户料号对应{0} 条。", [(result.mapping_count) ?? ""])}</p></div><div className="work-panel table-wrap"><table><thead><tr><th>{t("原表行号")}</th><th>{t("处理结果")}</th><th>{t("我方料号")}</th><th>{t("物料 / 原因")}</th></tr></thead><tbody>{pageRows.map(row => <tr key={row.row_number}><td>{row.row_number}</td><td>{t(actionLabels[row.action])}</td><td>{row.material?.own_code ?? "—"}</td><td>{row.material?.name ?? ("reason" in row ? row.reason : "")}</td></tr>)}</tbody></table></div><button onClick={() => onImported(result)}>{t("完成，返回物料池")}</button></> : <>
      <section className="work-panel import-file-section"><h2>{t("1. 选择资料表")}</h2><label className="import-file-label">{t("物料文件")}<input type="file" accept=".xlsx,.csv" disabled={locked} onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; void selectFile(file); }} /></label><p className="muted">{t("xlsx 或 UTF-8 CSV，最多2 MiB、2,000条数据、30列。料号建议在Excel中保存为文本，保留前导零。")}</p>
        {source && <div className="import-header-control"><strong>{source.filename}</strong><label>{t("表头所在行")}<input type="number" min={1} max={50} step={1} value={header} disabled={locked} onChange={event => { setHeader(event.target.value); setInspection(null); clearPreview(); }} /></label><button className="secondary" disabled={locked || !header} onClick={() => void readHeader()}>{t("读取表头")}</button></div>}
        {busy === "inspect" && <p role="status">{t("正在读取整份文件…")}</p>}
      </section>
      {inspection && <section className="work-panel"><h2>{t("2. 核对字段列")}</h2><p className="muted">{t("共读取{0} 条数据。名称必选，其余不导入的列留空。", [(inspection.data_row_count) ?? ""])}</p><div className="import-column-grid">{fields.map(field => <label key={field.key}>{t(field.label)}{field.key === "name" ? t("（必选）") : ""}<select value={columns[field.key] ?? ""} disabled={locked} onChange={event => { setColumns(previous => ({ ...previous, [field.key]: event.target.value ? Number(event.target.value) : null })); clearPreview(); }}><option value="">{field.key === "name" ? t("选择名称列") : t("不导入")}</option>{inspection.columns.map(column => <option key={column.index} value={column.index}>{t("第{0}列 ·{1}", [(column.index) ?? "", (column.label || t("无表头")) ?? ""])}</option>)}</select></label>)}</div>
        {columns.customer_code && <label className="import-customer">{t("客户料号属于哪位客户")}<select value={customer} disabled={locked} onChange={event => { setCustomer(event.target.value); clearPreview(); }}><option value="">{t("请选择已有客户")}</option>{customers.map(item => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></label>}
        <details className="import-source-sample"><summary>{t("查看原表样例（前20条）")}</summary><div className="table-wrap"><table><thead><tr><th>{t("原表行号")}</th>{inspection.columns.map(column => <th key={column.index}>{column.label || t("第{0}列", [column.index])}</th>)}</tr></thead><tbody>{inspection.samples.map(row => <tr key={row.row_number}><td>{row.row_number}</td>{row.values.map((value, index) => <td key={index}>{value}</td>)}</tr>)}</tbody></table></div></details>
        <button disabled={locked || !columns.name} onClick={() => void readPreview()}>{busy === "preview" ? t("正在核对…") : preview ? t("重新预览整批") : t("预览导入明细")}</button>
      </section>}
      {preview && <section className="work-panel import-preview"><div className="row-between"><h2>{t("3. 核对处理方式")}</h2><strong>{t("{0} 行", [(preview.data.rows.length) ?? ""])}</strong></div><p className="muted">{t("已有物料保持原资料；本次不会覆盖或自动合并。先逐行选择，最后统一导入。")}</p>
        {!current && <p className="warning" role="status">{t("处理方式已调整，请重新预览整批后再确认。")}</p>}
        {selecting && <section className="import-picker-panel" ref={picker} aria-label={t("第{0}行选择物料", [selecting.row_number])}><div className="row-between"><h3>{t("第{0}行 ·{1}", [(selecting.row_number) ?? "", (selecting.source.name) ?? ""])}</h3><button className="text-button" disabled={locked} onClick={() => setSelectingRow(null)}>{t("取消选择")}</button></div><MaterialSelect key={selecting.row_number} initialQuery={selecting.source.own_code ?? selecting.source.name} disabled={locked} actionLabel={t("选用此物料")} onSelect={material => choose(selecting, "reuse", material)} /></section>}
        <div className="table-wrap"><table className="material-import-table"><thead><tr><th>{t("原表行号")}</th><th>{t("名称 / 规格")}</th><th>{t("料号与单位")}</th><th>{t("本行处理")}</th><th>{t("核对提示")}</th></tr></thead><tbody>{preview.data.rows.slice(page * pageSize, (page + 1) * pageSize).map(row => {
          const choice = choices[row.row_number]; const dirty = choice !== preview.choices[row.row_number]; const target = choice?.selected ?? row.material;
          return <tr key={row.row_number}><td data-label={t("原表行号")}>{row.row_number}</td><td data-label={t("名称 / 规格")}><strong>{row.source.name || t("名称缺失")}</strong><small>{row.source.specification || t("规格暂缺")}</small></td><td data-label={t("料号与单位")}><span>{t("我方：{0}", [(row.source.own_code || t("自动编号")) ?? ""])}</span>{row.source.customer_code && <small>{t("客户：{0}", [(row.source.customer_code) ?? ""])}</small>}<small>{t("单位：{0}", [(displayUnit(row.source.unit)) ?? ""])}</small></td><td data-label={t("本行处理")}><label className="sr-only" htmlFor={`import-action-${row.row_number}`}>{t("第{0}行处理方式", [(row.row_number) ?? ""])}</label><select id={`import-action-${row.row_number}`} value={choice?.action === "default" ? "" : choice?.action ?? ""} disabled={locked} onChange={event => choose(row, event.target.value)}><option value="">{t("按预览判断：{0}", [(t(actionLabels[row.action])) ?? ""])}</option><option value="create">{t("明确新建")}</option><option value="reuse">{t("关联已有")}</option><option value="skip">{t("跳过本行")}</option></select>{(choice?.action === "reuse" || (!choice || choice.action === "default") && row.action === "reuse") && target && <small>{t("选用：{0} · {1}", [(target.own_code) ?? "", (target.name) ?? ""])}</small>}{choice?.action !== "skip" && <button className="text-button" disabled={locked} onClick={() => setSelectingRow(row.row_number)}>{t("查找已有物料")}</button>}{row.candidates.map(material => <button key={material.id} className="text-button import-candidate" disabled={locked || !material.active} onClick={() => choose(row, "reuse", material)}>{t("关联{0}", [(material.own_code) ?? ""])}<small>{material.name} · {material.specification || t("规格暂缺")}</small></button>)}</td><td data-label={t("核对提示")}>{dirty ? <small className="muted">{t("已调整，重新预览后检查。")}</small> : row.issues.length ? <ul className="import-issues">{row.issues.map(issue => <li key={issue}>{t(issueLabels[issue] ?? t("本行资料需要核对，请修正原文件或跳过。"))}</li>)}</ul> : <span className={row.action === "skip" ? "muted" : "success-text"}>{row.action === "skip" ? t("本行不会写入") : t("可以导入")}</span>}{row.numeric_fields.map(field => <label className="checkbox import-number-confirm" key={field.field}><input type="checkbox" disabled={locked || choice?.action === "skip"} checked={choice?.confirmed_numeric_fields?.includes(field.field) ?? false} onChange={event => confirmNumber(row, field.field, event.target.checked)} /><span>{t("确认{0}按“{1}”导入", [(field.field === "own_code" ? t("我方料号") : t("客户料号")) ?? "", (field.value) ?? ""])}<small>{t("Excel数值；显示格式{0}，不补猜前导零。", [(field.number_format || t("常规")) ?? ""])}</small></span></label>)}{row.warnings.includes("FILE_DUPLICATE") && <small className="warning-text">{t("文件内有重复项，已列出供核对。")}</small>}{row.warnings.includes("UNKNOWN_UNIT") && <small className="warning-text">{t("单位未识别，将保留原文。")}</small>}{row.warnings.includes("REUSE_KEEPS_EXISTING") && <small className="muted">{t("保留库内物料资料。")}</small>}</td></tr>;
        })}</tbody></table></div>
        <div className="actions import-confirm-actions"><button disabled={!!busy || !uncertain && (!current || !preview.data.ready || selectingRow !== null)} onClick={() => void save()}>{busy === "confirm" ? t("正在导入…") : uncertain ? t("重试本次导入") : t("确认导入整批")}</button>{!uncertain && <button className="secondary" disabled={!!busy} onClick={() => void readPreview()}>{t("重新预览整批")}</button>}</div>
        {!preview.data.ready && current && <p className="warning">{t("请处理待核对行，或明确跳过；至少保留一行导入。")}</p>}
      </section>}
    </>}
    {rows.length > pageSize && <nav className="actions import-pagination" aria-label={t("导入明细分页")}><button className="secondary" disabled={locked || page === 0} onClick={() => setPage(value => value - 1)}>{t("上一页")}</button><span>{t("第{0}页 / 共{1}页 · 所有行的选择都会保留", [(page + 1), (Math.ceil(rows.length / pageSize)) ?? ""])}</span><button className="secondary" disabled={locked || (page + 1) * pageSize >= rows.length} onClick={() => setPage(value => value + 1)}>{t("下一页")}</button></nav>}
    {error && <p role="alert" className="error">{t(error)}</p>}{uncertain && <p role="status" className="warning">{t("尚未确认本次是否已保存。请重试本次导入，系统会返回原结果，不会重复建档。")}</p>}
  </section>;
}
