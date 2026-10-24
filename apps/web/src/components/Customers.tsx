import { t, type UiMessage } from "../i18n";
import { useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Customer } from "../api";

export function NewCustomer({ onCreated, onCancel }: { onCreated: (customer: Customer) => void; onCancel?: () => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [uncertain, setUncertain] = useState(false);
  const command = useRef({ key: crypto.randomUUID(), name: "" });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!uncertain && command.current.name !== name) command.current = { key: crypto.randomUUID(), name };
    setBusy(true); setError("");
    try { const customer = await api.createCustomer(command.current.name, command.current.key); setName(""); setUncertain(false); onCreated(customer); }
    catch (failure) { setError(message(failure)); setUncertain(!(failure instanceof ApiError) || failure.status >= 500); }
    finally { setBusy(false); }
  }

  return <form onSubmit={submit} className="customer-form">
    <label>{t("客户完整名称")}<input autoFocus value={name} onChange={e => setName(e.target.value)} required maxLength={200} disabled={busy || uncertain} placeholder={t("请输入完整名称")} /></label>
    {error && <p role="alert" className="error">{t(error)}</p>}
    {uncertain && <p className="muted">{t("提交结果待确认。重试会查询同一次提交，不会重复创建。")}</p>}
    <div className="actions"><button disabled={busy || !name.trim()}>{busy ? t("保存中…") : uncertain ? t("重试本次创建") : t("创建客户")}</button>
      {onCancel && <button type="button" className="secondary" onClick={onCancel} disabled={busy || uncertain}>{t("取消")}</button>}</div>
  </form>;
}

export function Customers({ customers, canWrite, onCreated }: { customers: Customer[]; canWrite: boolean; onCreated: (customer: Customer) => void }) {
  return <section className="work-page customers-page">
    <div className="page-heading"><div><h1>{t("客户")}</h1><p>{t("创建后，在录入订单时明确选择客户。")}</p></div></div>
    <div className="customer-layout">
      <section aria-label={t("客户列表")} className="customer-directory work-panel"><h2>{t("客户列表")}<span className="count">{customers.length}</span></h2>
        {customers.length ? <ul>{customers.map(customer => <li key={customer.id}>{customer.full_name}</li>)}</ul> : <p className="empty-copy">{t("还没有客户。从右侧创建第一位客户。")}</p>}
      </section>
      {canWrite && <section className="new-customer-section work-panel"><h2>{t("新建客户")}</h2><p className="muted">{t("名称相同的客户无需重复创建。")}</p><NewCustomer onCreated={onCreated} /></section>}
    </div>
  </section>;
}
