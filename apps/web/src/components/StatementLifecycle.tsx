import { getLocale, outputLanguage, msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Schemas, type Statement, type StatementExport } from "../api";
import "./statement-lifecycle.css";
import { displayUnit } from "../units";

type Operation = "sent" | "feedback" | "approve" | "review" | "reserve" | "release" | "claim" | "defer" | "correctApproval" | "settle" | "correctSettlement";
const names: Record<Operation, string> = { sent: "登记已发给客户", feedback: "记录客户回复", approve: "确认客户认可", review: "留待核对", reserve: "选入本期结算", release: "取消本期结算安排", claim: "继续处理待核对货物", defer: "改到以后结算", correctApproval: "更正客户认可", settle: "确认本期正式结算", correctSettlement: "更正正式结算" };
const commonOperations: Operation[] = ["sent", "feedback", "approve", "reserve", "settle"];
const otherOperations: Operation[] = ["review", "claim", "release", "defer", "correctApproval", "correctSettlement"];
const exportName = (item: StatementExport) => `${item.customer_template_id ? t("{0} · 模板第{1}版", [item.template_name, item.template_version]) : item.template_id === "delivery-v1" ? t("按送货分组") : item.template_id === "standard-v1" ? t("标准明细") : item.template_name} · ${outputLanguage(item.locale)}`;
const blockers: Record<string, string> = { STATEMENT_RECONFIRMATION_EVIDENCE_REQUIRED: "已收到回签时，须先登记本期客户反馈依据", STATEMENT_RELATED_FEES_REVIEW: "来源相关费用需人工处理，暂不能直接正式更正", STATEMENT_STATE_CONFLICT: "当前状态不能执行此操作", STATEMENT_UNAPPROVED_QUANTITY: "仍有未认可的草稿数量", STATEMENT_FEES_UNKNOWN: "费用尚未确认", STATEMENT_RECONFIRMATION_UNKNOWN: "再次回签要求尚未确认", STATEMENT_ADJUSTMENTS_REVIEW: "费用调整需要重新核对", STATEMENT_AMOUNT_UNCONFIRMED: "最终金额尚未确定", STATEMENT_EMPTY_SETTLEMENT: "没有可结算的明细或转期认可", STATEMENT_NO_PENDING_QUANTITY: "没有可延期的未结数量", STATEMENT_FORMAL_CORRECTION_REQUIRED: "已正式结算，请通过正式更正处理", STATEMENT_REAPPROVAL_REQUIRED: "客户改变认可结果，需要重新取得认可", STATEMENT_DISPOSITION_REQUIRED: "请明确减少量的去向", STATEMENT_EVIDENCE_MISMATCH: "依据不属于对应对账单", STATEMENT_DOWNSTREAM_EFFECTS: "存在后续影响，需人工异常处理" };
const positive = (text: string) => /^\d+(?:\.\d+)?$/.test(text) && /[1-9]/.test(text);
const sourceName = (s: Schemas["StatementSource"]) => `${s.delivery_date} · ${s.item_code ?? ""} ${s.item_name ?? s.description} ${s.specification ?? ""}`;
const idShort = (id: string) => id.slice(-8);
async function allPages<T>(read: (cursor?: string) => Promise<{ items: T[]; next_cursor: string | null }>) {
  const items: T[] = []; let cursor: string | undefined;
  do { const page = await read(cursor); items.push(...page.items); cursor = page.next_cursor ?? undefined; } while (cursor);
  return items;
}
async function fileContent(file: File): Promise<string> {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error("file")); reader.onload = () => resolve(String(reader.result).split(",")[1] ?? ""); reader.readAsDataURL(file); });
}

