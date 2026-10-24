import { t } from "../i18n";
import { useEffect, useId, useState, type DragEvent } from "react";

const accepted = ["image/png", "image/jpeg", "application/pdf"];

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MiB` : `${Math.max(1, Math.round(bytes / 1024))} KiB`;
}

/** A large drop area for a customer's order. The real file input stays inside for keyboard and screen readers. */
export function FileDrop({ file, disabled, compact, onFile }: { file: File | null; disabled?: boolean; compact?: boolean; onFile: (file: File | null) => void }) {
  const id = useId();
  const [over, setOver] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) { setPreview(null); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function pick(next: File | undefined) {
    if (!next) return;
    if (!accepted.includes(next.type)) { setRejected(true); return; }
    setRejected(false); onFile(next);
  }
  function drop(event: DragEvent) {
    event.preventDefault(); setOver(false);
    if (!disabled) pick(event.dataTransfer.files[0]);
  }

  if (file) return <div className="file-picked">
    {preview ? <img src={preview} alt={t("所选订单的预览")} /> : <span className="file-picked-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M6 3h8l4 4v14H6zM14 3v4h4M9 13h6M9 17h4" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" /></svg></span>}
    <div><strong>{file.name}</strong><span>{size(file.size)}</span></div>
    <button type="button" className="text-button" disabled={disabled} onClick={() => onFile(null)}>{t("换一个文件")}</button>
  </div>;

  return <label htmlFor={id} className={`file-drop${over ? " is-over" : ""}${compact ? " is-compact" : ""}${disabled ? " is-disabled" : ""}`}
    onDragOver={event => { event.preventDefault(); if (!disabled) setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
    <input id={id} className="sr-only" type="file" accept={accepted.join(",")} disabled={disabled} onChange={event => { pick(event.target.files?.[0]); event.target.value = ""; }} />
    <span className="file-drop-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
    <strong>{t("把客户的订单拖到这里")}</strong>
    <span>{t("照片、截图或 PDF 都可以，最多 10 MiB、5 页")}</span>
    <span className="file-drop-button">{t("选择文件")}</span>
    {rejected && <span className="file-drop-error" role="alert">{t("只能用 PNG、JPEG 图片或 PDF 文件。")}</span>}
  </label>;
}
