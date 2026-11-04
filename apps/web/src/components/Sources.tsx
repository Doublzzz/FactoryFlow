import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, message, type Customer, type Extraction, type SourceSummary } from "../api";
import { FileDrop } from "./FileDrop";
import { OrderEntry } from "./OrderEntry";
import { extractionFailure } from "./SourceReview";

type UploadAttempt = { file: File; uploadKey: string; extractKey: string; sourceId?: string; runId?: string; completed?: boolean; error?: UiMessage };

export function Sources({ canWrite, customers, onCustomer, onManual, onOrder, onGuardChange }: {
  canWrite: boolean; customers: Customer[]; onCustomer: (customer: Customer) => void;
  onManual: () => void; onOrder: (id: string) => void; onGuardChange: (value: boolean) => void;
}) {
  const [items, setItems] = useState<SourceSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [review, setReview] = useState<Extraction | null>(null);
  const [lastOrder, setLastOrder] = useState<string | null>(null);
  const [progress, setProgress] = useState("");
  const [batch, setBatch] = useState<UploadAttempt[]>([]);
  const attempts = useRef<UploadAttempt[]>([]);
  const retry = useRef<{ sourceId: string; key: string; runId?: string } | null>(null);
  useEffect(() => { onGuardChange(busy || !!review); return () => onGuardChange(false); }, [busy, review, onGuardChange]);
  useEffect(() => { window.scrollTo(0, 0); }, [review]);
  useEffect(() => {
    if (!busy && !files.length) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", prevent); return () => window.removeEventListener("beforeunload", prevent);
  }, [busy, files.length]);
  async function load(next?: string) { const result = await api.sources(next); setItems(old => next ? [...old, ...result.items] : result.items); setCursor(result.next_cursor); }
  useEffect(() => { void load().catch(e => setError(message(e))); }, []);
  async function recognize(sourceId: string, key: string) {
    retry.current ??= { sourceId, key };
    const attempt = retry.current;
    if (!attempt.runId) attempt.runId = (await api.extract(attempt.sourceId, attempt.key)).extraction_id;
    const detail = await api.extraction(attempt.runId);
    await load();
    retry.current = null; setReview(detail);
  }
  async function upload(event: FormEvent) {
    event.preventDefault(); if (!files.length || busy) return;
    if (!attempts.current.length) attempts.current = files.map(file => ({ file, uploadKey: crypto.randomUUID(), extractKey: crypto.randomUUID() }));
    setBusy(true); setError(""); setNotice(""); setLastOrder(null);
    try {
      for (const [index, attempt] of attempts.current.entries()) {
        if (attempt.completed) continue;
        setProgress(t("正在处理第{0} / {1}份：{2}", [index + 1, attempts.current.length, attempt.file.name]));
        delete attempt.error;
        try {
          if (!attempt.sourceId) attempt.sourceId = (await api.upload(attempt.file, attempt.uploadKey)).source_id;
          const source = await api.source(attempt.sourceId);
          if (!source.order_id) {
            attempt.runId ??= source.extraction_id ?? (await api.extract(attempt.sourceId, attempt.extractKey)).extraction_id;
            const detail = await api.extraction(attempt.runId);
            if (detail.status === "failed") attempt.error = extractionFailure(detail.error_code);
          }
          attempt.completed = true;
        } catch (failure) {
          attempt.error = message(failure);
          if (failure instanceof ApiError && failure.status === 401) break;
        } finally { setBatch(attempts.current.map(item => ({ ...item }))); }
      }
      await load();
      if (attempts.current.every(attempt => attempt.completed)) {
        const failures = attempts.current.filter(attempt => attempt.error);
        setNotice(failures.length
          ? msg("已完成{0}份，{1}份识别失败，请查看原因。", [attempts.current.length - failures.length, failures.length])
          : msg("已就绪{0}份原件；已有记录已复用，请从列表继续。", [attempts.current.length]));
        setFiles([]); setBatch(failures); attempts.current = [];
      }
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); setProgress(""); }
  }
  async function open(item: SourceSummary, rerun = false) {
    if (busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (item.order_id) onOrder(item.order_id);
      else if (item.extraction_id && !rerun) setReview(await api.extraction(item.extraction_id));
      else { retry.current = null; await recognize(item.source_id, crypto.randomUUID()); }
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function resume() {
    if (!retry.current || busy) return; setBusy(true); setError("");
    try { await recognize(retry.current.sourceId, retry.current.key); } catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  if (review) return <OrderEntry key={review.extraction_id} customers={customers} extraction={review} onCustomer={onCustomer}
    onCancel={() => setReview(null)} onSaved={id => { setReview(null); setLastOrder(id); setNotice(msg("订单已确认并保存。")); void load().catch(failure => setError(message(failure))); }} />;
  return <section className="work-page sources-page"><div className="page-heading"><div><h1>{t("上传订单照片 / 文件")}</h1></div>{canWrite && <button className="secondary" onClick={onManual} disabled={busy}>{t("直接填写订单")}</button>}</div>
    {notice && <div className={batch.some(item => item.error) ? "warning" : "success"} role="status">{t(notice)}{lastOrder && <button type="button" className="text-button" onClick={() => onOrder(lastOrder)}>{t("打开订单")}</button>}</div>}
    {canWrite && <form className="upload-panel upload-drop-panel work-panel" onSubmit={upload} aria-label={t("上传客户订单")}><FileDrop files={files} maxFiles={5} disabled={busy} onFiles={next => { setFiles(next); attempts.current = []; setBatch([]); retry.current = null; setError(""); setNotice(""); }} /><div className="upload-drop-footer"><p className="muted">{t("每份文件单独识别，人工确认后分别保存为订单。")}</p><button disabled={!files.length || busy}>{busy ? t("本地处理中，请稍候…") : batch.length ? t("重试未完成的文件") : t("上传并识别")}</button></div></form>}
    {progress && <p role="status">{progress}</p>}
    {batch.some(item => item.error) && <ul className="batch-errors">{batch.filter(item => item.error).map(item => <li key={item.uploadKey} role="alert"><strong>{item.file.name}</strong>：{t(item.error!)}</li>)}</ul>}
    {error && <p role="alert" className="error">{t(error)}</p>}{retry.current && <button className="secondary" onClick={() => void resume()} disabled={busy}>{t("重试本次识别")}</button>}
    <section className="form-section work-panel"><div className="row-between work-panel-heading"><h2>{t("订单原件")}</h2><button className="text-button" disabled={busy} onClick={() => void load().catch(failure => setError(message(failure)))}>{t("刷新列表")}</button></div>{!items.length ? <p className="muted">{t("上传过的订单原件会列在这里，随时可以下载核对。")}</p> : <ul className="source-list">{items.map(item => <li key={item.source_id}><div><strong>{item.filename}</strong><p className="muted">{item.order_id ? t("已生成订单") : item.extraction_status === "failed" ? t("识别失败") : item.extraction_id ? t("待确认订单") : t("等待识别")}</p></div><div className="actions"><a href={"/api/v1/sources/" + item.source_id + "/download"}>{t("下载")}</a>{(canWrite || item.order_id) && <button className="secondary" disabled={busy} onClick={() => void open(item)}>{item.order_id ? t("打开订单") : item.extraction_status === "failed" ? t("查看原因 / 手工填写") : item.extraction_id ? t("核对并保存") : t("开始识别")}</button>}{canWrite && item.extraction_id && !item.order_id && <button className="text-button" disabled={busy} onClick={() => void open(item, true)}>{t("重新识别")}</button>}</div></li>)}</ul>}{cursor && <button className="secondary" disabled={busy} onClick={() => void load(cursor).catch(failure => setError(message(failure)))}>{t("加载更多")}</button>}</section>
  </section>;
}
