import { getLocale, outputLanguage, msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Customer, type Statement, type StatementCandidate, type StatementDraft, type StatementExport, type StatementSettings, type StatementAdjustment, type StatementTemplate } from "../api";

import { ItemIdentity } from "./ItemIdentity";
import { displayUnit } from "../units";
import { StatementLifecycle } from "./StatementLifecycle";
import { StatementTemplateImport } from "./StatementTemplateImport";

type Row = { source: StatementCandidate; quantity: string; unit_price: string; external_document_number: string; reason: string };
const keyOf = (row: { delivery_id: string; order_line_id: string }) => `${row.delivery_id}/${row.order_line_id}`;
const taxNames = { included: "含税价，不另加税", untaxed_final: "未税最终价，不另加税", add_tax: "未税价，另加税" };
const warnings: Record<string, string> = { PRICE_REQUIRED: "有明细尚未定价，最终金额留空；仍可导出待定价草稿。", ADJUSTMENT_REVIEW_REQUIRED: "来源已失效的调整需要删除或重新关联，处理前不能导出。", NEGATIVE_TOTAL_REVIEW_REQUIRED: "最终金额为负，请核对调整后再导出。" };
function validPrice(value: string | null) { return value && /^\d{1,12}(\.\d{1,4})?$/.test(value) ? value : ""; }
const templateLabel = (item: StatementExport) => `${item.customer_template_id ? item.template_name : item.template_id === "delivery-v1" ? t("按送货分组") : t("标准明细")}${item.customer_template_id ? t(" · 模板 v{0}", [item.template_version]) : ""} · ${outputLanguage(item.locale)}`;

