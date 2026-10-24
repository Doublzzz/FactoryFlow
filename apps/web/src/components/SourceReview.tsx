import { t } from "../i18n";
import { useState } from "react";
import type { Extraction } from "../api";

export function SourceReview({ extraction }: { extraction: Extraction }) {
  const [page, setPage] = useState(1);
  const errors: Record<string, string> = { NO_TEXT_FOUND: t("未识别到文字"), OCR_UNAVAILABLE: t("本机 OCR 或识别语言不可用"), OCR_TIMEOUT: t("本页识别超时"), EXTRACTION_TIMEOUT: t("文件处理超时"), FILE_DECODE_FAILED: t("文件无法解析或超过页数/尺寸限制"), EXTRACTION_FAILED: t("本地提取未完成") };
  return <aside className="source-review work-panel" aria-label={t("原件与识别结果")}><div className="row-between work-panel-heading"><h2>{t("原件对照")}</h2><a href={`/api/v1/sources/${extraction.source_id}/download`}>{t("下载原件")}</a></div>
    <p className="warning">{t("识别可能误读或漏行。请逐页核对，补齐明细后再确认。")}</p>
    {extraction.candidate.warnings?.map(warning => <p key={`${warning.code}-${warning.page}`} role="status" className="warning">{t("第{0} 页有区域未能可靠解析，已保留可识别明细。请对照原件检查是否漏行，补齐或修正后再确认。", [(warning.page) ?? ""])}</p>)}
    {extraction.status === "failed" && <p role="status" className="warning">{t("{0}。可按原件手工填写，或返回文件列表重试。", [(errors[extraction.error_code ?? ""] ?? t("提取失败")) ?? ""])}</p>}
    {extraction.pages.length > 0 ? <><label>{t("原件页码")}<select value={page} onChange={e => setPage(Number(e.target.value))}>{extraction.pages.map(p => <option key={p.number} value={p.number}>{t("第{0} 页 / 共{1} 页", [(p.number) ?? "", (extraction.pages.length) ?? ""])}</option>)}</select></label><a href={`/api/v1/extractions/${extraction.extraction_id}/pages/${page}`} target="_blank" rel="noreferrer"><img className="source-page" src={`/api/v1/extractions/${extraction.extraction_id}/pages/${page}`} alt={t("原件第 {0} 页，点击放大", [page])} /></a><details><summary>{t("查看原始识别文字")}</summary><pre>{extraction.pages[page - 1]?.text || t("本页未识别到文字")}</pre></details></> : <p>{t("没有可显示的页面，请下载原件核对。")}</p>}
  </aside>;
}
