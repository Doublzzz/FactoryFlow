import { getLocale, msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Delivery, type DeliveryLayout as LayoutDetail, type DeliveryLayoutConfig as Config } from "../api";
import "./delivery-layout.css";

type NumberKey = "paper_width_mm" | "paper_height_mm" | "margin_top_mm" | "margin_bottom_mm" | "margin_left_mm" | "margin_right_mm" | "font_size_pt" | "title_size_pt" | "row_height_mm" | "rows_per_page";
const numericFields: { key: NumberKey; label: string; min: number; max: number }[] = [
  { key: "paper_width_mm", label: "纸张宽度（mm）", min: 100, max: 420 },
  { key: "paper_height_mm", label: "纸张高度（mm）", min: 100, max: 420 },
  { key: "margin_left_mm", label: "左边距（mm）", min: 0, max: 40 },
  { key: "margin_right_mm", label: "右边距（mm）", min: 0, max: 40 },
  { key: "margin_top_mm", label: "上边距（mm）", min: 0, max: 40 },
  { key: "margin_bottom_mm", label: "下边距（mm）", min: 0, max: 40 },
  { key: "font_size_pt", label: "正文字号（pt）", min: 8, max: 16 },
  { key: "title_size_pt", label: "标题字号（pt）", min: 12, max: 26 },
  { key: "row_height_mm", label: "最小行高（mm）", min: 6, max: 18 },
  { key: "rows_per_page", label: "每页最多明细行", min: 1, max: 30 },
];
const textFields = [
  ["title", "单据标题", 40], ["company_name", "公司名称", 100], ["address", "公司地址", 240],
  ["phone", "电话", 60], ["fax", "传真", 60], ["postcode", "邮编", 20], ["delivery_person", "默认送货人", 60],
] as const;

