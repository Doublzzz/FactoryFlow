import { useEffect, useState } from "react";
import { api, message, type Supplier } from "../api";
import { t, type UiMessage } from "../i18n";

export function SupplierSelect({ selected, disabled, onSelect }: { selected: Supplier | null; disabled: boolean; onSelect: (item: Supplier) => void }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [items, setItems] = useState<Supplier[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<UiMessage>("");
  useEffect(() => {
    let live = true; setLoading(true); setError("");
    api.suppliers(filter, offset).then(page => { if (live) { setItems(page.items); setTotal(page.total); } })
      .catch(failure => { if (live) { setItems([]); setError(message(failure)); } }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [filter, offset, refresh]);
  function search() { setOffset(0); setFilter(query.trim()); setRefresh(value => value + 1); }
  return <section className="purchasing-picker" aria-label={t("选择供应商")}>
    {selected && <p role="status">{t("已选供应商：{0}", [selected.full_name])}</p>}
    <div className="material-search"><label>{t("查找供应商")}<input value={query} disabled={disabled} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); search(); } }} /></label><button type="button" className="secondary" disabled={disabled || loading} onClick={search}>{t("查找")}</button></div>
    {error && <p className="error" role="alert">{t(error)}<button type="button" className="text-button" disabled={disabled || loading} onClick={search}>{t("重试")}</button></p>}
    {loading ? <p role="status">{t("正在读取供应商…")}</p> : !items.length ? <p className="muted">{t("没有找到供应商，可调整关键词。")}</p> : <ul className="material-options">{items.map(item => <li key={item.id}><span>{item.full_name}{!item.active && <small>{t("已停用")}</small>}</span><button type="button" className="secondary" disabled={disabled || !item.active} onClick={() => onSelect(item)} aria-label={t("选择供应商 {0}", [item.full_name])}>{t("选择")}</button></li>)}</ul>}
    <div className="actions">{offset > 0 && <button type="button" className="text-button" disabled={disabled || loading} onClick={() => setOffset(Math.max(0, offset - 50))}>{t("上一页")}</button>}{offset + items.length < total && <button type="button" className="text-button" disabled={disabled || loading} onClick={() => setOffset(offset + 50)}>{t("下一页")}</button>}</div>
  </section>;
}
