import { getLocale, msg, t, type UiMessage } from "../i18n";
import { materialFromOrderLine, OrderMaterialLink } from "./MaterialSelect";
import { ItemIdentity } from "./ItemIdentity";
import { deliveredShare, displayUnit } from "../units";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Evidence, type OrderDetail as Detail, type Extraction, type Schemas } from "../api";
import { SourceReview } from "./SourceReview";

export function OrderDetail({ id, canWrite, onBack, onEdit, onDeliver, onGuardChange }: { id: string; canWrite: boolean; onBack: () => void; onEdit: (order: Detail) => void; onDeliver: (order: Detail) => void; onGuardChange: (guarded: boolean) => void }) {
  const [order, setOrder] = useState<Detail | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [source, setSource] = useState<Extraction | null>(null);
  const [action, setAction] = useState<"active" | "deleted" | null>(null);
  const [collect, setCollect] = useState<{ line: Detail["lines"][number]; mode: "existing" | "new"; error?: UiMessage; remember?: boolean } | null>(null);
  const [rememberCodes, setRememberCodes] = useState(true);
  const [organize, setOrganize] = useState(false);
  const [quickLine, setQuickLine] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<{ key: string; reason: string; target: "active" | "deleted"; version: number } | null>(null);
  const pendingMaterial = useRef<{ key: string; body: Schemas["OrderMaterialLinksInput"] } | null>(null);
  useEffect(() => { onGuardChange(busy || uncertain || !!action || !!collect); return () => onGuardChange(false); }, [busy, uncertain, action, collect, onGuardChange]);

  useEffect(() => { const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); }; if (collect || busy || uncertain) window.addEventListener("beforeunload", prevent); return () => window.removeEventListener("beforeunload", prevent); }, [collect, busy, uncertain]);

  async function load() { setBusy(true); setError(""); try { setOrder(await api.detail(id)); } catch (failure) { setError(message(failure)); } finally { setBusy(false); } }
  useEffect(() => { let active = true; api.detail(id).then(data => { if (active) setOrder(data); }).catch(failure => { if (active) setError(message(failure)); }); return () => { active = false; }; }, [id]);

  async function collectNew(line: Detail["lines"][number]) {
    if (!order || busy || uncertain && quickLine !== line.id) return;
    const remember = !!line.item_code?.trim() && rememberCodes;
    if (!pendingMaterial.current) {
      const draft = materialFromOrderLine(line);
      setError(""); setNotice("");
      if (!line.item_name?.trim() || draft.name.length > 500 || (draft.specification?.length ?? 0) > 1000 || (draft.unit?.length ?? 0) > 40) {
        setCollect({ line, mode: "new", remember, error: msg("这行资料还不能直接建档，请核对物料名称、规格和单位。") }); return;
      }
      pendingMaterial.current = { key: crypto.randomUUID(), body: { expected_version: order.version, lines: [{ line_id: line.id, new_material: draft, remember_code: remember, customer_code: remember ? line.item_code!.trim() : null, expected_mapping_version: 0 }] } };
    }
    setQuickLine(line.id); setBusy(true); setError("");
    try {
      await api.linkOrderMaterials(order.id, pendingMaterial.current.body, pendingMaterial.current.key);
      pendingMaterial.current = null; setUncertain(false); setQuickLine(null);
      setNotice(msg("已收录为新物料，我方料号已自动生成。"));
      try { setOrder(await api.detail(id)); }
      catch (failure) { setOrder(null); setError(msg("收录已完成，详情暂未更新。{0}", [message(failure)])); }
    } catch (failure) {
      const unknown = !(failure instanceof ApiError) || failure.status >= 500;
      setUncertain(unknown);
      if (unknown) setError(message(failure));
      else {
        pendingMaterial.current = null; setQuickLine(null);
        if (failure.code === "MATERIAL_MAPPING_CONFLICT" || failure.code === "MATERIAL_NUMBER_BUSY" || failure.status === 422) {
          setCollect({ line, mode: "new", remember, error: failure.code === "MATERIAL_MAPPING_CONFLICT" ? msg("这个客户料号已有对应，尚未新建。可改选已有物料，或核对后更正对应。") : message(failure) });
        } else setError(message(failure));
      }
    } finally { setBusy(false); }
  }

  async function changeStatus(event: FormEvent) {
    event.preventDefault(); if (!order || !action || busy) return;
    if (!pending.current || !uncertain) pending.current = { key: crypto.randomUUID(), reason, target: action, version: order.version };
    setBusy(true); setError("");
    try {
      const command = pending.current;
      await api.changeStatus(order.id, command.target, command.version, command.reason, command.key);
      setUncertain(false); setAction(null); setReason(""); pending.current = null;
      setNotice(command.target === "deleted" ? msg("订单已删除，确认凭证仍保留，可随时恢复。") : msg("订单已恢复。未交数量已重新列入明细。"));
      try { setOrder(await api.detail(id)); }
      catch (failure) { setOrder(null); setError(msg("操作已完成，详情暂未更新。{0}", [message(failure)])); }
    } catch (failure) { setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }

  async function viewEvidence(revision: string) { setBusy(true); setError(""); setSource(null); try { const result = await api.evidence(revision); setEvidence(result); if (result.content.source) setSource(await api.extraction(result.content.source.extraction_id)); } catch (failure) { setError(message(failure)); } finally { setBusy(false); } }

  return <section className="work-page order-detail-page">
    <button className="back-button" onClick={onBack} disabled={busy || uncertain || !!collect}>{t("返回订单")}</button>
    {error && <div className="error" role="alert">{t(error)}{!uncertain && <button className="text-button" disabled={busy} onClick={() => void load()}>{t("刷新订单")}</button>}</div>}
    {notice && <p className="success" role="status">{t(notice)}</p>}
    {uncertain && quickLine && <p className="warning" role="status">{t("收录结果待确认，请保留此页，点击该行“重试本次收录”。")}</p>}
    {!order ? <p role="status" className="muted">{error ? t("未能读取订单。") : t("正在读取订单…")}</p> : <>
      <div className="page-heading"><div><h1>{order.order_number}</h1><p>{order.customer_name} · {order.business_date}</p></div><span className={`state-label ${order.status}`}>{order.status === "active" ? t("有效订单") : t("已删除")}</span></div>
      <div className="detail-toolbar work-action-bar"><span className="muted">{t("当前版本{0} · {1}", [order.version, order.currency === "USD" ? t("USD 美元") : t("CNY 人民币")])}</span>{canWrite && <div className="actions">{order.status === "active" && order.lines.some(line => line.remaining_quantity !== "0") && <button onClick={() => onDeliver(order)} disabled={busy || uncertain || !!action || !!collect}>{t("登记送货")}</button>}{order.status === "active" && <button className="secondary" onClick={() => onEdit(order)} disabled={busy || uncertain || !!action || !!collect}>{t("修订订单")}</button>}<button className={order.status === "active" ? "text-button danger-text" : "secondary"} disabled={busy || uncertain || !!action || !!collect} onClick={() => { setAction(order.status === "active" ? "deleted" : "active"); setNotice(""); }}>{order.status === "active" ? t("删除订单") : t("恢复订单")}</button></div>}</div>
      {collect && <OrderMaterialLink key={collect.line.id} order={order} line={collect.line} initialMode={collect.mode} initialError={collect.error ?? ""} initialRemember={collect.remember ?? !!collect.line.item_code} onClose={() => setCollect(null)} onSaved={() => { setCollect(null); setNotice(msg("物料关联已保存，原单内容和交付数量保持原样。")); void load(); }} />}
      {action && <form onSubmit={changeStatus} className="status-form"><h2>{action === "deleted" ? t("删除订单") : t("恢复订单")}</h2><p>{action === "deleted" ? t("删除后不再计入未交明细，原确认凭证保留。") : t("恢复原订单及明细，不创建重复订单。")}</p><label>{t("操作原因")}<textarea autoFocus required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} disabled={busy || uncertain} /></label>{uncertain && <p role="status" className="warning">{t("结果待确认，请重试同一次操作。")}</p>}<div className="actions"><button disabled={busy || !reason.trim()}>{busy ? t("处理中…") : uncertain ? t("重试本次操作") : action === "deleted" ? t("确认删除") : t("确认恢复")}</button><button type="button" className="secondary" disabled={busy || uncertain} onClick={() => { setAction(null); setReason(""); }}>{t("取消")}</button></div></form>}
      <section className="detail-section work-panel"><h2>{t("订单明细")}</h2>{(() => { const linked = order.lines.filter(line => line.material_id).length, total = order.lines.length, open = total - linked, editable = canWrite && order.status === "active"; return <div className={`material-summary${open ? "" : " is-complete"}`} role="group" aria-label={t("物料池")}>
        <div><strong>{open ? t("{0} / {1} 行已对上物料池", [linked, total]) : t("{0} 行都已对上物料池", [total])}</strong><span>{t("记住客户料号后，下次料号和内容匹配的订单可自动带出物料。")}</span></div>
        {editable && <div className="material-summary-actions">{organize && order.lines.some(line => !line.material_id && line.item_code?.trim()) && <label className="checkbox"><input type="checkbox" checked={rememberCodes} disabled={busy || uncertain || !!action || !!collect} onChange={e => setRememberCodes(e.target.checked)} />{t("收录时同时记住{0}的料号", [order.customer_name])}</label>}<button type="button" className="secondary" aria-expanded={organize} disabled={busy || uncertain || !!action || !!collect} onClick={() => setOrganize(value => !value)}>{organize ? t("收起") : open ? t("整理物料") : t("维护物料关联")}</button></div>}
      </div>; })()}<div className="table-wrap"><table><thead><tr><th>{t("货物信息")}</th><th className="numeric">{t("订单单价")}</th><th className="numeric">{t("订单数量")}</th><th className="numeric">{t("已交")}</th><th className="numeric">{t("未交")}</th><th>{t("单位")}</th></tr></thead><tbody>{order.lines.map(line => <tr key={line.id}><td><ItemIdentity line={line} />{line.material && <small className="material-binding material-chip">{t("已收录，我方料号 {0}", [(line.material.own_code) ?? ""])}{!line.material.active && t("（已停用）")}</small>}{canWrite && order.status === "active" && (organize || quickLine === line.id) && <div className="material-row-actions">
        {!line.material_id && <button type="button" className="secondary" disabled={busy || uncertain && quickLine !== line.id || !!action || !!collect} onClick={() => void collectNew(line)}>{quickLine === line.id ? uncertain ? t("重试本次收录") : t("收录中…") : t("收录为新物料")}</button>}
        <button type="button" className="text-button" disabled={busy || uncertain || !!action || !!collect} onClick={() => { setCollect({ line, mode: "existing", remember: !!line.item_code?.trim() && rememberCodes }); setNotice(""); setError(""); }}>{line.material_id ? t("维护物料关联") : t("关联已有")}</button>
      </div>}{line.quantity_policy.warning_codes.length > 0 && <small className="warning-text">{t("单位待核对")}</small>}</td><td className="numeric">{line.source_unit_price ?? "—"}</td><td className="numeric">{line.quantity}</td><td className="numeric">{line.delivered_quantity}{(() => { const share = deliveredShare(line.delivered_quantity, line.quantity); return share === null ? null : <span className="delivery-progress" aria-hidden="true"><span style={{ width: `${share}%` }} /></span>; })()}</td><td className="numeric remaining">{line.remaining_quantity}</td><td>{displayUnit(line.source_unit)}</td></tr>)}</tbody></table></div></section>
      <section className="detail-section work-panel"><h2>{t("确认凭证")}</h2><p className="muted">{t("每次修订都保存独立版本。下载文件可留底核对。")}</p><ul className="revision-list">{order.revisions.map(revision => <li key={revision.revision_id}><div><strong>{t("确认版本{0}", [(revision.revision_number) ?? ""])}</strong><small>{new Date(revision.confirmed_at).toLocaleString(getLocale(), { hour12: false })}</small></div><div className="actions"><button className="text-button" disabled={busy || uncertain || !!collect} onClick={() => void viewEvidence(revision.revision_id)}>{t("查看确认内容")}</button><a href={`/api/v1/documents/${revision.revision_id}/download`}>{t("下载凭证")}</a></div></li>)}</ul></section>
      {evidence && <section className="evidence-panel work-panel"><div className="row-between"><h2>{t("确认版本{0}", [(evidence.content.revision_number) ?? ""])}</h2><button className="text-button" onClick={() => setEvidence(null)}>{t("收起")}</button></div><p>{evidence.content.order.order_number} · {evidence.content.order.business_date}</p><ul className="evidence-lines">{evidence.content.order.lines.map(line => <li key={line.line_number}><ItemIdentity line={line} /><span>{t("提交数量{0} {1} · 记录数量{2}", [(line.source_quantity_text) ?? "", (line.source_unit || t("（空单位）")) ?? "", (line.canonical_quantity) ?? ""])}</span><span>{t("订单单价{0} · 原单金额{1}", [(line.source_unit_price ?? t("未提供")) ?? "", (line.source_amount ?? t("未提供")) ?? ""])}</span></li>)}</ul><details><summary>{t("文件校验信息")}</summary><p className="hash">SHA-256：{evidence.sha256}</p></details></section>}
      {evidence && source && <SourceReview extraction={source} />}
    </>}
  </section>;
}