function CorrectionEvidence({ correction, evidence }: { correction: Schemas["StatementCorrection"] | null | undefined; evidence: Schemas["StatementEvidence"][] }) {
  if (!correction) return null;
  const record = evidence.find(e => e.id === correction.evidence_id);
  return <details><summary>{t("更正差异与依据")}</summary><p>{t("数量{0} → {1}；单价{2} → {3}", [(correction.previous_quantity) ?? "", (correction.quantity) ?? "", (correction.previous_unit_price) ?? "", (correction.unit_price) ?? ""])}</p><p>{t("{0} · 减少量{1} · {2}", [(correction.cause === "entry_error" ? t("系统录入错误") : t("客户后来改变认可")) ?? "", (correction.disposition === "pending" ? t("保留认可待结") : t("转待核对")) ?? "", (correction.reason) ?? ""])}</p><p>{t("依据{0}{1}", [(idShort(correction.evidence_id)) ?? "", (record ? ` · ${record.person} · ${record.occurred_on} · ${record.note}` : t("（对应原对账单反馈）")) ?? ""])}</p>{record?.filename && <a href={`/api/v1/statement-evidence/${record.id}/file`} download>{t("下载更正依据：{0}", [(record.filename) ?? ""])}</a>}<small>{t("操作人{0} · {1} · {2}", [(idShort(correction.actor_id)) ?? "", (new Date(correction.recorded_at).toLocaleString(getLocale())) ?? "", (correction.no_downstream_effects ? t("已确认无后续影响") : t("后续影响按更正规则处理")) ?? ""])}</small></details>;
}
const historyNames: Record<string, string> = { statement_approvals: "认可", statement_allocations: "结算分配", statement_reviews: "待核对", statement_review_transfers: "待核对承接", statement_evidence: "发送/反馈依据", approval: "认可", allocation: "结算分配", review: "待核对", review_transfer: "待核对承接", evidence: "发送/反馈依据", sent: "发送", feedback: "反馈", approve: "认可", reserve: "预留", release: "取消预留", defer: "延期", correct_approval: "更正认可", correct_settlement: "更正正式结算" };
const snapshotFields: Record<string, string> = { external_document_number: "客户外部单号", quantity: "数量", unit_price: "单价", target_start: "结算期间开始", target_end: "结算期间结束", status: "当时状态", reason: "原因", person: "确认人", occurred_on: "实际日期", note: "备注", sent_id: "发送依据", feedback_id: "反馈依据", approval_id: "认可记录", review_id: "待核对事项", statement_id: "对账单", actor_id: "操作人" };