export function DeliveryLayout({ delivery, canWrite, onClose, onGuardChange }: {
  delivery: Delivery; canWrite: boolean; onClose: () => void; onGuardChange: (value: boolean) => void;
}) {
  const [saved, setSaved] = useState<LayoutDetail | null>(null);
  const [edit, setEdit] = useState<Config | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [html, setHtml] = useState("");
  const [previewKey, setPreviewKey] = useState("");
  const [rendered, setRendered] = useState<{ pages: number; blocked: boolean } | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [conflict, setConflict] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const pending = useRef<{ key: string; body: { expected_version: number; config: Config } } | null>(null);
  const locale = getLocale();
  const serial = JSON.stringify(edit);
  const previewIdentity = (config: Config | null, language = locale) => JSON.stringify([language, config]);
  const dirty = !!saved && serial !== JSON.stringify(saved.config);
  const stale = previewKey !== previewIdentity(edit);
  const blocked = busy || uncertain;

  useEffect(() => {
    onGuardChange(busy || uncertain || dirty);
    return () => onGuardChange(false);
  }, [busy, uncertain, dirty, onGuardChange]);
  useEffect(() => {
    if (!dirty && !uncertain) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, uncertain]);
  useEffect(() => {
    const ready = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || event.data?.type !== "delivery-print-ready") return;
      if (typeof event.data.blocked === "boolean" && Number.isInteger(event.data.pages)) setRendered({ pages: event.data.pages, blocked: event.data.blocked });
    };
    window.addEventListener("message", ready);
    return () => window.removeEventListener("message", ready);
  }, []);
  useEffect(() => {
    let active = true;
    const initialLocale = getLocale();
    api.deliveryLayout(initialLocale).then(async value => {
      if (!active) return;
      setSaved(value); setEdit(value.config);
      const result = await api.previewDeliveryLayout(delivery.id, value.config, initialLocale);
      if (active && getLocale() === initialLocale) { setHtml(result); setPreviewKey(previewIdentity(value.config, initialLocale)); }
    }).catch(failure => { if (active) setError(message(failure)); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [delivery.id]);
  // Language changes invalidate presentation only; never reinitialize edited content.
  useEffect(() => { setRendered(null); }, [locale]);

  async function preview(config: Config) {
    if (!form.current?.reportValidity()) return;
    setBusy(true); setError(""); setRendered(null);
    const requestLocale = locale;
    try {
      const result = await api.previewDeliveryLayout(delivery.id, config, requestLocale);
      if (getLocale() === requestLocale) { setHtml(result); setPreviewKey(previewIdentity(config, requestLocale)); }
    }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function reload() {
    setBusy(true); setError(""); setRendered(null);
    const requestLocale = locale;
    try {
      const current = await api.deliveryLayout(requestLocale);
      setSaved(current); setEdit(current.config); setConflict(false); setNotice("");
      const result = await api.previewDeliveryLayout(delivery.id, current.config, requestLocale);
      if (getLocale() === requestLocale) { setHtml(result); setPreviewKey(previewIdentity(current.config, requestLocale)); }
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function restoreDefaults() {
    setBusy(true); setError("");
    try {
      const defaults = (await api.deliveryLayout(locale)).defaults;
      setEdit(defaults); setNotice(msg("已恢复内置版式，更新预览并保存后才会生效。"));
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!saved || !edit || busy || !canWrite) return;
    if (!uncertain) {
      if (stale || !rendered || rendered.blocked || !dirty || conflict) return;
      pending.current = { key: crypto.randomUUID(), body: { expected_version: saved.version, config: edit } };
    }
    if (!pending.current) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.saveDeliveryLayout(pending.current.body, pending.current.key);
      pending.current = null; setUncertain(false); setSaved(result); setEdit(result.config);
      setNotice(msg("已保存为默认模板 v{0}，以后打开送货打印页会使用此版面。", [result.version]));
      setPreviewKey(""); // Re-preview the saved version before printing it.
    } catch (failure) {
      setError(message(failure));
      setUncertain(!(failure instanceof ApiError) || failure.status >= 500);
      if (failure instanceof ApiError && failure.code === "VERSION_CONFLICT") setConflict(true);
    } finally { setBusy(false); }
  }
  function change<K extends keyof Config>(key: K, value: Config[K]) {
    if (!edit) return;
    setEdit({ ...edit, [key]: value }); setNotice("");
  }
  function moveColumn(index: number, direction: number) {
    if (!edit) return;
    const columns = [...edit.columns]; const target = index + direction;
    const source = columns[index]; const other = columns[target];
    if (!source || !other) return;
    columns[index] = other; columns[target] = source; change("columns", columns);
  }
  return <section className="delivery-layout work-page">
    <button className="back-button" disabled={blocked} onClick={onClose}>{dirty ? t("放弃未保存调整并返回") : t("返回送货详情")}</button>
    <div className="page-heading"><div><h1>{t("送货单版面设置")}</h1><p>{t("沿用连续纸版式，边调整边预览。保存后作为本工厂共用的默认模板。")}</p></div></div>
    <p className="muted">{t("语言切换只更新界面与本次打印说明；自定义版式文字保持原样。")}</p>
    <nav className="work-section-nav" aria-label={t("版面设置区域")}><a href="#delivery-layout-controls">{t("模板内容")}</a><a href="#delivery-layout-preview">{t("打印预览")}</a></nav>
    {error && <div className="error" role="alert">{t(error)}{!uncertain && <button type="button" className="text-button" disabled={busy} onClick={() => void reload()}>{conflict ? t("载入最新模板，放弃本次调整") : t("重新载入模板")}</button>}</div>}
    {notice && <p className="notice" role="status">{t(notice)}</p>}
    {uncertain && <p className="warning" role="status">{t("保存结果待确认。请重试本次保存，确认前不能更改内容。")}</p>}
    {!canWrite && <p className="muted">{t("只读账号可调整预览；保存模板需要操作员或管理员账号。")}</p>}
    {saved && edit ? <div className="layout-workspace">
      <form ref={form} onSubmit={save} id="delivery-layout-controls" tabIndex={-1} className="layout-controls work-panel">
        <div className="layout-version"><strong>{t("本工厂默认模板")}</strong><span>{saved.version ? t("已保存 v{0}", [saved.version]) : t("内置版式")}{dirty ? t(" · 有未保存调整") : ""}</span></div>
        <fieldset disabled={blocked}>
          <legend>{t("抬头与送货信息")}</legend>
          {textFields.map(([key, label, max]) => <label key={key}>{t(label)}<input value={edit[key]} required={key === "title"} maxLength={max} onChange={event => change(key, event.target.value)} /></label>)}
        </fieldset>
        <details><summary>{t("纸张、边距与字号")}</summary><fieldset className="layout-number-grid" disabled={blocked}><legend className="sr-only">{t("纸张、边距与字号")}</legend>
          {numericFields.map(item => <label key={item.key}>{t(item.label)}<input type="number" required min={item.min} max={item.max} step={1} value={edit[item.key]} onChange={event => change(item.key, Number(event.target.value))} /></label>)}
        </fieldset><p className="muted">{t("原版连续纸：243 × 140 mm。内容超过一页会继续到下一页，送货单号保持不变。")}</p></details>
        <details><summary>{t("明细列与顺序")}</summary><fieldset disabled={blocked}><legend className="sr-only">{t("明细列设置")}</legend>
          {edit.columns.map((col, index) => <div className="layout-column" key={col.key}>
            <label>{t("第{0} 列名称", [(index + 1)])}<input value={col.label} required maxLength={30} onChange={event => change("columns", edit.columns.map((c, i) => i === index ? { ...c, label: event.target.value } : c))} /></label>
            <label>{t("宽度（mm）")}<input type="number" required min={6} max={200} step={1} value={col.width_mm} onChange={event => change("columns", edit.columns.map((c, i) => i === index ? { ...c, width_mm: Number(event.target.value) } : c))} /></label>
            <div className="layout-column-move"><button className="text-button" type="button" disabled={index === 0} aria-label={t("上移第{0}列", [index + 1])} onClick={() => moveColumn(index, -1)}>{t("上移")}</button><button className="text-button" type="button" disabled={index === edit.columns.length - 1} aria-label={t("下移第{0}列", [index + 1])} onClick={() => moveColumn(index, 1)}>{t("下移")}</button></div>
          </div>)}
        </fieldset><p className="muted">{t("各列合计{0} mm / 纸张可用{1} mm", [(edit.columns.reduce((sum, col) => sum + col.width_mm, 0)) ?? "", (edit.paper_width_mm - edit.margin_left_mm - edit.margin_right_mm)])}</p></details>
        <details><summary>{t("备注与签收区")}</summary><fieldset disabled={blocked}><legend className="sr-only">{t("备注与签收区")}</legend>
          <label>{t("固定备注")}<textarea maxLength={300} value={edit.footer_note} onChange={event => change("footer_note", event.target.value)} /></label>
          {edit.signatures.map((text, index) => <label key={index}>{t("签收栏{0}", [(index + 1)])}<input maxLength={40} value={text} onChange={event => change("signatures", edit.signatures.map((v, i) => i === index ? event.target.value : v))} /></label>)}
        </fieldset></details>
        <div className="layout-save-actions"><button className="secondary" type="button" disabled={blocked} onClick={() => void preview(edit)}>{busy ? t("正在处理…") : t("更新预览")}</button>
          {canWrite && <button disabled={busy || (!uncertain && (!dirty || stale || !rendered || rendered.blocked || conflict))}>{uncertain ? t("重试本次保存") : t("保存为默认模板")}</button>}
          <button className="text-button" type="button" disabled={blocked} onClick={() => void restoreDefaults()}>{t("恢复内置版式")}</button>
        </div>
        {dirty && stale && <p className="muted">{t("调整后先更新预览，再保存模板。")}</p>}
      </form>
      <section id="delivery-layout-preview" tabIndex={-1} className="layout-preview work-panel" aria-label={t("送货单预览")}>
        <div className="layout-preview-heading"><div><h2>{t("打印预览")}</h2><p>{delivery.customer_name} · {delivery.delivery_date}</p></div><button className="secondary" disabled={busy || stale || !rendered || rendered.blocked} onClick={() => frame.current?.contentWindow?.postMessage({ type: "delivery-print" }, "*")}>{t("打印此预览")}</button></div>
        <p className={stale ? "warning" : "muted"} role="status">{stale ? t("设置已变化，请更新预览。") : !rendered ? t("正在排版…") : rendered.blocked ? t("当前内容无法完整放入纸张，请查看预览提示并调整。") : t("{0} 页 · {1} · 预览按窗口缩放，打印使用实际纸张尺寸", [rendered.pages, dirty ? t("未保存的版面") : saved.version ? t("模板 v{0}", [saved.version]) : t("内置版式")])}</p>
        {html && <iframe ref={frame} title={t("送货单打印版面")} srcDoc={html} sandbox="allow-scripts allow-modals" />}
      </section>
    </div> : busy && <p role="status">{t("正在读取默认模板…")}</p>}
  </section>;
}