export function StatementEditor({ customer, start, end, existing, canWrite, onBack, onGuardChange }: {
  customer: Customer; start: string; end: string; existing: Statement | null; canWrite: boolean;
  onBack: () => void; onGuardChange: (blocked: boolean) => void;
}) {
  const [saved, setSaved] = useState(existing);
  const [rows, setRows] = useState<Row[]>([]);
  const [candidates, setCandidates] = useState<StatementCandidate[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [overlap, setOverlap] = useState(false);
  const [taxMode, setTaxMode] = useState<StatementDraft["tax_mode"]>("untaxed_final");
  const [taxRate, setTaxRate] = useState("0");
  const [adjustments, setAdjustments] = useState<StatementAdjustment[]>([]);
  const [reason, setReason] = useState("");
  const [settings, setSettings] = useState<StatementSettings | null>(null);
  const [template, setTemplate] = useState("standard-v1");
  const [templates, setTemplates] = useState<StatementTemplate[]>([]);
  const [templateCursor, setTemplateCursor] = useState<string | null>(null);
  const [cycleDay, setCycleDay] = useState("");
  const [exports, setExports] = useState<StatementExport[]>([]);
  const [exportCursor, setExportCursor] = useState<string | null>(null);
  const [editorBusy, setBusy] = useState(true);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [templateBusy, setTemplateBusy] = useState(false);
  const busy = editorBusy || lifecycleBusy || templateBusy;
  const [dirty, setDirty] = useState(false);
  const [reopening, setReopening] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<{ signature: string; key: string } | null>(null);
  const inflight = useRef(false);
  const retryAction = useRef<(() => Promise<void>) | null>(null);
  const exportResult = useRef<HTMLDivElement>(null);
  const revealExportResult = useRef(false);
  const closed = !!saved && saved.status !== "draft" && !reopening;
  const locked = !canWrite || busy || uncertain || closed;
  const templateChoice: { template_id: StatementSettings["template_id"]; customer_template_id: string | null } = template === "standard-v1" || template === "delivery-v1" ? { template_id: template, customer_template_id: null } : { template_id: "customer-v1", customer_template_id: template };
  function commandKey(body: unknown) {
    const signature = JSON.stringify(body);
    if (pending.current?.signature !== signature) pending.current = { signature, key: crypto.randomUUID() };
    return pending.current.key;
  }
  function adopt(data: Statement) {
    setSaved(data); setTaxMode(data.tax_mode); setTaxRate(data.tax_rate);
    setRows(data.lines.filter(line => ["included", "deferred"].includes(line.status)).map(line => ({
      source: { ...line.source, available_quantity: line.source.quantity, cross_period: line.source.delivery_date < start },
      external_document_number: line.external_document_number ?? "", quantity: line.quantity, unit_price: line.unit_price ?? "", reason: line.reason,
    })));
    setAdjustments(data.adjustments.map(({ status: _status, ...item }) => item));
    setReason(""); setDirty(false); setReopening(false);
  }
  async function exportList(id: string, more = false) {
    const page = await api.statementExports(id, more ? exportCursor ?? undefined : undefined);
    setExports(old => more ? [...old, ...page.items] : page.items); setExportCursor(page.next_cursor);
  }
  async function initialize(strict = false) {
    setBusy(true); setError("");
    try {
      const id = saved?.id;
      const [preference, data, candidatePage, templatePage] = await Promise.all([
        api.statementSettings(customer.id), id ? api.statement(id) : Promise.resolve(null),
        api.statementCandidates(customer.id, start, end, id),
        api.statementTemplates(customer.id),
      ]);
      setSettings(preference); setTemplate(preference?.customer_template_id ?? preference?.template_id ?? "standard-v1"); setCycleDay(preference?.cycle_day?.toString() ?? "");
      const defaultTemplate = preference?.customer_template_id && !templatePage.items.some(item => item.id === preference.customer_template_id) ? await api.statementTemplate(customer.id, preference.customer_template_id) : null;
      setTemplates(defaultTemplate ? [...templatePage.items, defaultTemplate] : templatePage.items); setTemplateCursor(templatePage.next_cursor);
      setCandidates(candidatePage.items); setCursor(candidatePage.next_cursor);
      setOverlap(candidatePage.overlapping_statements.some(other => other !== id));
      if (data) { adopt(data); await exportList(data.id); }
      else { setRows([]); setAdjustments([]); setTaxMode(preference?.tax_mode ?? "untaxed_final"); setTaxRate(preference?.tax_rate ?? "0"); setDirty(false); setReason(""); }
    } catch (failure) { setError(message(failure)); if (strict) throw failure; } finally { setBusy(false); }
  }
  useEffect(() => { void initialize(); }, []);
  useEffect(() => {
    if (!editorBusy && revealExportResult.current) {
      exportResult.current?.scrollIntoView({ block: "nearest" });
      revealExportResult.current = false;
    }
  }, [editorBusy, exports]);
  useEffect(() => { onGuardChange(busy || dirty || uncertain || reopening); return () => onGuardChange(false); }, [busy, dirty, uncertain, reopening, onGuardChange]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => { if (dirty || uncertain || busy) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", leave); return () => window.removeEventListener("beforeunload", leave);
  }, [dirty, uncertain, busy]);
  function change(action: () => void) { action(); setDirty(true); setNotice(""); }
  async function run(action: () => Promise<void>, isCommand = false) {
    if (inflight.current) return;
    if (isCommand) retryAction.current = action;
    inflight.current = true; setBusy(true); setError(""); setNotice("");
    try { await action(); if (isCommand) { pending.current = null; retryAction.current = null; setUncertain(false); } }
    catch (failure) {
      setError(message(failure));
      if (isCommand) {
        // Authentication/validation may fail before the journal sees the original key.
        // Only known checks after claim can resolve a previously unknown outcome.
        const resolved = failure instanceof ApiError && ["VERSION_CONFLICT", "STATEMENT_STATE_CONFLICT", "STATEMENT_EXPORT_REVIEW_REQUIRED"].includes(failure.code);
        setUncertain(!(failure instanceof ApiError) || failure.status >= 500 || failure.status === 408 || uncertain && !resolved);
      }
    } finally { inflight.current = false; setBusy(false); }
  }
  function editRow(index: number, field: "quantity" | "unit_price" | "external_document_number" | "reason", value: string) {
    change(() => setRows(old => old.map((row, i) => i === index ? { ...row, [field]: value } : row)));
  }
  function save() {
    const body: StatementDraft = { customer_id: customer.id, period_start: start, period_end: end, tax_mode: taxMode, tax_rate: taxRate, adjustments, reason,
      lines: rows.map(row => ({ delivery_id: row.source.delivery_id, order_line_id: row.source.order_line_id, external_document_number: row.external_document_number, quantity: row.quantity, unit_price: row.unit_price || null, reason: row.reason })) };
    void run(async () => {
      const payload = saved ? { ...body, expected_version: saved.version } : body;
      const key = commandKey({ action: reopening ? "reopen" : "save", id: saved?.id, ...payload });
      const result = saved ? await api.saveStatement(saved.id, { ...body, expected_version: saved.version }, key, reopening) : await api.createStatement(body, key);
      adopt(result); setNotice(msg("对账草稿已保存，金额已更新。"));
      // Reads are independent of command completion: a refresh failure must not replay a new save.
      pending.current = null; setUncertain(false);
      await exportList(result.id).catch(() => setNotice(msg("草稿已保存。导出记录暂未刷新，请重新读取。")));
    }, true);
  }
  function createExport() {
    if (!saved) return;
    const outputLocale = templateChoice.customer_template_id ? "zh-CN" : getLocale();
    void run(async () => {
      const key = commandKey({ action: "export", id: saved.id, version: saved.version, template, locale: outputLocale });
      const item = await api.createStatementExport(saved.id, saved.version, templateChoice.template_id, key, outputLocale, templateChoice.customer_template_id);
      revealExportResult.current = true;
      setExports(old => [item, ...old.filter(e => e.id !== item.id)]);
      // Identity is durable now; retry generation by this ID, never create another snapshot.
      pending.current = null; setUncertain(false);
      const result = await api.generateStatementExport(item.id).catch(() => null);
      if (result) {
        setExports(old => old.map(e => e.id === result.id ? result : e));
        if (result.status === "ready" && result.locale !== "source" && result.locale !== getLocale()) setNotice(msg("已生成{0} Excel，请在全部导出记录中下载。", [msg(result.locale === "en" ? "英文" : "中文")]));
      }
    }, true);
  }
  const currentExport = exports.find(item => item.current && item.statement_version === saved?.version && item.template_id === templateChoice.template_id && (item.customer_template_id ?? null) === templateChoice.customer_template_id && item.locale === (templateChoice.customer_template_id ? "source" : getLocale()));
  const selectedKeys = new Set(rows.map(row => keyOf(row.source)));
  const adjustmentSources = [...new Map([...rows.map(row => row.source), ...(saved?.settlement_lines.map(line => line.source) ?? [])].map(source => [keyOf(source), source])).values()];
  const adjustmentSourceKeys = new Set(adjustmentSources.map(keyOf));
  const choices = candidates.filter(c => !selectedKeys.has(keyOf(c)) && !/^0(?:\.0+)?$/.test(c.available_quantity));
  const editable = canWrite && !closed;
  const staleLines = saved?.lines.filter(line => line.status === "source_void") ?? [];
  return <section className="statements-page statement-editor">
    <button className="back-button" disabled={busy || dirty || uncertain || reopening} onClick={onBack}>{t("返回客户对账")}</button>
    <div className="page-heading"><div><h1>{customer.full_name}</h1><p>{t("对账期间：{0} 至{1}", [(start) ?? "", (end) ?? ""])}<span className="statement-version">{saved ? t("v{0} · {1}", [saved.version, closed ? saved.status === "confirmed" ? t("正式结算") : saved.status === "void" ? t("已作废") : t("已放弃") : t("对账草稿")]) : t("新对账草稿")}</span></p></div><span className={`statement-save-state${dirty ? " is-dirty" : ""}`}>{dirty ? t("有未保存修改") : saved ? t("当前版本已保存") : t("尚未保存")}</span></div>
    <div className="statement-section-nav"><nav aria-label={t("本单操作区域")}><a href="#statement-review">{t("明细与金额")}</a>{saved ? <><a href="#statement-export">{t("Excel 导出")}</a><a href="#statement-lifecycle">{t("认可与结算")}</a></> : <><span>{t("Excel 导出")}</span><span>{t("认可与结算")}</span></>}</nav><div className="actions">
      {editable && <button disabled={busy || uncertain} onClick={save}>{editorBusy || lifecycleBusy ? t("处理中…") : reopening ? t("重开并保存") : t("保存草稿")}</button>}
    </div></div>
    {error && <p className="error" role="alert">{t(error)}</p>}{notice && <p className="success" role="status">{t(notice)}</p>}
    {uncertain && <p className="warning">{t("尚未确认操作结果。输入已保留并锁定。")}<button className="secondary" disabled={busy} onClick={() => { if (retryAction.current) void run(retryAction.current, true); }}>{t("重试刚才的操作")}</button></p>}
    {(editorBusy || lifecycleBusy) && <p className="muted" role="status">{t("正在处理…")}</p>}
    {templateBusy && !editorBusy && !lifecycleBusy && <p className="muted" role="status">{t("正在配置客户模板，请保存或取消本次导入后继续处理本单。")}</p>}
    {overlap && <p className="warning">{t("该期间与已有草稿重叠。下方可用量已扣除其他草稿占用，请核对是否需要回到原对账单。")}</p>}
    {!!staleLines.length && <p className="warning">{t("{0} 条来源送货已作废，已退出金额计算；原明细保留在变更记录中。", [(staleLines.length) ?? ""])}</p>}
    <section id="statement-review" className="statement-panel" aria-labelledby="statement-review-heading" tabIndex={-1}>
    <header className="statement-panel-heading"><div><h2 id="statement-review-heading">{t("明细与金额")}{!!rows.length && <span className="count">{t("{0} 项待认可", [(rows.length) ?? ""])}</span>}</h2><p>{closed ? t("查看本单保存的明细与金额，原版本可在下方变更记录中追查。") : t("先核对数量与单价，再保存草稿。导出使用已保存的内容。")}</p></div></header>
    {!!rows.length && <div className="table-wrap statement-lines statement-lines-compact"><table><colgroup><col className="st-date"/><col className="st-item"/><col className="st-unit"/><col className="st-num"/><col className="st-num"/><col className="st-action"/></colgroup><thead><tr><th>{t("送货日期")}</th><th>{t("货物 / 单号与调整")}</th><th>{t("单位")}</th><th className="numeric">{t("本次数量")}</th><th className="numeric">{t("结算单价（元）")}</th><th>{t("操作")}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={keyOf(row.source)}>
      <td>{row.source.delivery_date}{row.source.cross_period && <small className="warning-text">{t("跨期未结")}</small>}</td><td><ItemIdentity line={row.source}/><details className="statement-row-details"><summary>{t("单号与调整原因{0}", [(row.external_document_number || row.reason ? t(" · 已填写") : "") ?? ""])}</summary><label>{t("客户外部送货／退货单号")}<input aria-label={t("第{0}行客户外部单号", [index + 1])} maxLength={120} placeholder={t("可留空")} value={row.external_document_number} disabled={locked} onChange={e => editRow(index, "external_document_number", e.target.value)} /></label><label>{t("调整原因")}<input aria-label={t("第{0}行调整原因", [index + 1])} maxLength={500} placeholder={t("部分数量、改价时必填")} value={row.reason} disabled={locked} onChange={e => editRow(index, "reason", e.target.value)} /></label></details></td><td>{displayUnit(row.source.canonical_unit ?? row.source.source_unit)}</td>
      <td className="numeric"><input aria-label={t("第{0}行本次数量", [index + 1])} inputMode="decimal" maxLength={32} value={row.quantity} disabled={locked} onChange={e => editRow(index, "quantity", e.target.value)} /></td>
      <td className="numeric"><input aria-label={t("第{0}行结算单价", [index + 1])} inputMode="decimal" maxLength={32} placeholder={t("待定价")} value={row.unit_price} disabled={locked} onChange={e => editRow(index, "unit_price", e.target.value)} />{row.source.source_unit_price !== null && <small title={t("订单原版本的来源价格")}>{t("来源{0}", [(row.source.source_unit_price) ?? ""])}</small>}</td>
      <td>{editable && <button className="text-button" aria-label={t("移除第{0}行", [index + 1])} disabled={locked} onClick={() => change(() => setRows(rows.filter((_, i) => i !== index)))}>{t("移除")}</button>}</td>
    </tr>)}</tbody></table></div>}
    {!rows.length && <p className="empty-state">{saved?.settlement_lines.length ? t("本期已选认可明细见下方「认可与结算」。") : closed ? t("本次明细已释放，原版本保留在变更记录中。") : t("从下方待对账送货中加入明细。数量和价格可逐项核对。")}</p>}
    {editable && <p className="statement-section-note">{t("数量填 0 表示草稿暂缓。客户已认可但要转下期，请在「认可与结算」中办理。")}</p>}
    {editable && <details className="statement-candidates statement-candidates-compact" open={!rows.length}><summary>{t("待对账送货 · 已载入{0} 项可选", [(choices.length) ?? ""])}</summary>
      <p className="muted">{t("包含本期送货和以前未结完的数量。可逐条加入，避免把不属于本次的货物一起结算。")}</p>
      {!!choices.length && <div className="table-wrap"><table><thead><tr><th>{t("送货日期")}</th><th>{t("货物")}</th><th className="numeric">{t("可用数量")}</th><th className="numeric">{t("来源单价（元）")}</th><th>{t("操作")}</th></tr></thead><tbody>{choices.map(c => <tr key={keyOf(c)}><td>{c.delivery_date}{c.cross_period && <small className="warning-text">{t("跨期未结")}</small>}</td><td><ItemIdentity line={c}/></td><td className="numeric">{c.available_quantity} {displayUnit(c.canonical_unit ?? c.source_unit)}</td><td className="numeric">{c.source_unit_price ?? t("待定价")}</td><td><button className="text-button" disabled={locked || rows.length >= 200} onClick={() => change(() => setRows([...rows, { source: c, quantity: c.available_quantity, unit_price: validPrice(c.source_unit_price), external_document_number: "", reason: "" }]))}>{t("加入")}</button></td></tr>)}</tbody></table></div>}
      {!choices.length && <p className="muted">{t("当前页没有可加入的送货明细。")}</p>}{cursor && <button className="secondary" disabled={locked} onClick={() => void run(async () => { const page = await api.statementCandidates(customer.id, start, end, saved?.id, cursor); setCandidates(old => [...old, ...page.items]); setCursor(page.next_cursor); })}>{t("继续加载送货")}</button>}
    </details>}
    <div className="statement-bottom"><div>
      <details className="statement-options"><summary>{t("税费与其他调整{0}", [(adjustments.length ? t(" · {0} 项", [adjustments.length]) : "") ?? ""])}</summary>
        <div className="statement-filters"><label>{t("计价方式")}<select value={taxMode} disabled={locked} onChange={e => change(() => setTaxMode(e.target.value as StatementDraft["tax_mode"]))}>{Object.entries(taxNames).map(([key, title]) => <option key={key} value={key}>{t(title)}</option>)}</select></label><label>{t("税率（%）")}<input inputMode="decimal" value={taxRate} disabled={locked || taxMode !== "add_tax"} maxLength={16} onChange={e => change(() => setTaxRate(e.target.value))} /></label></div>
        {adjustments.map((item, index) => <div className="statement-adjustment" key={index}>
          <label>{t("项目")}<input value={item.kind} maxLength={80} disabled={locked} onChange={e => change(() => setAdjustments(adjustments.map((a, i) => i === index ? { ...a, kind: e.target.value } : a)))} /></label>
          <label>{t("金额（扣减填负数）")}<input inputMode="decimal" value={item.amount} maxLength={40} disabled={locked} onChange={e => change(() => setAdjustments(adjustments.map((a, i) => i === index ? { ...a, amount: e.target.value } : a)))} /></label>
          <label>{t("阶段")}<select value={item.stage} disabled={locked} onChange={e => change(() => setAdjustments(adjustments.map((a, i) => i === index ? { ...a, stage: e.target.value as "before_tax" | "after_tax" } : a)))}><option value="before_tax">{t("税前")}</option><option value="after_tax">{t("税后")}</option></select></label>
          <label>{t("关联明细")}<select value={item.delivery_id ? `${item.delivery_id}/${item.order_line_id}` : ""} disabled={locked} onChange={e => change(() => setAdjustments(adjustments.map((a, i) => { if (i !== index) return a; const { delivery_id: _d, order_line_id: _o, ...rest } = a; const [delivery_id, order_line_id] = e.target.value.split("/"); return delivery_id && order_line_id ? { ...rest, delivery_id, order_line_id } : rest; })))}><option value="">{t("整单调整")}</option>{item.delivery_id && !adjustmentSourceKeys.has(`${item.delivery_id}/${item.order_line_id}`) && <option value={`${item.delivery_id}/${item.order_line_id}`}>{t("来源失效，请处理")}</option>}{adjustmentSources.map(source => <option key={keyOf(source)} value={keyOf(source)}>{source.delivery_date} · {source.item_code ?? ""} {source.item_name ?? source.description} · {selectedKeys.has(keyOf(source)) ? t("草稿来源") : t("认可预留来源")}</option>)}</select></label>
          <label>{t("调整说明")}<input value={item.reason} maxLength={500} disabled={locked} onChange={e => change(() => setAdjustments(adjustments.map((a, i) => i === index ? { ...a, reason: e.target.value } : a)))} /></label>
          {editable && <button className="text-button" disabled={locked} onClick={() => change(() => setAdjustments(adjustments.filter((_, i) => i !== index)))}>{t("删除调整")}</button>}
        </div>)}
        {editable && <button className="secondary" disabled={locked || adjustments.length >= 100} onClick={() => change(() => setAdjustments([...adjustments, { kind: "", amount: "", stage: "after_tax", reason: "" }]))}>{t("添加调整")}</button>}
      </details>
      {editable && <label className="statement-change-reason">{t("本次修改说明")}<input value={reason} disabled={locked} maxLength={500} placeholder={t("移除明细、修改税费或调整、重开时必填")} onChange={e => change(() => setReason(e.target.value))} /></label>}
      <div className="actions"><button className="text-button" disabled={busy || uncertain} onClick={() => void initialize()}>{dirty ? t("放弃未保存修改并重新读取") : t("刷新草稿与送货")}</button></div>
    </div><aside className="statement-totals"><h2>{dirty ? t("上次保存的金额") : saved?.status === "confirmed" ? t("正式结算金额") : t("本期金额（含待结算明细）")}</h2>{saved ? <><dl><div><dt>{t("已定价小计")}</dt><dd>{saved.calculation.priced_subtotal}</dd></div><div><dt>{t("税额")}</dt><dd>{saved.calculation.tax_amount ?? t("待核对")}</dd></div><div className="statement-total"><dt>{t("最终金额（元）")}</dt><dd>{saved.calculation.total ?? t("待核对")}</dd></div></dl>{saved.calculation.warnings.map(code => <p className="warning-text" key={code}>{t(warnings[code] ?? code)}</p>)}</> : <p className="muted">{t("保存草稿后计算金额。")}</p>}{dirty && <p className="warning-text">{t("有未保存修改，保存后更新金额与导出版本。")}</p>}</aside></div>
    </section>
    {saved && <section id="statement-export" className="statement-panel statement-export-section" aria-labelledby="statement-export-heading" tabIndex={-1}><header className="statement-panel-heading"><div><h2 id="statement-export-heading">{t("Excel 导出")}</h2><p>{t("下载后自行发给客户，再登记发送记录。")}</p></div></header>
      <div className="statement-filters"><label>{t("Excel 排版")}<select value={template} disabled={busy || uncertain} onChange={e => setTemplate(e.target.value)}><option value="standard-v1">{t("标准明细")}</option><option value="delivery-v1">{t("按送货分组")}</option>{templates.map(item => <option key={item.id} value={item.id}>{t("{0} · 模板 v{1}", [(item.name) ?? "", (item.version) ?? ""])}</option>)}</select></label>{canWrite && (saved.status === "draft" || saved.status === "confirmed") && <button className={currentExport?.status === "ready" ? "secondary" : undefined} disabled={busy || uncertain || dirty || reopening || saved.calculation.warnings.some(c => c !== "PRICE_REQUIRED")} onClick={createExport}>{editorBusy ? t("正在处理…") : saved.status === "confirmed" ? t("生成正式 Excel") : t("生成 Excel 草稿")}</button>}</div>
      {templateCursor && <button className="text-button" disabled={busy || uncertain} onClick={() => void run(async () => { const page = await api.statementTemplates(customer.id, templateCursor); setTemplates(old => [...old, ...page.items.filter(item => !old.some(existing => existing.id === item.id))]); setTemplateCursor(page.next_cursor); })}>{t("加载更早的客户模板")}</button>}
      {canWrite && (saved.status === "draft" || saved.status === "confirmed") && <StatementTemplateImport statement={saved} disabled={editorBusy || lifecycleBusy || dirty || uncertain || reopening} onGuardChange={setTemplateBusy} onImported={item => { setTemplates(old => [item, ...old.filter(existing => existing.id !== item.id)]); setTemplate(item.id); setNotice(msg("已保存 {0} · 模板 v{1}，现可生成 Excel。客户默认设置尚未更改。", [item.name, item.version])); }} />}
      {currentExport && !dirty && !reopening && <div ref={exportResult} className={`statement-export-result ${currentExport.status === "ready" ? "success" : "warning"}`}>
        <div role="status" aria-live="polite"><strong>{currentExport.status === "ready" ? t("Excel 已生成") : currentExport.status === "failed" ? currentExport.error_code === "STATEMENT_TEMPLATE_TEXT_LIMIT" ? t("此模板无法完整显示文字") : t("Excel 生成失败，可重试") : t("导出记录已保存，Excel 尚未生成")}</strong><p>{currentExport.status === "ready" ? t("v{0} · {1}。点击下载，保存到电脑后即可查看。", [currentExport.statement_version, templateLabel(currentExport)]) : currentExport.error_code === "STATEMENT_TEMPLATE_TEXT_LIMIT" ? t("文字超出模板单行可打印范围。请调整模板字段宽度后导入新版本，再生成新文件。") : t("记录已保留，无需重复创建；可在下方重试生成。")}</p></div>
        {currentExport.status === "ready" && <button disabled={busy || uncertain} onClick={() => void run(() => api.downloadStatementExport(currentExport))}>{t("立即下载 Excel")}</button>}
      </div>}
      {dirty && <p className="muted">{t("请先保存修改，再生成新文件。")}</p>}
      <p className="muted">{t("客户模板保留原有文字与系统注记；内置 Excel 使用当前界面语言。")}</p>
      {!exports.length && <p className="muted">{t("尚无导出记录。")}</p>}
      {!!exports.length && <details className="statement-export-history" open={currentExport?.status === "failed" || currentExport?.status === "pending"}><summary>{t("查看全部导出记录")}<span className="count">{t("{0} 份已载入", [(exports.length) ?? ""])}</span></summary><p className="muted">{t("每份文件保留生成时的内容。草稿改变后，旧文件仍可在这里下载。")}</p>
      <ul className="statement-export-list">{exports.map(item => <li key={item.id}><div><strong>v{item.statement_version} · {templateLabel(item)}</strong><small>{new Date(item.created_at).toLocaleString(getLocale())} · {item.current ? item.statement_status === "confirmed" ? t("当前正式版本") : t("当前草稿版本") : t("历史版本")} · {item.status === "ready" ? t("文件已生成") : item.status === "failed" ? t("生成失败，可重试") : t("等待生成")}</small></div><div className="actions">{item.status === "ready" ? <button className="secondary" disabled={busy || uncertain} onClick={() => void run(() => api.downloadStatementExport(item))}>{item.current ? t("下载 Excel") : t("下载历史文件")}</button> : canWrite && <button className="secondary" disabled={busy || uncertain} onClick={() => void run(async () => { const updated = await api.generateStatementExport(item.id); revealExportResult.current = item.id === currentExport?.id; setExports(old => old.map(e => e.id === item.id ? updated : e)); })}>{t("重试生成{0}", [(!item.current ? t("历史文件") : "") ?? ""])}</button>}</div></li>)}</ul>
      {exportCursor && <button className="text-button" disabled={busy || uncertain} onClick={() => void run(() => exportList(saved.id, true))}>{t("加载更早导出")}</button>}
      </details>}
    </section>}
    {saved && <StatementLifecycle statement={saved} exports={exports} canWrite={canWrite} disabled={editorBusy || templateBusy || dirty || uncertain || reopening} onRefresh={() => initialize(true)} onGuardChange={setLifecycleBusy} />}
    <section className="statement-secondary-panel" aria-label={t("设置与变更记录")}><h2>{t("设置与变更记录")}</h2>
    {canWrite && <details className="statement-options"><summary>{t("客户默认设置")}</summary><p className="muted">{t("记住当前计价方式、税率和 Excel 排版。税费用于以后新建的草稿，排版用于之后的导出，旧文件保持原样。")}</p><div className="statement-filters"><label>{t("对账截止日（可留空）")}<input type="number" min={1} max={31} value={cycleDay} disabled={busy || uncertain} onChange={e => setCycleDay(e.target.value)} /></label><button className="secondary" disabled={busy || uncertain} onClick={() => void run(async () => { const body = { expected_version: settings?.version ?? 0, cycle_day: cycleDay ? Number(cycleDay) : null, tax_mode: taxMode, tax_rate: taxRate, ...templateChoice, reason: "人工保存客户默认设置" }; const updated = await api.saveStatementSettings(customer.id, body, commandKey({ action: "settings", ...body })); setSettings(updated); setNotice(msg("客户默认设置已保存。")); }, true)}>{t("记住这些设置")}</button></div></details>}
    {saved && <details className="statement-options"><summary>{t("变更记录与作废")}</summary><ol>{saved.history.map(item => <li key={item.version}>v{item.version} · {({ create: t("创建"), save: t("保存"), reopen: t("重开"), abandon: t("放弃"), void: t("作废"), source_void: t("来源送货作废") } as Record<string, string>)[item.action] ?? item.action} · {item.reason || t("无额外说明")}<details><summary>{t("查看当时明细")}</summary><div className="table-wrap"><table><thead><tr><th>{t("货物")}</th><th>{t("规格")}</th><th>{t("外部单号")}</th><th>{t("数量")}</th><th>{t("单价")}</th><th>{t("状态")}</th></tr></thead><tbody>{[...(item.snapshot.lines as Statement["lines"] | undefined ?? []), ...(item.snapshot.settlement_lines as Statement["settlement_lines"] | undefined ?? [])].map((line, index) => <tr key={`${keyOf(line)}/${index}`}><td>{line.source.item_code} {line.source.item_name ?? line.source.description}</td><td>{line.source.specification}</td><td>{line.external_document_number || "—"}</td><td>{line.quantity}</td><td>{line.unit_price ?? t("待定价")}</td><td>{({ included: t("计入"), deferred: t("暂缓"), released: t("已释放"), source_void: t("来源已作废") })[line.status]}</td></tr>)}</tbody></table></div></details></li>)}</ol>
      {canWrite && !dirty && saved.status !== "confirmed" && <div className="actions">{closed ? <button className="secondary" disabled={busy || uncertain} onClick={() => { setReopening(true); setDirty(true); setNotice(msg("重新选择本次要结算的送货，填写修改说明，再重开并保存。")); }}>{t("重开此对账单")}</button> : <><label>{t("作废或放弃原因")}<input aria-label={t("作废或放弃原因")} value={reason} maxLength={500} disabled={busy || uncertain} onChange={e => setReason(e.target.value)} /></label><button className="danger" disabled={busy || uncertain || !reason.trim() || reopening} onClick={() => void run(async () => { const body = { expected_version: saved.version, reason }; const key = commandKey({ action: exports.length ? "void" : "abandon", id: saved.id, ...body }); const data = await api.closeStatement(saved.id, body, key, !!exports.length); adopt(data); pending.current = null; setUncertain(false); await exportList(data.id).catch(() => setNotice(msg("状态已保存，请刷新导出记录。"))); }, true)}>{exports.length ? t("作废对账草稿") : t("放弃草稿")}</button></>}</div>}
    </details>}
    </section>
  </section>;
}