export function StatementLifecycle({ statement, exports, canWrite, disabled, onRefresh, onGuardChange }: {
  statement: Statement; exports: StatementExport[]; canWrite: boolean; disabled: boolean;
  onRefresh: () => Promise<void>; onGuardChange: (blocked: boolean) => void;
}) {
  const [view, setView] = useState<Schemas["StatementLifecycleView"] | null>(null);
  const [approvals, setApprovals] = useState<Schemas["StatementApproval"][]>([]);
  const [reviews, setReviews] = useState<Schemas["StatementReview"][]>([]);
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const [refreshRequired, setRefreshRequired] = useState(false);
  const needsHeadRefresh = useRef(false);
  const loadSequence = useRef(0);
  const [error, setError] = useState<UiMessage>(""), [notice, setNotice] = useState<UiMessage>("");
  const [operation, setOperation] = useState<Operation>(statement.status === "confirmed" ? "feedback" : "sent");
  const [form, setForm] = useState({ person: "", date: new Date().toLocaleDateString("en-CA"), reason: "", exportId: "", sent: "", feedback: "", source: "", approval: "", allocation: "", review: "", quantity: "", price: "", start: statement.period_start, end: statement.period_end, evidence: "", cause: "entry_error" as "entry_error" | "customer_change" | "return", disposition: "review" as "review" | "pending", fees: false, reconfirmation: "unknown" as "unknown" | "not_required" | "received", noDownstream: false });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Schemas["LifecyclePreview"] | null>(null);
  const pending = useRef<{ signature: string; key: string } | null>(null);
  const retry = useRef<(() => Promise<unknown>) | null>(null);
  const inflight = useRef(false);
  const locked = disabled || busy || uncertain || refreshRequired || !canWrite;
  const draft = statement.status === "draft";
  const choices = (Object.keys(names) as Operation[]).filter(op => draft || (statement.status === "confirmed" && op === "sent") || op === "feedback" || op === "defer" || op === "correctApproval" || (statement.status === "confirmed" && op === "correctSettlement"));
  const dLines = statement.lines.filter(line => line.status === "included" && positive(line.quantity));
  const approval = approvals.find(a => a.id === form.approval);
  const allocation = view?.allocations.find(a => a.id === form.allocation);
  const review = reviews.find(r => r.id === form.review);
  const source = dLines.find(line => `${line.delivery_id}/${line.order_line_id}` === form.source);
  function allocationName(item: Schemas["StatementLifecycleView"]["allocations"][number], index: number) {
    const itemSource = approvals.find(a => a.id === item.approval_id)?.source ?? statement.settlement_lines.find(line => line.allocation_id === item.id)?.source;
    return t("{0} · 数量 {1}{2} · 单价 {3}", [itemSource ? sourceName(itemSource) : t("第{0}项结算明细", [index + 1]), item.quantity, itemSource ? ` ${displayUnit(itemSource.canonical_unit ?? itemSource.source_unit)}` : "", item.unit_price]);
  }
  const quantitySource = ["approve", "review"].includes(operation) ? source?.source : operation === "claim" ? review?.source : ["reserve", "correctApproval"].includes(operation) ? approval?.source : statement.settlement_lines.find(line => line.allocation_id === form.allocation)?.source;
  const quantityUnit = quantitySource ? displayUnit(quantitySource.canonical_unit ?? quantitySource.source_unit) : "";
  const needsPreview = ["defer", "correctApproval", "settle", "correctSettlement"].includes(operation);
  const currentExports = exports.filter(item => item.current && item.status === "ready");
  const feedbacks = view?.evidence.filter(e => e.kind === "feedback") ?? [];
  const change = (patch: Partial<typeof form>) => { setForm(old => ({ ...old, ...patch })); setPreview(null); setNotice(""); };
  async function load() {
    const request = ++loadSequence.current;
    const [next, a, r] = await Promise.all([api.statementLifecycle(statement.id), allPages(cursor => api.statementApprovals(statement.customer_id, cursor)), allPages(cursor => api.statementReviews(statement.customer_id, cursor))]);
    if (request !== loadSequence.current) return false;
    setView(next); setApprovals(a.filter(item => item.source.currency === (statement.currency ?? "CNY"))); setReviews(r.filter(item => item.source.currency === (statement.currency ?? "CNY")));
    return true;
  }
  useEffect(() => { setPreview(null); if (statement.status !== "draft") setOperation("feedback"); let active = true; setBusy(true); void load().then(loaded => { if (active && loaded && !needsHeadRefresh.current) setRefreshRequired(false); }).catch(f => { if (active) { setError(message(f)); setRefreshRequired(true); } }).finally(() => { if (active) setBusy(false); }); return () => { active = false; loadSequence.current += 1; }; }, [statement.id, statement.version]);
  useEffect(() => { onGuardChange(busy || uncertain || refreshRequired); return () => onGuardChange(false); }, [busy, uncertain, refreshRequired, onGuardChange]);
  async function execute(action: () => Promise<unknown>, write: boolean) {
    if (inflight.current) return;
    inflight.current = true; setBusy(true); setError(""); setNotice("");
    if (write) retry.current = action;
    try {
      const result = await action();
      if (write) {
        pending.current = null; retry.current = null; setUncertain(false); setPreview(null);
        needsHeadRefresh.current = true; setRefreshRequired(true);
        try {
          await onRefresh();
          if (await load()) { needsHeadRefresh.current = false; setRefreshRequired(false); setNotice(operation === "approve" ? msg("客户认可已记录，尚未计入本期结算。") : operation === "reserve" ? msg("已选入本期结算，尚未正式确认。") : operation === "settle" ? msg("本期正式结算已确认；这不表示已经收款。") : msg("已完成：{0}。", [msg(names[operation])])); }
        } catch { setNotice(msg("操作已登记；刷新未完成，请重新读取后再继续。")); }
      } else setPreview(result as Schemas["LifecyclePreview"]);
    } catch (failure) { setError(message(failure)); if (write) setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { inflight.current = false; setBusy(false); }
  }
  function key(body: unknown) { const signature = JSON.stringify(body); if (pending.current?.signature !== signature) pending.current = { signature, key: crypto.randomUUID() }; return pending.current.key; }
  async function submit(previewOnly = false) {
    if (locked) return;
    const base = { expected_version: statement.version, reason: form.reason };
    const evidence = { person: form.person, occurred_on: form.date, note: form.reason };
    const amount = { quantity: form.quantity, unit_price: form.price };
    const period = { target_start: form.start, target_end: form.end };
    const settlement: Schemas["SettlementPreviewInput"] = { ...base, fees_confirmed: form.fees, reconfirmation: form.reconfirmation };
    const defer = { ...base, expected_version: approval?.version ?? 0, ...period };
    const correctApproval: Schemas["CorrectApprovalPreviewInput"] = { ...base, expected_version: approval?.version ?? 0, ...amount, disposition: "review", evidence_id: form.evidence, cause: form.cause === "customer_change" ? "customer_change" : "entry_error" };
    const correctSettlement: Schemas["CorrectSettlementPreviewInput"] = { ...base, ...amount, allocation_id: form.allocation, disposition: form.disposition, evidence_id: form.evidence, cause: form.cause, no_downstream_effects: form.noDownstream };
    if (previewOnly) {
      const action = operation === "settle" ? () => api.previewStatementSettlement(statement.id, settlement) : operation === "defer" ? () => api.previewStatementDefer(form.approval, defer) : operation === "correctApproval" ? () => api.previewApprovalCorrection(form.approval, correctApproval) : () => api.previewSettlementCorrection(statement.id, correctSettlement);
      await execute(action, false); return;
    }
    const token = preview?.token ?? "";
    const send = <T,>(body: T, call: (body: T, key: string) => Promise<unknown>) => { const commandKey = key({ operation, statement: statement.id, approval: form.approval, body }); return () => call(body, commandKey); };
    let action: () => Promise<unknown>;
    switch (operation) {
      case "sent": action = send({ ...evidence, expected_version: statement.version, export_id: form.exportId }, (b, k) => api.recordStatementSent(statement.id, b, k)); break;
      case "feedback": {
        if (file && (!['application/pdf', 'image/png', 'image/jpeg'].includes(file.type) || file.size > 10 * 1024 * 1024)) { setError(msg("反馈文件仅支持 10 MB 以内的 PNG、JPEG 或 PDF。")); return; }
        // File bytes are frozen in the command closure before any network retry.
        setBusy(true);
        let content: string | undefined;
        try { if (file) content = await fileContent(file); } catch { setError(msg("无法读取反馈文件，请重新选择。")); setBusy(false); return; }
        setBusy(false);
        const body: Schemas["FeedbackInput"] = { ...evidence, ...(file ? { filename: file.name, media_type: file.type as "application/pdf" | "image/png" | "image/jpeg", content_base64: content ?? null } : {}) };
        action = send(body, (b, k) => api.recordStatementFeedback(statement.id, b, k)); break;
      }
      case "approve": if (!source) return; action = send({ ...base, ...amount, ...period, delivery_id: source.delivery_id, order_line_id: source.order_line_id, sent_id: form.sent, feedback_id: form.feedback }, (b, k) => api.approveStatement(statement.id, b, k)); break;
      case "review": if (!source) return; action = send({ ...base, quantity: form.quantity, delivery_id: source.delivery_id, order_line_id: source.order_line_id }, (b, k) => api.reviewStatement(statement.id, b, k)); break;
      case "reserve": if (!approval) return; action = send({ ...base, approval_id: approval.id, approval_version: approval.version, quantity: form.quantity }, (b, k) => api.reserveStatementApproval(statement.id, b, k)); break;
      case "release": if (!allocation) return; action = send({ ...base, allocation_id: allocation.id, allocation_version: allocation.version }, (b, k) => api.releaseStatementAllocation(statement.id, b, k)); break;
      case "claim": if (!review) return; action = send({ ...base, ...amount, review_id: review.id, review_version: review.version }, (b, k) => api.claimStatementReview(statement.id, b, k)); break;
      case "settle": action = send({ ...settlement, preview_token: token }, (b, k) => api.settleStatement(statement.id, b, k)); break;
      case "defer": action = send({ ...defer, preview_token: token }, (b, k) => api.deferStatementApproval(form.approval, b, k)); break;
      case "correctApproval": action = send({ ...correctApproval, preview_token: token }, (b, k) => api.correctStatementApproval(form.approval, b, k)); break;
      case "correctSettlement": action = send({ ...correctSettlement, preview_token: token }, (b, k) => api.correctStatementSettlement(statement.id, b, k)); break;
    }
    await execute(action, true);
  }
  return <section id="statement-lifecycle" className="statement-panel statement-lifecycle" aria-labelledby="statement-lifecycle-heading" tabIndex={-1}>
    <header className="statement-panel-heading"><div><h2 id="statement-lifecycle-heading">{t("客户认可与本期结算")}</h2><p>{t("正式结算不表示收款。")}</p></div></header>
    <CorrectionEvidence correction={statement.correction} evidence={view?.evidence ?? []} />
    {disabled && <p className="warning">{t("请先保存草稿并完成当前操作，再登记发送、认可或结算。")}</p>}
    {error && <p className="error" role="alert">{t(error)}</p>}{notice && <p className="success" role="status">{t(notice)}</p>}
    {uncertain && <p className="warning">{t("操作结果尚未确定，输入已锁定。")}<button disabled={busy} onClick={() => { if (retry.current) void execute(retry.current, true); }}>{t("按原内容重试")}</button></p>}
    {refreshRequired && <p className="warning">{t("最新版本尚未完整读取，暂停登记动作。")}<button type="button" className="secondary" disabled={busy || uncertain} onClick={() => { setBusy(true); setError(""); void onRefresh().then(() => load()).then(loaded => { if (loaded) { needsHeadRefresh.current = false; setRefreshRequired(false); setNotice(msg("最新版本已重新读取。")); } }).catch(f => setError(message(f))).finally(() => setBusy(false)); }}>{t("重新读取最新版本")}</button></p>}
    {busy && <p role="status" className="muted">{t("正在读取或登记…")}</p>}
    {canWrite && <section className="lifecycle-command" aria-labelledby="lifecycle-command-heading"><h3 id="lifecycle-command-heading">{t("选择本次要做的事")}</h3>
      <form onSubmit={event => { event.preventDefault(); void submit(needsPreview && !preview); }}>
        <fieldset disabled={locked}>
          <div className="lifecycle-operation-groups lifecycle-business-steps" role="group" aria-label={t("客户对账步骤")}>{commonOperations.filter(op => choices.includes(op)).map(op => <button key={op} type="button" aria-pressed={operation === op} onClick={() => { setOperation(op); setPreview(null); setError(""); }}><small>{t("第{0} 步", [(commonOperations.indexOf(op) + 1)])}</small>{t(names[op])}</button>)}</div>
          <details className="lifecycle-more-actions" open={otherOperations.includes(operation)}><summary>{t("待核对、延期与更正")}</summary><div className="actions">{otherOperations.filter(op => choices.includes(op)).map(op => <button key={op} type="button" className="secondary" aria-pressed={operation === op} onClick={() => { setOperation(op); setPreview(null); setError(""); }}>{t(names[op])}</button>)}</div></details>
          <h3 className="lifecycle-current-action">{t(names[operation])}</h3>
          {operation === "sent" && <p className="lifecycle-action-note">{t("在你实际发给客户后登记，系统不会替你发送文件。")}</p>}
          {operation === "feedback" && <p className="lifecycle-action-note">{t("上传客户回签，或填写电话确认内容。记录反馈后，再按反馈登记认可数量。")}</p>}
          {operation === "settle" && <p className="lifecycle-action-note">{t("核对费用和再次回签要求，先预览金额与阻断项，再明确确认。")}</p>}
          <div className="statement-filters">
            {(operation === "sent" || operation === "feedback") && <><label>{operation === "sent" ? t("发给谁") : t("客户确认人")}<input required maxLength={500} value={form.person} onChange={e => change({ person: e.target.value })}/></label><label>{t("实际日期")}<input required type="date" value={form.date} onChange={e => change({ date: e.target.value })}/></label></>}
            {operation === "sent" && <label className="lifecycle-wide-field">{t("实际发送的当前 Excel")}<select required value={form.exportId} onChange={e => change({ exportId: e.target.value })}><option value="">{t("选择已生成文件")}</option>{currentExports.map(x => <option key={x.id} value={x.id}>{t("第{0}版 ·{1} · {2}", [(x.statement_version) ?? "", (exportName(x)) ?? "", (new Date(x.created_at).toLocaleString(getLocale())) ?? ""])}</option>)}</select></label>}
            {operation === "feedback" && <label>{t("回签文件（电话确认可留空）")}<input type="file" accept="image/png,image/jpeg,application/pdf" onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); }}/></label>}
            {["approve", "review"].includes(operation) && <label className="lifecycle-wide-field">{t("选择要处理的货物")}<select required value={form.source} onChange={e => { const line = dLines.find(l => `${l.delivery_id}/${l.order_line_id}` === e.target.value); change({ source: e.target.value, quantity: line?.quantity ?? "", price: line?.unit_price ?? "" }); }}><option value="">{t("选择货物")}</option>{dLines.map(l => <option key={`${l.delivery_id}/${l.order_line_id}`} value={`${l.delivery_id}/${l.order_line_id}`}>{t("{0} · 待认可{1} {2}", [(sourceName(l.source)) ?? "", (l.quantity) ?? "", (displayUnit(l.source.canonical_unit ?? l.source.source_unit)) ?? ""])}</option>)}</select></label>}
            {operation === "approve" && <><label>{t("对应发送记录")}<select required value={form.sent} onChange={e => change({ sent: e.target.value })}><option value="">{t("选择发送版本")}</option>{view?.evidence.filter(e => e.kind === "sent").map(e => <option key={e.id} value={e.id}>v{e.statement_version} · {e.occurred_on} · {e.person}</option>)}</select></label><label>{t("对应反馈依据")}<select required value={form.feedback} onChange={e => change({ feedback: e.target.value })}><option value="">{t("选择反馈记录")}</option>{feedbacks.map(e => <option key={e.id} value={e.id}>{e.occurred_on} · {e.person} · {e.note}</option>)}</select></label></>}
            {["reserve", "defer", "correctApproval"].includes(operation) && <label className="lifecycle-wide-field">{t("认可记录")}<select required value={form.approval} onChange={e => { const a = approvals.find(x => x.id === e.target.value); change({ approval: e.target.value, quantity: operation === "correctApproval" ? a?.quantity ?? "" : a?.available_quantity ?? "", price: a?.unit_price ?? "", start: a?.target_start ?? statement.period_start, end: a?.target_end ?? statement.period_end }); }}><option value="">{t("选择认可记录")}</option>{approvals.filter(a => operation === "correctApproval" ? a.statement_id === statement.id : operation !== "reserve" || (positive(a.available_quantity) && a.target_start === statement.period_start && a.target_end === statement.period_end)).map(a => <option key={a.id} value={a.id}>{t("{0} · 可选{1} {2} · 单价{3}", [(sourceName(a.source)) ?? "", (a.available_quantity) ?? "", (displayUnit(a.source.canonical_unit ?? a.source.source_unit)) ?? "", (a.unit_price) ?? ""])}</option>)}</select></label>}
            {operation === "claim" && <label className="lifecycle-wide-field">{t("待核对事项")}<select required value={form.review} onChange={e => { const r = reviews.find(x => x.id === e.target.value); change({ review: e.target.value, quantity: r?.remaining_quantity ?? "", price: "" }); }}><option value="">{t("选择待核对事项")}</option>{reviews.filter(r => positive(r.remaining_quantity)).map(r => <option key={r.id} value={r.id}>{t("{0} · 剩余{1} {2}", [(sourceName(r.source)) ?? "", (r.remaining_quantity) ?? "", (displayUnit(r.source.canonical_unit ?? r.source.source_unit)) ?? ""])}</option>)}</select></label>}
            {["release", "correctSettlement"].includes(operation) && <label className="lifecycle-wide-field">{t("本期结算明细")}<select required value={form.allocation} onChange={e => { const a = view?.allocations.find(x => x.id === e.target.value); change({ allocation: e.target.value, quantity: a?.quantity ?? "", price: a?.unit_price ?? "" }); }}><option value="">{t("选择结算明细")}</option>{view?.allocations.filter(a => a.status === (operation === "release" ? "reserved" : "settled")).map((a, index) => <option key={a.id} value={a.id}>{allocationName(a, index)}</option>)}</select></label>}
            {["approve", "review", "reserve", "claim", "correctApproval", "correctSettlement"].includes(operation) && <label>{operation.startsWith("correct") ? t("更正后数量") : t("本次数量")}{quantityUnit && `（${quantityUnit}）`}<input required inputMode="decimal" maxLength={64} value={form.quantity} onChange={e => change({ quantity: e.target.value })}/></label>}
            {["approve", "claim", "correctApproval", "correctSettlement"].includes(operation) && <label>{t("客户认可单价（{0}）", [statement.currency ?? "CNY"])}<input required inputMode="decimal" maxLength={64} value={form.price} onChange={e => change({ price: e.target.value })}/></label>}
            {["approve", "defer"].includes(operation) && <><label>{operation === "approve" ? t("本次认可计入哪一期：开始日期") : t("改到哪一期：开始日期")}<input required type="date" value={form.start} onChange={e => change({ start: e.target.value })}/></label><label>{t("该期结束日期")}<input required type="date" min={form.start} value={form.end} onChange={e => change({ end: e.target.value })}/></label></>}
            {["correctApproval", "correctSettlement"].includes(operation) && <><label>{t("更正依据")}<select required value={form.evidence} onChange={e => change({ evidence: e.target.value })}><option value="">{t("选择本单反馈证据")}</option>{feedbacks.map(e => <option key={e.id} value={e.id}>{e.person} · {e.occurred_on} · {e.note}</option>)}</select></label><label>{t("更正类型")}<select value={form.cause} onChange={e => change({ cause: e.target.value as typeof form.cause })}><option value="entry_error">{t("系统录入错误")}</option><option value="customer_change">{t("客户后来改变认可")}</option>{operation === "correctSettlement" && <option value="return">{t("后续退货（需人工异常处理）")}</option>}</select></label><label>{t("减少量去向")}<select value={operation === "correctApproval" ? "review" : form.disposition} onChange={e => change({ disposition: e.target.value as typeof form.disposition })}><option value="review">{t("转待核对")}</option>{operation === "correctSettlement" && <option value="pending">{t("保留已认可待结")}</option>}</select></label></>}
            {operation === "settle" && <><label>{t("费用确认")}<select value={form.fees ? "yes" : "unknown"} onChange={e => change({ fees: e.target.value === "yes" })}><option value="unknown">{t("尚未确认")}</option><option value="yes">{t("费用已完整核对（含明确无额外费用）")}</option></select></label><label>{t("再次回签要求")}<select value={form.reconfirmation} onChange={e => change({ reconfirmation: e.target.value as typeof form.reconfirmation })}><option value="unknown">{t("要求未知")}</option><option value="not_required">{t("已确认无需再次回签")}</option><option value="received">{t("要求再次回签且已收到")}</option></select></label></>}
          </div>
          {operation === "correctSettlement" && <label className="lifecycle-check"><input type="checkbox" checked={form.noDownstream} onChange={e => change({ noDownstream: e.target.checked })}/>{t("已人工核对无收款、退货、后续正式结算或其他下游影响")}</label>}
          <label>{t("本次原因 / 确认备注")}<input required maxLength={500} value={form.reason} placeholder={operation === "feedback" ? t("电话确认请写明确认内容和范围") : t("说明本次动作及数量范围")} onChange={e => change({ reason: e.target.value })}/></label>
          {operation === "reserve" && <p className="muted">{t("这里只列出安排在本期、仍有未结数量的客户认可。")}</p>}
          {operation === "claim" && <p className="warning">{t("承接到当前可编辑草稿后，仍需解决疑点并另行记录认可；放弃草稿会恢复事项余量。")}</p>}
          {operation === "review" && <p className="warning">{t("所填数量暂不结算，保留货物、数量和原因，之后可继续核对。")}</p>}
          {preview && <div className="lifecycle-preview" role="status"><h3>{t("请核对预览")}</h3><p>{t(names[operation])} · {form.reason}</p>{["defer", "approve"].includes(operation) && <p>{t("结算期间：{0} 至{1}", [(form.start) ?? "", (form.end) ?? ""])}</p>}{operation.startsWith("correct") && <p>{t("更正后数量{0} · 单价{1} · 减少量{2}", [(form.quantity) ?? "", (form.price) ?? "", (form.disposition === "pending" && operation === "correctSettlement" ? t("保留认可待结") : t("转待核对")) ?? ""])}</p>}<p>{t("受影响结算明细：{0} 项", [(preview.affected_allocations.length) ?? ""])}</p><ul>{preview.affected_allocations.map((a, index) => <li key={a.id}>{allocationName(a, index)} · {operation === "settle" ? t("确认后转为正式结算") : a.status === "reserved" ? t("确认后取消原结算安排") : t("保留原正式结算历史")}<details><summary>{t("查看校验编号")}</summary>{t("结算记录{0} · 对账单{1}", [(idShort(a.id)) ?? "", (idShort(a.statement_id)) ?? ""])}</details></li>)}</ul>{preview.calculation && <dl><dt>{t("货款小计")}</dt><dd>{preview.calculation.priced_subtotal}</dd><dt>{t("税额")}</dt><dd>{preview.calculation.tax_amount ?? t("待确认")}</dd><dt>{t("最终金额（{0}）", [statement.currency ?? "CNY"])}</dt><dd>{preview.calculation.total ?? t("待确认")}</dd></dl>}{preview.blockers.length ? <ul className="error">{preview.blockers.map(b => <li key={b}>{t(blockers[b] ?? b)}</li>)}</ul> : <p>{t("预览已通过，请核对后确认。")}</p>}</div>}
          <div className="actions"><button className={needsPreview && preview ? "danger" : undefined} disabled={!!preview?.blockers.length || (needsPreview && !preview && operation === "correctSettlement" && !form.noDownstream)}>{needsPreview ? preview ? t("确认执行：{0}", [t(names[operation])]) : t("先预览影响与金额") : t(names[operation])}</button>{preview && <button type="button" className="text-button" onClick={() => setPreview(null)}>{t("取消本次预览")}</button>}</div>
        </fieldset>
      </form>
    </section>}
    <div className="lifecycle-records"><h3>{t("查看记录与余量")}</h3>
    <details open={statement.settlement_lines.length > 0}><summary>{t("本期已选认可明细 ·{0} 项", [(statement.settlement_lines.length) ?? ""])}</summary>
      <div className="table-wrap"><table><thead><tr><th>{t("来源")}</th><th>{t("追溯记录")}</th><th>{t("数量")}</th><th>{t("认可单价")}</th><th>{t("状态")}</th></tr></thead><tbody>{statement.settlement_lines.map(line => <tr key={line.allocation_id}><td>{sourceName(line.source)}{line.external_document_number && <small>{t("外部单号：{0}", [(line.external_document_number) ?? ""])}</small>}</td><td><details><summary>{t("查看编号")}</summary>{t("认可{0} / 结算{1}", [(idShort(line.approval_id)) ?? "", (idShort(line.allocation_id)) ?? ""])}</details></td><td>{line.quantity} {displayUnit(line.source.canonical_unit ?? line.source.source_unit)}</td><td>{line.unit_price}</td><td>{line.allocation_status === "reserved" ? t("本期待结算") : t("正式结算")}</td></tr>)}</tbody></table></div>
      {!statement.settlement_lines.length && <p className="muted">{t("尚无认可量选入本期。不同认可价逐项列示。")}</p>}
    </details>
    <details><summary>{t("客户认可待结 · 全部{0} 项", [(approvals.length) ?? ""])}</summary><div className="table-wrap"><table><thead><tr><th>{t("来源 / 认可")}</th><th>{t("安排结算期间")}</th><th>{t("认可数量")}</th><th>{t("可选入结算")}</th><th>{t("待结算 / 已结算")}</th><th>{t("认可价")}</th></tr></thead><tbody>{approvals.map(a => <tr key={a.id}><td>{sourceName(a.source)}{a.external_document_number && <small>{t("外部单号：{0}", [(a.external_document_number) ?? ""])}</small>}<small>{a.reason}</small><details><summary>{t("查看记录编号")}</summary>{idShort(a.id)} · v{a.version}</details><CorrectionEvidence correction={a.correction} evidence={view?.evidence ?? []}/></td><td>{t("{0} 至{1}", [(a.target_start) ?? "", (a.target_end) ?? ""])}</td><td>{a.quantity} {displayUnit(a.source.canonical_unit ?? a.source.source_unit)}</td><td>{a.available_quantity}</td><td>{a.reserved_quantity} / {a.settled_quantity}</td><td>{a.unit_price}</td></tr>)}</tbody></table></div></details>
    <details><summary>{t("客户待核对 · 全部{0} 项", [(reviews.length) ?? ""])}</summary><div className="table-wrap"><table><thead><tr><th>{t("来源 / 事项")}</th><th>{t("原待核对量")}</th><th>{t("剩余待承接")}</th><th>{t("原因")}</th></tr></thead><tbody>{reviews.map(r => <tr key={r.id}><td>{sourceName(r.source)}{r.external_document_number && <small>{t("外部单号：{0}", [(r.external_document_number) ?? ""])}</small>}<details><summary>{t("查看记录编号")}</summary>{idShort(r.id)} · v{r.version}</details></td><td>{r.quantity} {displayUnit(r.source.canonical_unit ?? r.source.source_unit)}</td><td>{r.remaining_quantity}</td><td>{r.reason}</td></tr>)}</tbody></table></div></details>
    <details><summary>{t("发送与反馈证据 ·{0} 项", [(view?.evidence.length ?? 0) ?? ""])}</summary><ul>{view?.evidence.map(e => <li key={e.id}>{e.kind === "sent" ? t("实际发送") : t("客户反馈")} · v{e.statement_version} · {e.person} · {e.occurred_on} · {e.note}<small>{t("依据{0} · 操作人{1}{2}", [(idShort(e.id)) ?? "", (idShort(e.actor_id)) ?? "", (e.export_id ? t(" · 导出 {0}", [idShort(e.export_id)]) : "") ?? ""])}{e.filename ? <> · <a href={`/api/v1/statement-evidence/${e.id}/file`} download>{e.filename}</a></> : ""}</small></li>)}</ul></details>
    <details><summary>{t("分配与待核对承接记录")}</summary><ul>{view?.allocations.map(a => <li key={a.id}>{t("分配{0} · 认可{1} · 数量{2} · 价{3} · {4} · {5}", [(idShort(a.id)) ?? "", (idShort(a.approval_id)) ?? "", (a.quantity) ?? "", (a.unit_price) ?? "", (({ reserved: t("预留"), settled: t("已正式结算"), released: t("已取消"), superseded: t("已被更正版本替代") })[a.status]) ?? "", (a.reason) ?? ""])}</li>)}{view?.review_transfers.map(take => <li key={take.id}>{t("事项{0} · 承接{1} · 数量{2} · {3} · {4}", [(idShort(take.review_id)) ?? "", (idShort(take.id)) ?? "", (take.quantity) ?? "", (({ claimed: t("草稿处理中"), approved: t("已认可"), released: t("已释放回事项") })[take.status]) ?? "", (take.reason) ?? ""])}</li>)}</ul></details>
    <details><summary>{t("操作历史 ·{0} 项", [(view?.history.length ?? 0) ?? ""])}</summary><ol>{view?.history.map((h, i) => <li key={`${h.entity_id}/${h.version}/${i}`}>{t(historyNames[h.kind] ?? h.kind)} · {idShort(h.entity_id)} · v{h.version} · {new Date(h.created_at).toLocaleString(getLocale())}<details><summary>{t("查看当时记录（只读）")}</summary><dl>{Object.entries(snapshotFields).filter(([key]) => h.snapshot[key] !== undefined && h.snapshot[key] !== null).map(([key, label]) => <div key={key}><dt>{t(label)}</dt><dd>{String(h.snapshot[key])}</dd></div>)}</dl>{h.snapshot.correction && typeof h.snapshot.correction === "object" ? <CorrectionEvidence correction={h.snapshot.correction as Schemas["StatementCorrection"]} evidence={view.evidence}/> : null}</details></li>)}</ol></details>
    </div>
  </section>;
}
