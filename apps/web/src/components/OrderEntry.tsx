import { t, type UiMessage } from "../i18n";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, message, type Customer, type OrderDetail, type OrderInput, type OrderPreview, type Material } from "../api";
import { NewCustomer } from "./Customers";
import type { Extraction } from "../api";
import { SourceReview } from "./SourceReview";
import { MaterialSelect } from "./MaterialSelect";
import { ItemIdentity } from "./ItemIdentity";
import { displayUnit } from "../units";

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
  const [review, setReview] = useState<{ preview: OrderPreview; input: OrderInput; key: string } | null>(null);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  useEffect(() => { const prevent = (e: BeforeUnloadEvent) => { e.preventDefault(); }; window.addEventListener("beforeunload", prevent); return () => window.removeEventListener("beforeunload", prevent); }, []);
  useEffect(() => { window.scrollTo(0, 0); }, [review]);

  async function preview(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError("");
    const input: OrderInput = { customer_id: customer, order_number: number, business_date: date, currency: "CNY", material_choices: lines.flatMap((line, index) => line.chosen ? [{ line_number: index + 1, material_id: line.chosen.id, expected_material_version: line.chosen.version }] : []), lines: lines.map(({ chosen: _chosen, ...line }) => ({ ...line, description: [line.item_code, line.item_name, line.specification].filter(Boolean).join(" ") })), ...(extraction ? { extraction_id: extraction.extraction_id } : {}) };
    try {
      const result = await api.preview(input);
      const selected = input.material_choices ?? [];
      const automatic = (result.material_suggestions ?? []).filter(suggestion => suggestion.automatic && !selected.some(choice => choice.line_number === suggestion.line_number)).map(suggestion => ({ line_number: suggestion.line_number, material_id: suggestion.material.id, expected_material_version: suggestion.material.version, mapping: suggestion.mapping }));
      setReview({ preview: result, input: { ...input, material_choices: [...selected, ...automatic] }, key: crypto.randomUUID() }); setChecked(false);
    }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (!review || busy || !checked) return;
    setBusy(true); setError("");
    try {
      const result = existing ? await api.revise(existing.id, review.input, existing.version, reason, review.key) : await api.confirm(review.input, review.key);
      setUncertain(false); onSaved(result.order_id);
    } catch (failure) {
      setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500);
    } finally { setBusy(false); }
  }

  function changeLine(index: number, field: string, value: string) {
    setLines(previous => previous.map((line, i) => i === index ? { ...line, ...(["item_code", "item_name", "specification", "unit"].includes(field) ? { chosen: null } : {}), [field]: ["source_unit_price", "source_amount"].includes(field) && value === "" ? null : value } : line));
  }

  function selectedMaterial(number: number) {
    if (!review?.input.material_choices?.some(choice => choice.line_number === number)) return null;
    return lines[number - 1]?.chosen ?? review.preview.material_suggestions?.find(suggestion => suggestion.line_number === number)?.material;
  }
  function chooseMaterial(index: number, material: Material) {
    setLines(previous => previous.map((line, i) => i === index ? { ...line, chosen: material, item_name: line.item_name || material.name, specification: line.specification || material.specification || "", unit: line.unit || material.unit || "" } : line));
    setChoosingLine(null);
  }
  function cancel() { if (window.confirm(t("离开后，本次未提交的录入会丢失。确定返回吗？"))) onCancel(); }

  return <section className="work-page order-entry-page">
    <button className="back-button" onClick={cancel} disabled={busy || uncertain}>{t("返回订单")}</button>
    <div className="page-heading"><div><h1>{review ? t("核对订单") : existing ? t("修订订单") : t("录入订单")}</h1><p>{existing ? t("修订生成新确认版本，原凭证保留。") : t("先录入客户和明细，核对后再生成订单。")}</p></div><span className="step-label">{review ? t("2 / 2 核对确认") : t("1 / 2 录入内容")}</span></div>
    {error && <p role="alert" className="error">{t(error)}</p>}
    <div className={extraction ? "source-entry-layout" : undefined}>{extraction && <SourceReview extraction={extraction} />}<div>
    {review ? <section className="review-panel work-panel"><h2>{t("核对结果")}</h2>
      <dl className="order-facts"><div><dt>{t("客户")}</dt><dd>{review.preview.customer_name}</dd></div><div><dt>{t("客户订单号")}</dt><dd>{review.preview.order.order_number}</dd></div><div><dt>{t("订单日期")}</dt><dd>{review.preview.order.business_date}</dd></div><div><dt>{t("币种")}</dt><dd>{t("CNY 人民币")}</dd></div></dl>
      <div className="table-wrap"><table><thead><tr><th>{t("货物信息")}</th><th className="numeric">{t("订单数量 / 单位")}</th><th className="numeric">{t("订单单价")}</th><th className="numeric">{t("原单金额")}</th></tr></thead><tbody>{review.preview.order.lines.map(line => <tr key={line.line_number}><td><ItemIdentity line={line} />{selectedMaterial(line.line_number) && <small className="material-binding">{t("我方料号：{0}", [(selectedMaterial(line.line_number)?.own_code) ?? ""])}<button type="button" className="text-button" disabled={busy || uncertain} onClick={() => setReview(previous => previous ? { ...previous, input: { ...previous.input, material_choices: previous.input.material_choices?.filter(choice => choice.line_number !== line.line_number) ?? [] }, key: crypto.randomUUID() } : null)}>{t("本行暂不关联")}</button></small>}</td><td className="numeric">{line.source_quantity_text} {displayUnit(line.source_unit)}{line.source_quantity_text !== line.canonical_quantity && <small>{t("记录为{0}", [(line.canonical_quantity) ?? ""])}</small>}</td><td className="numeric">{line.source_unit_price ?? t("未填写")}</td><td className="numeric">{line.source_amount ?? t("未填写")}</td></tr>)}</tbody></table></div>
      {review.preview.order.lines.some(line => line.quantity_policy.warning_codes.length > 0) && <p className="warning" role="status">{t("部分单位尚无精度规则，请逐行核对数量和单位。警告会随确认凭证保留。")}</p>}
      {review.preview.material_suggestions?.some(suggestion => !suggestion.automatic && !review.input.material_choices?.some(choice => choice.line_number === suggestion.line_number)) && <p className="warning">{t("部分客户料号已有对应，但内容变化、物料停用或单位待核对，本次未自动关联。可直接确认订单，或返回修改后人工选择。")}</p>}
      {existing && <p>{t("修订原因：{0}", [(reason) ?? ""])}</p>}
      <section className="work-confirm" aria-label={t("确认订单内容")}><h2>{t("确认本次内容")}</h2>
      <label className="checkbox"><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} disabled={busy || uncertain} />{t("我已核对客户、订单号、日期、货物编号、名称、规格、数量、单位、价格和物料对应（如有），确认以上内容")}</label>
      {uncertain && <p className="warning" role="status">{t("提交结果待确认。请重试本次提交；同一次请求不会重复生成订单。确认结果前请保留此页面。")}</p>}
      <div className="actions"><button onClick={() => void confirm()} disabled={!checked || busy}>{busy ? t("正在确认…") : uncertain ? t("重试本次提交") : existing ? t("确认修订") : t("确认生成订单")}</button><button className="secondary" onClick={() => { setReview(null); setError(""); }} disabled={busy || uncertain}>{t("返回修改")}</button></div>
      </section>
    </section> : newCustomer ? <section className="inline-customer work-panel"><h2>{t("新建客户")}</h2><NewCustomer onCreated={c => { onCustomer(c); setCustomer(c.id); setNewCustomer(false); }} onCancel={() => setNewCustomer(false)} /></section> : <form onSubmit={preview}>
      <section className="form-section work-panel"><h2>{t("订单信息")}</h2><div className="form-grid">
        <div className="customer-field"><label htmlFor="order-customer">{t("客户")}</label><select id="order-customer" value={customer} onChange={e => setCustomer(e.target.value)} required disabled={!!existing || busy}><option value="">{t("请选择客户")}</option>{customers.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select>{!existing && <button type="button" className="text-button" onClick={() => setNewCustomer(!newCustomer)} disabled={busy}>{t("新建客户")}</button>}</div>
        <div><label>{t("客户订单号")}<input value={number} onChange={e => setNumber(e.target.value)} maxLength={100} required disabled={!!existing || busy} placeholder={t("按客户订单填写")} aria-describedby={extraction && !extraction.candidate.order_number ? "missing-order-number" : undefined} /></label>{extraction && !extraction.candidate.order_number && <small id="missing-order-number" className="warning-text">{t("未可靠提取，请对照原件填写。")}</small>}</div>
        <div><label>{t("订单日期")}<input type="date" value={date} onChange={e => setDate(e.target.value)} required disabled={busy} aria-describedby={extraction && !extraction.candidate.business_date ? "missing-order-date" : undefined} /></label>{extraction && !extraction.candidate.business_date && <small id="missing-order-date" className="warning-text">{t("未可靠提取，请对照原件填写。")}</small>}</div>
        <div className="select-field"><label htmlFor="order-currency">{t("币种")}</label><select id="order-currency" value={currency} onChange={e => setCurrency(e.target.value)} required disabled={busy}><option value="">{t("请选择币种")}</option><option value="CNY">{t("CNY 人民币")}</option></select></div>
      </div></section>
      <section className="form-section work-panel"><div className="row-between work-panel-heading"><h2>{t("订单明细")}</h2><span className="muted">{t("{0} 行", [(lines.length) ?? ""])}</span></div><p className="muted">{t("请分别核对货物编号、名称和规格。数量最多三位小数，单价、金额未知时留空。")}</p>
        <div className="entry-lines">{lines.map((line, index) => <fieldset className="entry-line" key={index}><legend>{t("第{0} 行", [(index + 1)])}</legend>
          <div className="entry-material"><button type="button" className="text-button" onClick={() => setChoosingLine(choosingLine === index ? null : index)} disabled={busy}>{t("从物料池选择")}</button>{line.chosen && <span>{t("我方料号：{0}", [(line.chosen.own_code) ?? ""])}<button type="button" className="text-button" onClick={() => setLines(previous => previous.map((value, i) => i === index ? { ...value, chosen: null } : value))} disabled={busy}>{t("取消关联")}</button></span>}{choosingLine === index && <MaterialSelect initialQuery={line.item_name} disabled={busy} onSelect={material => chooseMaterial(index, material)} />}</div>
          <label className="item-code-field">{t("货物编号")}<input value={line.item_code} onChange={e => changeLine(index, "item_code", e.target.value)} maxLength={100} disabled={busy} placeholder={t("原件未提供则留空")} /></label>
          <label className="item-name-field">{t("货物名称")}<textarea value={line.item_name} onChange={e => changeLine(index, "item_name", e.target.value)} maxLength={500} disabled={busy} rows={2} /></label>
          <label className="specification-field">{t("规格型号")}<textarea value={line.specification} onChange={e => changeLine(index, "specification", e.target.value)} maxLength={1000} disabled={busy} rows={3} placeholder={t("按原件填写，可保留换行")} /></label>
          <label>{t("数量")}<input inputMode="decimal" value={line.quantity} onChange={e => changeLine(index, "quantity", e.target.value)} required maxLength={64} disabled={busy} /></label>
          <label>{t("单位")}<input value={line.unit} onChange={e => changeLine(index, "unit", e.target.value)} maxLength={40} placeholder={t("如 件、千克、米")} disabled={busy} /></label>
          <label>{t("订单单价")}<input inputMode="decimal" value={line.source_unit_price ?? ""} onChange={e => changeLine(index, "source_unit_price", e.target.value)} maxLength={64} placeholder={t("不知道可留空")} disabled={busy} /></label>
          <label>{t("原单金额")}<input inputMode="decimal" value={line.source_amount ?? ""} onChange={e => changeLine(index, "source_amount", e.target.value)} maxLength={64} placeholder={t("按原单填写，可留空")} disabled={busy} /></label>
          <button className="text-button danger-text" type="button" aria-label={t("删除第 {0} 行", [index + 1])} disabled={lines.length === 1 || busy} onClick={() => { setChoosingLine(null); setLines(previous => previous.filter((_, i) => i !== index)); }}>{t("移除行")}</button>
        </fieldset>)}</div>
        <button type="button" className="secondary" onClick={() => setLines(previous => [...previous, emptyLine()])} disabled={busy || lines.length >= 200}>{t("添加明细")}</button>
      </section>
      {existing && <label className="reason-field">{t("修订原因")}<textarea value={reason} onChange={e => setReason(e.target.value)} required maxLength={500} disabled={busy} /></label>}
      <div className="form-submit work-action-bar"><p className="muted">{t("下一步核对内容，尚不会创建订单。")}</p><button disabled={busy || newCustomer}>{busy ? t("校验中…") : t("核对订单")}</button></div>
    </form>}
    </div></div>
  </section>;
}
