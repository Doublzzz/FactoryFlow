import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useState, type FormEvent } from "react";
import { api, message, type Extraction, type SourceSummary } from "../api";
import { FileDrop } from "./FileDrop";

export function Sources({ canWrite, initialFile, onManual, onReview, onOrder, onGuardChange }: { canWrite: boolean; initialFile?: File | undefined; onManual: () => void; onReview: (value: Extraction) => void; onOrder: (id: string) => void; onGuardChange: (value: boolean) => void }) {
  const [items, setItems] = useState<SourceSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(initialFile ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [retry, setRetry] = useState<{ sourceId: string; key: string } | null>(null);
  const [uploadKey, setUploadKey] = useState(() => crypto.randomUUID());
  useEffect(() => { onGuardChange(busy); return () => onGuardChange(false); }, [busy, onGuardChange]);
  async function load(next?: string) { const result = await api.sources(next); setItems(old => next ? [...old, ...result.items] : result.items); setCursor(result.next_cursor); }
  useEffect(() => { void load().catch(e => setError(message(e))); }, []);
  async function recognize(sourceId: string, key: string) {
    setRetry({ sourceId, key });
    const result = await api.extract(sourceId, key);
    setRetry(null);
    onReview(await api.extraction(result.extraction_id));
  }
  async function upload(event: FormEvent) {
    event.preventDefault(); if (!file || busy) return;
    if (file.size > 10 * 1024 * 1024) { setError(msg("文件最多 10 MiB，请拆分后上传。")); return; }
    setBusy(true); setError("");
    try { const result = await api.upload(file, uploadKey); await recognize(result.source_id, crypto.randomUUID()); }
    catch (e) { setError(message(e)); await load().catch(() => {}); }
    finally { setBusy(false); }
  }
  async function open(item: SourceSummary, rerun = false) {
    setBusy(true); setError("");
    try {
      if (item.order_id) onOrder(item.order_id);
      else if (item.extraction_id && !rerun) onReview(await api.extraction(item.extraction_id));
      else await recognize(item.source_id, crypto.randomUUID());
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }
  async function resume() {
    if (!retry || busy) return; setBusy(true); setError("");
    try { await recognize(retry.sourceId, retry.key); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <section className="work-page sources-page"><div className="page-heading"><div><h1>{t("上传订单照片 / 文件")}</h1></div>{canWrite && <button className="secondary" onClick={onManual} disabled={busy}>{t("直接填写订单")}</button>}</div>
    {canWrite && <form className="upload-panel upload-drop-panel work-panel" onSubmit={upload} aria-label={t("上传客户订单")}><FileDrop file={file} disabled={busy} onFile={next => { setFile(next); setUploadKey(crypto.randomUUID()); setRetry(null); setError(""); }} /><div className="upload-drop-footer"><p className="muted">{t("文件只保存在这台电脑，识别也在本机完成；识别结果要你对照原件确认后才会存成订单。")}</p><button disabled={!file || busy}>{busy ? t("本地处理中，请稍候…") : t("上传并识别")}</button></div></form>}
    {error && <p role="alert" className="error">{t(error)}</p>}{retry && <button className="secondary" onClick={() => void resume()} disabled={busy}>{t("重试本次识别")}</button>}
    <section className="form-section work-panel"><div className="row-between work-panel-heading"><h2>{t("订单原件")}</h2><button className="text-button" disabled={busy} onClick={() => void load().catch(e => setError(message(e)))}>{t("刷新列表")}</button></div>{!items.length ? <p className="muted">{t("上传过的订单原件会列在这里，随时可以下载核对。")}</p> : <ul className="source-list">{items.map(item => <li key={item.source_id}><div><strong>{item.filename}</strong><p className="muted">{item.order_id ? t("已生成订单") : item.extraction_id ? t("已有提取记录，待核对") : t("等待识别")}</p></div><div className="actions"><a href={`/api/v1/sources/${item.source_id}/download`}>{t("下载")}</a>{(canWrite || item.order_id) && <button className="secondary" disabled={busy} onClick={() => void open(item)}>{item.order_id ? t("打开订单") : item.extraction_id ? t("继续核对") : t("开始识别")}</button>}{canWrite && item.extraction_id && !item.order_id && <button className="text-button" disabled={busy} onClick={() => void open(item, true)}>{t("重新识别")}</button>}</div></li>)}</ul>}{cursor && <button className="secondary" disabled={busy} onClick={() => void load(cursor).catch(e => setError(message(e)))}>{t("加载更多")}</button>}</section>
  </section>;
}
