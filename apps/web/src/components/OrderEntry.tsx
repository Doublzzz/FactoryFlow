import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, message, type Customer, type OrderDetail, type OrderInput, type OrderPreview, type Material } from "../api";
import { NewCustomer } from "./Customers";
import type { Extraction } from "../api";
import { SourceReview } from "./SourceReview";
import { MaterialSelect } from "./MaterialSelect";

const emptyLine = () => ({ chosen: null as Material | null, description: "", item_code: "", item_name: "", specification: "", quantity: "", unit: "", source_unit_price: null as string | null, source_amount: null as string | null });
function today() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }

export function OrderEntry({ customers, existing, extraction, onCustomer, onCancel, onSaved }: {
  customers: Customer[]; existing?: OrderDetail | undefined; extraction?: Extraction | undefined; onCustomer: (customer: Customer) => void; onCancel: () => void; onSaved: (id: string) => void;
}) {
  const [customer, setCustomer] = useState(existing?.customer_id ?? "");
  const [number, setNumber] = useState(existing?.order_number ?? extraction?.candidate.order_number ?? "");
  const [date, setDate] = useState(existing?.business_date ?? (extraction ? extraction.candidate.business_date ?? "" : today()));
  const [currency, setCurrency] = useState(existing?.currency ?? (extraction ? extraction.candidate.currency ?? "" : "CNY"));
  const [lines, setLines] = useState(() => existing?.lines.map(line => ({ description: line.description, item_code: line.item_code ?? "", item_name: line.item_name ?? (line.item_code != null || line.specification != null ? "" : line.description), specification: line.specification ?? "", quantity: line.source_quantity_text, unit: line.source_unit ?? "", source_unit_price: line.source_unit_price, source_amount: line.source_amount, chosen: line.material ?? null as Material | null })) ?? (extraction?.candidate.lines.length ? extraction.candidate.lines.map(line => ({ ...line, chosen: null as Material | null, item_code: line.item_code ?? "", item_name: line.item_name ?? (line.item_code != null || line.specification != null ? "" : line.description), specification: line.specification ?? "", unit: line.unit ?? "" })) : [emptyLine()]));
  const [choosingLine, setChoosingLine] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [newCustomer, setNewCustomer] = useState(false);
  const [review, setReview] = useState<{ preview: OrderPreview; input: OrderInput; key: string; signature: string } | null>(null);
  const [ignoredMaterials, setIgnoredMaterials] = useState<number[]>([]);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState<UiMessage>("");
  const [validationRetry, setValidationRetry] = useState(0);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  useEffect(() => { window.scrollTo(0, 0); }, []);
  useEffect(() => { const prevent = (e: BeforeUnloadEvent) => { e.preventDefault(); }; window.addEventListener("beforeunload", prevent); return () => window.removeEventListener("beforeunload", prevent); }, []);
  const locked = busy || uncertain;
  const input: OrderInput = { customer_id: customer, order_number: number, business_date: date, currency: currency as "CNY" | "USD", material_choices: lines.flatMap((line, index) => line.chosen ? [{ line_number: index + 1, material_id: line.chosen.id, expected_material_version: line.chosen.version }] : []), lines: lines.map(({ chosen: _chosen, ...line }) => ({ ...line, description: [line.item_code, line.item_name, line.specification].filter(Boolean).join(" ") })), ...(extraction ? { extraction_id: extraction.extraction_id } : {}) };
  const signature = JSON.stringify({ input, ignoredMaterials });
  const currentReview = review?.signature === signature ? review : null;
  // Read-only validation stays on the editable page. Only the Save button writes.
  useEffect(() => {
    if (locked) return;
    setReview(null); setValidationError("");
    const snapshot = JSON.parse(signature) as { input: OrderInput; ignoredMaterials: number[] };
    const draft = snapshot.input;
    if (!draft.customer_id || !draft.order_number.trim() || !draft.business_date || !["CNY", "USD"].includes(draft.currency) || draft.lines.some(line => !line.quantity || !line.description.trim())) { setValidating(false); return; }
    let active = true; setValidating(true);
    const timer = window.setTimeout(() => {
      void api.preview(draft).then(result => {
        if (!active) return;
        const selected = draft.material_choices ?? [];
        const automatic = (result.material_suggestions ?? []).filter(suggestion => suggestion.automatic && !snapshot.ignoredMaterials.includes(suggestion.line_number) && !selected.some(choice => choice.line_number === suggestion.line_number)).map(suggestion => ({ line_number: suggestion.line_number, material_id: suggestion.material.id, expected_material_version: suggestion.material.version, mapping: suggestion.mapping }));
        setReview({ preview: result, input: { ...draft, material_choices: [...selected, ...automatic] }, key: crypto.randomUUID(), signature });
      }).catch(failure => { if (active) setValidationError(message(failure)); }).finally(() => { if (active) setValidating(false); });
    }, 300);
    return () => { active = false; window.clearTimeout(timer); };
  }, [signature, locked, validationRetry]);

  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (busy || !uncertain && validating) return;
    const command = uncertain ? review : currentReview;
    if (!command) { setValidationError(previous => previous || msg("请补齐客户、订单号、日期、币种和明细后保存。")); return; }
    setBusy(true); setError("");
    try {
      const result = existing ? await api.revise(existing.id, command.input, existing.version, reason, command.key) : await api.confirm(command.input, command.key);
      setUncertain(false); onSaved(result.order_id);
    } catch (failure) {
      setError(message(failure)); setUncertain(previous => previous || !(failure instanceof ApiError) || failure.status >= 500 || failure.status === 401);
    } finally { setBusy(false); }
  }

  function changeLine(index: number, field: string, value: string) {
    setIgnoredMaterials(previous => previous.filter(number => number !== index + 1));
    setLines(previous => previous.map((line, i) => i === index ? { ...line, ...(["item_code", "item_name", "specification", "unit"].includes(field) ? { chosen: null } : {}), [field]: ["source_unit_price", "source_amount"].includes(field) && value === "" ? null : value } : line));
  }

  function selectedMaterial(number: number) {
    if (!currentReview?.input.material_choices?.some(choice => choice.line_number === number)) return null;
    return lines[number - 1]?.chosen ?? currentReview.preview.material_suggestions?.find(suggestion => suggestion.line_number === number)?.material;
  }
  function chooseMaterial(index: number, material: Material) {
    setIgnoredMaterials(previous => previous.filter(number => number !== index + 1));
    setLines(previous => previous.map((line, i) => i === index ? { ...line, chosen: material, item_name: line.item_name || material.name, specification: line.specification || material.specification || "", unit: line.unit || material.unit || "" } : line));
    setChoosingLine(null);
  }
  function cancel() { if (window.confirm(t("离开后，本次未提交的录入会丢失。确定返回吗？"))) onCancel(); }

  return <section className="work-page order-entry-page">
    <button className="back-button" onClick={cancel} disabled={busy || uncertain}>{t("返回订单")}</button>
    <div className="page-heading"><div><h1>{existing ? t("修订订单") : extraction ? t("核对并保存订单") : t("录入订单")}</h1><p>{existing ? t("修订生成新确认版本，原凭证保留。") : t("对照原件修改内容，确认后直接保存。")}</p></div></div>
    {error && <p role="alert" className="error">{t(error)}</p>}
    {validationError && <div role="alert" className="error">{t(validationError)} <button type="button" className="text-button" disabled={locked || validating} onClick={() => setValidationRetry(value => value + 1)}>{t("重试校验")}</button></div>}
    <div className={extraction ? "source-entry-layout" : undefined}>{extraction && <SourceReview extraction={extraction} />}<div>
    {newCustomer ? <section className="inline-customer work-panel"><h2>{t("新建客户")}</h2><NewCustomer onCreated={c => { onCustomer(c); setCustomer(c.id); setNewCustomer(false); }} onCancel={() => setNewCustomer(false)} /></section> : <form onSubmit={confirm}>
      <section className="form-section work-panel"><h2>{t("订单信息")}</h2><div className="form-grid">
        <div className="customer-field"><label htmlFor="order-customer">{t("客户")}</label><select id="order-customer" value={customer} onChange={e => setCustomer(e.target.value)} required disabled={!!existing || locked}><option value="">{t("请选择客户")}</option>{customers.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select>{!existing && <button type="button" className="text-button" onClick={() => setNewCustomer(!newCustomer)} disabled={locked}>{t("新建客户")}</button>}</div>
        <div><label>{t("客户订单号")}<input value={number} onChange={e => setNumber(e.target.value)} maxLength={100} required disabled={!!existing || locked} placeholder={t("按客户订单填写")} aria-describedby={extraction && !extraction.candidate.order_number ? "missing-order-number" : undefined} /></label>{extraction && !extraction.candidate.order_number && <small id="missing-order-number" className="warning-text">{t("未可靠提取，请对照原件填写。")}</small>}</div>
        <div><label>{t("订单日期")}<input type="date" value={date} onChange={e => setDate(e.target.value)} required disabled={locked} aria-describedby={extraction && !extraction.candidate.business_date ? "missing-order-date" : undefined} /></label>{extraction && !extraction.candidate.business_date && <small id="missing-order-date" className="warning-text">{t("未可靠提取，请对照原件填写。")}</small>}</div>
        <div className="select-field"><label htmlFor="order-currency">{t("币种")}</label><select id="order-currency" value={currency} onChange={e => setCurrency(e.target.value)} required disabled={locked || !!existing}><option value="">{t("请选择币种")}</option><option value="CNY">{t("CNY 人民币")}</option><option value="USD">{t("USD 美元")}</option></select></div>
      </div></section>
      <section className="form-section work-panel"><div className="row-between work-panel-heading"><h2>{t("订单明细")}</h2><span className="muted">{t("{0} 行", [(lines.length) ?? ""])}</span></div><p className="muted">{t("请分别核对货物编号、名称和规格。数量最多三位小数，单价、金额未知时留空。")}</p>
        <div className="entry-lines">{lines.map((line, index) => <fieldset className="entry-line" key={index}><legend>{t("第{0} 行", [(index + 1)])}</legend>
          <div className="entry-material"><button type="button" className="text-button" onClick={() => setChoosingLine(choosingLine === index ? null : index)} disabled={locked}>{t("从物料池选择")}</button>{line.chosen && <span>{t("我方料号：{0}", [(line.chosen.own_code) ?? ""])}<button type="button" className="text-button" onClick={() => setLines(previous => previous.map((value, i) => i === index ? { ...value, chosen: null } : value))} disabled={locked}>{t("取消关联")}</button></span>}{choosingLine === index && <MaterialSelect initialQuery={line.item_name} disabled={locked} onSelect={material => chooseMaterial(index, material)} />}</div>
          {!line.chosen && selectedMaterial(index + 1) && <p className="material-binding">{t("按已记住的客户料号关联：{0}", [selectedMaterial(index + 1)!.own_code])}<button type="button" className="text-button" disabled={locked} onClick={() => setIgnoredMaterials(previous => [...previous, index + 1])}>{t("本行暂不关联")}</button></p>}
          <label className="item-code-field">{t("货物编号")}<input value={line.item_code} onChange={e => changeLine(index, "item_code", e.target.value)} maxLength={100} disabled={locked} placeholder={t("原件未提供则留空")} /></label>
          <label className="item-name-field">{t("货物名称")}<textarea aria-label={t("货物名称")} value={line.item_name} onChange={e => changeLine(index, "item_name", e.target.value)} maxLength={500} disabled={locked} rows={2} /></label>
          <label className="specification-field">{t("规格型号")}<textarea aria-label={t("规格型号")} value={line.specification} onChange={e => changeLine(index, "specification", e.target.value)} maxLength={1000} disabled={locked} rows={3} placeholder={t("按原件填写，可保留换行")} /></label>
          <label>{t("数量")}<input inputMode="decimal" value={line.quantity} onChange={e => changeLine(index, "quantity", e.target.value)} required maxLength={64} disabled={locked} /></label>
          <label>{t("单位")}<input value={line.unit} onChange={e => changeLine(index, "unit", e.target.value)} maxLength={40} placeholder={t("如 件、千克、米")} disabled={locked} /></label>
          <label>{t("订单单价")}<input inputMode="decimal" value={line.source_unit_price ?? ""} onChange={e => changeLine(index, "source_unit_price", e.target.value)} maxLength={64} placeholder={t("不知道可留空")} disabled={locked} /></label>
          <label>{t("原单金额")}<input inputMode="decimal" value={line.source_amount ?? ""} onChange={e => changeLine(index, "source_amount", e.target.value)} maxLength={64} placeholder={t("按原单填写，可留空")} disabled={locked} /></label>
          {currentReview?.preview.order.lines[index] && <div className="entry-line-validation">
            {currentReview.preview.order.lines[index]!.source_quantity_text !== currentReview.preview.order.lines[index]!.canonical_quantity && <small>{t("记录为{0}", [currentReview.preview.order.lines[index]!.canonical_quantity])}</small>}
            {currentReview.preview.order.lines[index]!.quantity_policy.warning_codes.length > 0 && <p className="warning">{t("此单位尚无精度规则，请在保存前核实数量和单位；该提示会保留在凭证中。")}</p>}
          </div>}
          <button className="text-button danger-text" type="button" aria-label={t("删除第 {0} 行", [index + 1])} disabled={lines.length === 1 || locked} onClick={() => { setChoosingLine(null); setIgnoredMaterials([]); setLines(previous => previous.filter((_, i) => i !== index)); }}>{t("移除行")}</button>
        </fieldset>)}</div>
        <button type="button" className="secondary" onClick={() => setLines(previous => [...previous, emptyLine()])} disabled={locked || lines.length >= 200}>{t("添加明细")}</button>
      </section>
      {existing && <label className="reason-field">{t("修订原因")}<textarea value={reason} onChange={e => setReason(e.target.value)} required maxLength={500} disabled={locked} /></label>}
      {currentReview?.preview.material_suggestions?.some(suggestion => !suggestion.automatic && !currentReview.input.material_choices?.some(choice => choice.line_number === suggestion.line_number)) && <p className="warning">{t("部分客户料号对应的内容有变化，本次未自动关联。可从物料池选择，或直接保存订单。")}</p>}
      {uncertain && <p className="warning" role="status">{t("提交结果待确认。请重试本次提交；同一次请求不会重复生成订单。确认结果前请保留此页面。")}</p>}
      <div className="form-submit work-action-bar"><p className="muted" role="status">{validating ? t("正在校验数量、单位和物料对应…") : t("保存即确认本页内容，并保留确认凭证。")}</p><button disabled={busy || !uncertain && validating || newCustomer}>{busy ? t("正在确认…") : uncertain ? t("重试本次提交") : existing ? t("确认修订") : t("确认保存订单")}</button></div>
    </form>}
    </div></div>
  </section>;
}
