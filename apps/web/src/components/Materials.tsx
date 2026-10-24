import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Customer, type Material, type MaterialInput, type MaterialCode, type Schemas } from "../api";
import { MaterialFields } from "./MaterialSelect";
import { MaterialImport } from "./MaterialImport";
import { displayUnit } from "../units";

function MaterialEditor({ current, onSaved, onClose }: {
  current: Material | null; onSaved: () => void; onClose: () => void;
}) {
  const [draft, setDraft] = useState<MaterialInput>(current ? { own_code: current.own_code, name: current.name, specification: current.specification ?? null, unit: current.unit ?? null } : { name: "", own_code: "", specification: "", unit: "" });
  const [active, setActive] = useState(current?.active ?? true);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const pending = useRef<{ key: string; body: MaterialInput; reason: string; active: boolean } | null>(null);
  async function save(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    if (!uncertain) pending.current = { key: crypto.randomUUID(), body: draft, reason, active };
    if (!pending.current) return;
    setBusy(true); setError("");
    const command = pending.current;
    try {
      if (current) await api.updateMaterial(current.id, { ...command.body, expected_version: current.version, reason: command.reason, active: command.active }, command.key);
      else await api.createMaterial(command.body, command.key);
      setUncertain(false); onSaved();
    } catch (failure) { setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }
  return <section className="work-panel material-editor"><h2>{current ? t("维护物料") : t("新建物料")}</h2>
    <p className="muted">{current ? t("更正料号或名称保留物料身份；停用后保留原关联。已有规格和单位在这里保留，可补齐空白项。") : t("只需填写名称。已有我方料号就沿用，没有则留空，保存时自动编号。")}</p>
    <form onSubmit={save}><MaterialFields value={draft} onChange={setDraft} disabled={busy || uncertain} {...(current ? { fixed: current } : {})} />
      {current && <><label className="checkbox"><input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} disabled={busy || uncertain} />{t("允许新订单选择这条物料")}</label><label>{t("维护原因")}<textarea value={reason} onChange={e => setReason(e.target.value)} required maxLength={500} disabled={busy || uncertain} /></label></>}
      {error && <p role="alert" className="error">{t(error)}</p>}{uncertain && <p className="warning" role="status">{t("结果待确认。请重试本次保存，不会重复建档。")}</p>}
      <div className="actions"><button disabled={busy || !draft.name.trim()}>{busy ? t("保存中…") : uncertain ? t("重试本次保存") : current ? t("保存物料更正") : t("保存物料")}</button><button type="button" className="secondary" onClick={onClose} disabled={busy || uncertain}>{t("取消")}</button></div>
    </form>
  </section>;
}

