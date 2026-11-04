import { msg, t, type UiMessage } from "../i18n";
import { useEffect, useId, useState, type DragEvent } from "react";

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MiB` : `${Math.max(1, Math.round(bytes / 1024))} KiB`;
}

function PickedFile({ file }: { file: File }) {
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file.type.startsWith("image/")) return;
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <li className="file-picked">{preview && <img src={preview} alt="" />}<div><strong>{file.name}</strong><span>{size(file.size)}</span></div></li>;
}

/** File selection only. Each sales file remains an independent order source. */
export function FileDrop({ files, disabled, purpose = "order", maxFiles = 1, onFiles }: {
  files: File[]; disabled?: boolean; purpose?: "order" | "purchase"; maxFiles?: number; onFiles: (files: File[]) => void;
}) {
  const id = useId();
  const [over, setOver] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const accept = purpose === "purchase" ? ".png,.jpg,.jpeg,.pdf,.xlsx" : ".png,.jpg,.jpeg,.pdf";
  function pick(next: File[]) {
    if (!next.length) return;
    if (next.length > maxFiles) { setError(msg("一次最多选择{0}份文件，请重新选择。", [maxFiles])); return; }
    for (const file of next) {
      const sheet = purpose === "purchase" && /\.xlsx$/i.test(file.name);
      if (!sheet && !["image/png", "image/jpeg", "application/pdf"].includes(file.type)) {
        setError(purpose === "purchase" ? msg("请选择PNG、JPEG、PDF或.xlsx采购单。") : msg("只能用 PNG、JPEG 图片或 PDF 文件。")); return;
      }
      const limit = sheet ? 2 : 10;
      if (file.size > limit * 1024 * 1024) { setError(msg("{0}超过{1} MiB，请缩小或拆分后上传。", [file.name, limit])); return; }
    }
    setError(""); onFiles(next);
  }
  function drop(event: DragEvent) {
    event.preventDefault(); setOver(false);
    if (!disabled) pick(Array.from(event.dataTransfer.files));
  }
  return <div className="file-selection">
    {files.length > 0 && <ul className="picked-files">{files.map((file, index) => <PickedFile key={file.name + ":" + file.lastModified + ":" + index} file={file} />)}</ul>}
    <label htmlFor={id} className={"file-drop" + (over ? " is-over" : "") + (files.length ? " is-compact" : "") + (disabled ? " is-disabled" : "")}
      onDragOver={event => { event.preventDefault(); if (!disabled) setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}>
      <input id={id} className="sr-only" type="file" accept={accept} multiple={maxFiles > 1} disabled={disabled} onChange={event => { pick(Array.from(event.target.files ?? [])); event.target.value = ""; }} />
      <span className="file-drop-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
      <strong>{purpose === "purchase" ? t("把采购单拖到这里") : t("把客户的订单拖到这里")}</strong>
      <span>{purpose === "purchase" ? t("图片/PDF不超过10MB；Excel为.xlsx，不超过2MB、一个内容工作表。") : t("一次最多5份独立订单；每份图片/PDF最多10 MiB，单个PDF最多5页。")}</span>
      <span className="file-drop-button">{files.length ? t("重新选择文件") : t("选择文件")}</span>
    </label>
    {error && <p className="file-drop-error" role="alert">{t(error)}</p>}
  </div>;
}