function MaterialCodes({ material, customers, canWrite, onClose }: {
  material: Material; customers: Customer[]; canWrite: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<MaterialCode[]>([]);
  const [customer, setCustomer] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState(material.name);
  const [specification, setSpecification] = useState(material.specification ?? "");
  const [unit, setUnit] = useState(material.unit ?? "");
  const [mapping, setMapping] = useState<MaterialCode | null>(null);
  const [mappingLoading, setMappingLoading] = useState(false);
  const [lookupError, setLookupError] = useState<UiMessage>("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [refresh, setRefresh] = useState(0);
  const pending = useRef<{ key: string; body: Schemas["MaterialCodeInput"] } | null>(null);
  useEffect(() => { let live = true; api.materialCodes(material.id).then(result => { if (live) setItems(result.items); }).catch(failure => { if (live) setError(message(failure)); }); return () => { live = false; }; }, [material.id, refresh]);
  useEffect(() => {
    let live = true; setMapping(null); setLookupError("");
    if (!customer || !code.trim()) { setMappingLoading(false); return; }
    setMappingLoading(true);
    api.materialCodes(undefined, customer, code.trim()).then(result => { if (live) setMapping(result.items[0] ?? null); }).catch(failure => { if (live) setLookupError(message(failure)); }).finally(() => { if (live) setMappingLoading(false); });
    return () => { live = false; };
  }, [customer, code, refresh]);
  async function save(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    if (!uncertain) pending.current = { key: crypto.randomUUID(), body: {
      customer_id: customer, customer_code: code.trim(), material_id: material.id, expected_material_version: material.version,
      expected_mapping_version: mapping?.version ?? 0, item_name: name || null, specification: specification || null, unit: unit || null, reason: reason || null,
    } };
    if (!pending.current) return;
    setBusy(true); setError(""); setNotice("");
    try { await api.saveMaterialCode(pending.current.body, pending.current.key); setUncertain(false); setNotice(msg("客户料号对应已保存，历史订单关联保持原样。")); setCode(""); setReason(""); setRefresh(value => value + 1); }
    catch (failure) { setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }
  return <section className="work-panel material-editor"><div className="row-between"><h2>{t("{0} · 客户料号", [(material.own_code) ?? ""])}</h2><button className="text-button" onClick={onClose} disabled={busy || uncertain}>{t("关闭")}</button></div>
    <p>{material.name} · {material.specification || t("规格暂缺")}</p>
    {items.length ? <ul className="material-options">{items.map(item => <li key={`${item.customer_id}:${item.customer_code}`}><div><strong>{customers.find(c => c.id === item.customer_id)?.full_name ?? t("客户资料未载入")}</strong><small>{t("客户料号：{0} · {1} · {2} · {3}", [(item.customer_code) ?? "", (item.item_name || t("名称暂缺")) ?? "", (item.specification || t("规格暂缺")) ?? "", (item.canonical_unit || t("单位待核对")) ?? ""])}</small></div>{canWrite && <button type="button" className="text-button" disabled={busy || uncertain} onClick={() => { setCustomer(item.customer_id); setCode(item.customer_code); setName(item.item_name ?? ""); setSpecification(item.specification ?? ""); setUnit(item.canonical_unit ?? ""); setReason(""); }}>{t("更正对应")}</button>}</li>)}</ul> : <p className="muted">{t("尚未记录客户料号。同一物料可对应不同客户的不同料号。")}</p>}
    {items.length === 1000 && <p className="warning">{t("当前展示前 1,000 条，新增或更正时会按客户和料号精确核对。")}</p>}
    {canWrite && material.active && <form onSubmit={save}>
      <h3>{t("新增或更正一个客户料号")}</h3><div className="form-grid">
        <div><label htmlFor="material-code-customer">{t("对应客户")}</label><select id="material-code-customer" value={customer} onChange={e => setCustomer(e.target.value)} required disabled={busy || uncertain}><option value="">{t("请选择已有客户")}</option>{customers.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select></div>
        <label>{t("客户料号")}<input value={code} onChange={e => setCode(e.target.value)} required maxLength={100} disabled={busy || uncertain} /></label>
        <label>{t("客户单据上的名称")}<input value={name} onChange={e => setName(e.target.value)} maxLength={500} disabled={busy || uncertain} /></label>
        <label>{t("客户单据上的规格")}<input value={specification} onChange={e => setSpecification(e.target.value)} maxLength={1000} disabled={busy || uncertain} /></label>
        <label>{t("客户单据上的单位")}<input value={unit} onChange={e => setUnit(e.target.value)} maxLength={40} disabled={busy || uncertain} /></label>
      </div><p className="muted">{t("以后下单时，只有这些已确认内容一致，才会带出此物料；缺少或未知单位仍由人选择。")}</p>
      {mapping && <><p className="warning">{t("这个客户料号已有对应。更正只影响以后选择，不改历史订单。")}</p><label>{t("对应更正原因")}<textarea value={reason} onChange={e => setReason(e.target.value)} required maxLength={500} disabled={busy || uncertain} /></label></>}
      {lookupError && <p role="alert" className="error">{t(lookupError)}</p>}{uncertain && <p className="warning">{t("结果待确认，请重试本次保存。")}</p>}
      <button disabled={busy || !uncertain && (mappingLoading || !!lookupError)}>{busy ? t("保存中…") : uncertain ? t("重试本次对应") : t("保存客户料号对应")}</button>
    </form>}
    {error && <p className="error" role="alert">{t(error)}</p>}{notice && <p role="status" className="success">{t(notice)}</p>}
  </section>;
}

export function Materials({ customers, canWrite, onGuardChange }: {
  customers: Customer[]; canWrite: boolean; onGuardChange: (blocked: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [items, setItems] = useState<Material[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [panel, setPanel] = useState<{ kind: "edit"; item: Material | null } | { kind: "codes"; item: Material } | { kind: "import" } | null>(null);
  useEffect(() => {
    onGuardChange(!!panel);
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    if (panel) window.addEventListener("beforeunload", prevent);
    return () => { onGuardChange(false); window.removeEventListener("beforeunload", prevent); };
  }, [panel, onGuardChange]);
  useEffect(() => { let live = true; setLoading(true); setError(""); api.materials(filter, offset).then(result => { if (live) { setItems(result.items); setNext(result.next_offset); } }).catch(failure => { if (live) setError(message(failure)); }).finally(() => { if (live) setLoading(false); }); return () => { live = false; }; }, [filter, offset, refresh]);
  if (panel?.kind === "import") return <MaterialImport customers={customers} onClose={() => setPanel(null)} onImported={result => { setPanel(null); setOffset(0); setNotice(msg("导入完成：新建 {0} 条、关联已有 {1} 条、跳过 {2} 行。", [result.created_count, result.reused_count, result.skipped_count])); setRefresh(value => value + 1); }} />;
  return <section className="work-page materials-page">
    <div className="page-heading"><div><h1>{t("物料池")}</h1><p>{t("统一我方料号，记住各客户的料号。订单可以先做，需要时再收录。")}</p></div>{canWrite && <div className="actions"><button className="secondary" onClick={() => { setPanel({ kind: "import" }); setNotice(""); }} disabled={!!panel}>{t("导入资料表")}</button><button onClick={() => { setPanel({ kind: "edit", item: null }); setNotice(""); }} disabled={!!panel}>{t("新建物料")}</button></div>}</div>
    {notice && <p className="success" role="status">{t(notice)}</p>}
    {panel?.kind === "edit" && <MaterialEditor key={panel.item?.id ?? "new"} current={panel.item} onClose={() => setPanel(null)} onSaved={() => { setPanel(null); setNotice(msg("物料已保存。")); setRefresh(value => value + 1); }} />}
    {panel?.kind === "codes" && <MaterialCodes key={panel.item.id} material={panel.item} customers={customers} canWrite={canWrite} onClose={() => { setPanel(null); setRefresh(value => value + 1); }} />}
    <section className="work-panel"><form className="material-search" onSubmit={event => { event.preventDefault(); setOffset(0); setFilter(query.trim()); setRefresh(value => value + 1); }}><label>{t("搜索物料")}<input value={query} onChange={e => setQuery(e.target.value)} placeholder={t("我方料号、客户料号、名称或规格")} disabled={!!panel} /></label><button className="secondary" disabled={!!panel}>{t("查询")}</button></form>
      {error && <p className="error" role="alert">{t(error)}</p>}
      {loading ? <p role="status">{t("正在读取物料…")}</p> : !items.length ? <p className="empty-copy">{filter ? t("没有找到匹配的物料。") : t("还没有物料。可在这里新建，也可以先下订单，之后从订单明细收录。")}</p> : <div className="table-wrap"><table><thead><tr><th>{t("我方料号")}</th><th>{t("物料名称 / 规格")}</th><th>{t("基本单位")}</th><th>{t("状态")}</th><th>{t("操作")}</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.own_code}</td><td><strong>{item.name}</strong><small className="material-spec">{item.specification || t("规格暂缺")}</small>{item.matched_customer_codes?.map(code => <small className="material-spec" key={`${code.customer_name}:${code.customer_code}`}>{t("客户：{0} · 料号：{1}", [(code.customer_name) ?? "", (code.customer_code) ?? ""])}</small>)}</td><td>{displayUnit(item.unit)}</td><td>{item.active ? t("可用") : t("已停用")}</td><td><div className="actions"><button className="text-button" disabled={!!panel} onClick={() => setPanel({ kind: "codes", item })}>{t("客户料号")}</button>{canWrite && <button className="text-button" disabled={!!panel} onClick={() => setPanel({ kind: "edit", item })}>{t("维护")}</button>}</div></td></tr>)}</tbody></table></div>}
      <div className="actions">{offset > 0 && <button className="secondary" disabled={loading || !!panel} onClick={() => setOffset(Math.max(0, offset - 50))}>{t("上一页")}</button>}{next !== null && <button className="secondary" disabled={loading || !!panel} onClick={() => setOffset(next)}>{t("下一页")}</button>}</div>
    </section>
  </section>;
}
