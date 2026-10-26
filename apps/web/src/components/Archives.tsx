import { getLocale, outputLanguage, msg, t, type UiMessage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type ArchiveBatch, type ArchivePreview, type ArchivePreviewRequest, type ArchiveRule, type ArchiveSettings, type ArchiveSource } from "../api";
import "./archives.css";

type Kind = ArchiveSource["kind"];
type SourcePage = { items: ArchiveSource[]; cursor: string | null };
type PendingCommand = { kind: "save"; key: string; body: { rule: ArchiveRule; expected_version: number } }
  | { kind: "create"; key: string; body: ArchivePreviewRequest & { preview_token: string } };
const kinds: { value: Kind; label: string }[] = [
  { value: "source", label: "订单原件" }, { value: "delivery", label: "送货单" }, { value: "statement_export", label: "对账 Excel" },
];
const rules: { value: ArchiveRule; label: string; path: string }[] = [
  { value: "date", label: "按日期", path: "年 / 月 / 日 / 文件类型 / 文件" },
  { value: "customer", label: "按客户", path: "客户 / 文件类型 / 文件" },
  { value: "month_customer", label: "月份 → 客户", path: "年 / 月 / 客户 / 文件类型 / 文件" },
];
const ruleName = (rule: ArchiveRule) => t(rules.find(item => item.value === rule)!.label);
const size = (bytes: number | null) => bytes === null ? t("预览时计算") : bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
const dateTime = (value: string) => new Date(value).toLocaleString(getLocale());
const unknown = (item: ArchiveSource) => !item.business_date || !item.customer_id;
const batchState = (batch: ArchiveBatch) => batch.status === "pending" ? t("待生成") : batch.status === "failed" ? t("生成失败") : batch.local_available === false ? t("副本不可用") : t("已生成");
const uncertainFailure = (error: unknown) => !(error instanceof ApiError) || error.status >= 500 || error.status === 408;
const sourceTitle = (item: ArchiveSource) => item.kind === "statement_export" ? t(item.title) : item.title;
function sourceVersion(item: ArchiveSource): string {
  // These are server-owned metadata labels; filenames and frozen paths stay untouched.
  const label = item.version_label;
  if (item.kind === "delivery") {
    const match = /^送货 v(\d+) · 模板 v(\d+)$/.exec(label);
    if (match) return t("送货 v{0} · 模板 v{1}", [match[1], match[2]]);
  } else if (item.kind === "statement_export") {
    const match = /^(正式对账|对账) v(\d+)$/.exec(label);
    if (match) return t("{0} v{1}", [t(match[1]!), match[2]]);
  } else if (label.startsWith("确认版本 ")) return t("确认版本 {0}", [label.slice(5)]);
  return t(label);
}

function FileTable({ items }: { items: ArchivePreview["items"] }) {
  return <div className="table-wrap archive-table" tabIndex={0} aria-label={t("文件路径，可横向滚动")}><table>
    <thead><tr><th>{t("文件 / 生成时版本")}</th><th>{t("归类 / 日期")}</th><th>{t("生成时状态")}</th><th>{t("相对路径")}</th><th className="numeric">{t("文件大小")}</th></tr></thead>
    <tbody>{items.map(item => <tr key={item.key}>
      <td><strong>{sourceTitle(item)}</strong><small>{sourceVersion(item)} · {item.extension.toUpperCase()}</small></td>
      <td>{unknown(item) ? t("待归类") : item.customer_name}<small>{item.business_date ?? t("业务日期未确认")}{item.period_end ? t(" 至 {0}", [item.period_end]) : ""}</small></td>
      <td>{t(item.state_label)}<small>{item.current ? t("预览 / 生成时来源") : t("历史来源快照")}</small></td>
      <td className="archive-path">{item.path}</td><td className="numeric">{size(item.byte_size)}</td>
    </tr>)}</tbody></table></div>;
}

export function Archives({ canWrite, onGuardChange }: { canWrite: boolean; onGuardChange: (blocked: boolean) => void }) {
  const [settings, setSettings] = useState<ArchiveSettings | null>(null);
  const [rule, setRule] = useState<ArchiveRule>("date");
  const [kind, setKind] = useState<Kind>("source");
  const [pages, setPages] = useState<Partial<Record<Kind, SourcePage>>>({});
  const [selections, setSelections] = useState<Record<string, ArchiveSource>>({});
  const [preview, setPreview] = useState<ArchivePreview | null>(null);
  const [previewBody, setPreviewBody] = useState<ArchivePreviewRequest | null>(null);
  const [batches, setBatches] = useState<ArchiveBatch[]>([]);
  const [batchCursor, setBatchCursor] = useState<string | null>(null);
  const [detail, setDetail] = useState<ArchiveBatch | null>(null);
  const [busy, setBusy] = useState(true);
  const [sourceBusy, setSourceBusy] = useState(false);
  const [error, setError] = useState<UiMessage>("");
  const [sourceError, setSourceError] = useState<UiMessage>("");
  const [notice, setNotice] = useState<UiMessage>("");
  const [pending, setPending] = useState<PendingCommand | null>(null);
  const command = useRef<PendingCommand | null>(null);
  const sourceRequest = useRef(0);
  const detailSection = useRef<HTMLElement>(null);
  const locale = getLocale();
  const selected = Object.values(selections);
  const locked = busy || sourceBusy || !!pending;
  const guard = busy || !!pending;
  const page = pages[kind];

  useEffect(() => {
    if (detail) { detailSection.current?.scrollIntoView({ block: "start" }); detailSection.current?.focus({ preventScroll: true }); }
  }, [detail?.id]);

  useEffect(() => {
    onGuardChange(guard);
    return () => onGuardChange(false);
  }, [guard, onGuardChange]);
  useEffect(() => {
    if (!guard) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [guard]);
  useEffect(() => {
    let active = true;
    Promise.all([api.archiveSettings(), api.archives()]).then(([preference, records]) => {
      if (!active) return;
      setSettings(preference); setRule(preference.rule); setBatches(records.items); setBatchCursor(records.next_cursor);
    }).catch(failure => { if (active) setError(message(failure)); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; sourceRequest.current++; };
  }, []);
  useEffect(() => {
    if (!pages[kind]) void loadSources(kind);
    // Cached pages stay selected independently of the active type.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  useEffect(() => { if (!pending) { setPreview(null); setPreviewBody(null); } }, [locale]);
  function invalidate() { setPreview(null); setPreviewBody(null); }
  async function loadSources(target: Kind, more = false) {
    const request = ++sourceRequest.current;
    setSourceBusy(true); setSourceError("");
    try {
      const result = await api.archiveSources(target, more ? pages[target]?.cursor ?? undefined : undefined);
      if (request !== sourceRequest.current) return;
      setPages(old => ({ ...old, [target]: { items: more ? [...(old[target]?.items ?? []), ...result.items] : result.items, cursor: result.next_cursor } }));
    } catch (failure) { if (request === sourceRequest.current) setSourceError(message(failure)); }
    finally { if (request === sourceRequest.current) setSourceBusy(false); }
  }
  function refreshSources() {
    setSelections({}); setPages({}); invalidate();
    setNotice(msg("旧选择和路径预览已清除，请按重新读取的来源再次选择。其他类型尚未重新加载。"));
    void loadSources(kind);
  }
  function toggle(item: ArchiveSource) {
    invalidate(); setNotice("");
    setSelections(old => {
      const next = { ...old };
      if (next[item.key]) delete next[item.key]; else next[item.key] = item;
      return next;
    });
  }
  async function previewPaths() {
    if (!selected.length || locked) return;
    const body: ArchivePreviewRequest = { rule, locale, selections: selected.map(({ key, token }) => ({ key, token })) };
    setBusy(true); setError(""); invalidate();
    try { const result = await api.previewArchive(body); setPreview(result); setPreviewBody(body); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function runCommand(frozen: PendingCommand) {
    command.current = frozen; setPending(frozen); setBusy(true); setError(""); setNotice("");
    try {
      if (frozen.kind === "save") {
        const result = await api.saveArchiveSettings(frozen.body, frozen.key);
        setSettings(result); setNotice(msg("已保存为工厂默认规则，仅用于后续整理；旧批次保持原路径。"));
      } else {
        const result = await api.createArchive(frozen.body, frozen.key);
        setDetail(result); setBatches(old => [result, ...old.filter(item => item.id !== result.id)]);
        invalidate(); setNotice(msg("批次已冻结。请生成本地副本；这不会改变订单、送货或对账记录。"));
      }
      command.current = null; setPending(null);
    } catch (failure) {
      if (uncertainFailure(failure)) {
        setError(msg("{0} 操作结果尚未确认，已保留本次内容。请用同一操作重试确认结果。", [message(failure)]));
      } else {
        command.current = null; setPending(null);
        if (frozen.kind === "create") invalidate();
        setError(msg("{0}{1}", [message(failure), frozen.kind === "create" ? msg(" 请重新读取来源并预览。") : msg(" 可重新读取默认规则后再保存。")]));
      }
    } finally { setBusy(false); }
  }
  async function reloadSettings() {
    setBusy(true); setError("");
    try { const result = await api.archiveSettings(); setSettings(result); setRule(result.rule); invalidate(); }
    catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  async function loadBatches(more = false) {
    setBusy(true); setError("");
    try {
      const result = await api.archives(more ? batchCursor ?? undefined : undefined);
      setBatches(old => more ? [...old, ...result.items] : result.items); setBatchCursor(result.next_cursor);
      if (detail) setDetail(await api.archive(detail.id));
    } catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  async function openBatch(id: string) {
    setBusy(true); setError("");
    try { setDetail(await api.archive(id)); }
    catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  async function generate() {
    if (!detail || !canWrite || !settings?.root_configured || locked) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.generateArchive(detail.id);
      setDetail(result); setBatches(old => old.map(item => item.id === result.id ? result : item));
      setNotice(result.status === "ready" && result.local_available !== false ? msg("本地工作文件已生成。离线文件永久保留生成时状态。") : msg("本地文件生成未完成，请查看批次状态后重试同一批次。"));
    } catch (failure) {
      setError(msg("{0} 请刷新此批次状态；重试始终使用同一批次。", [message(failure)]));
      try { setDetail(await api.archive(detail.id)); } catch { /* Keep the known frozen batch identity. */ }
    } finally { setBusy(false); }
  }
  async function download() {
    if (!detail || locked) return;
    setBusy(true); setError("");
    try { await api.downloadArchive(detail); }
    catch (failure) { setError(msg("{0} 请刷新批次，核对当前性和本地副本后重试。", [message(failure)])); }
    finally { setBusy(false); }
  }

  return <section className="archives-page work-page">
    <div className="page-heading"><div><h1>{t("文件整理")}</h1><p>{t("选择订单原件、送货单和对账 Excel，预览分类路径，再生成一批工作文件。")}</p></div></div>
    <nav className="work-section-nav" aria-label={t("文件整理区域")}><a href="#archive-rule">{t("整理规则")}</a><a href="#archive-files">{t("选择文件")}</a><a href="#archive-records">{t("整理记录")}</a></nav>
    <p className="archive-disclosure">{t("工作文件保存生成时的版本与状态。离线副本不会随业务变化更新，也不替代正式结算或正式归档。")}</p>
    <p className="muted">{t("新送货副本和分类路径使用预览时的语言；原件、旧导出和自定义版式文字保持原文。")}</p>
    {!canWrite && <p className="warning">{t("当前账号可查看、预览和下载，不能保存规则或生成文件。")}</p>}
    {settings && !settings.root_configured && <p role="status" className="warning">{t("本机未配置工作归档目录，暂不能创建批次或生成副本。请由本机管理员配置；仍可预览分类路径和查看记录。")}</p>}
    {error && <p role="alert" className="error">{t(error)}</p>}
    {notice && <p role="status" className="archive-notice">{t(notice)}</p>}
    {pending && <div className="warning"><p>{t("本次{0}结果待确认。内容和操作身份已冻结，确认前不能改选文件或切换规则。", [(pending.kind === "save" ? t("规则保存") : t("批次创建")) ?? ""])}</p><button disabled={busy} onClick={() => { if (command.current) void runCommand(command.current); }}>{t("重试同一操作")}</button></div>}
    {busy && <p role="status">{t("正在处理，请稍候…")}</p>}
    <section id="archive-rule" className="work-panel" tabIndex={-1} aria-labelledby="archive-rule-heading"><div className="archive-rule-heading work-panel-heading"><h2 id="archive-rule-heading">{t("本次整理规则")}</h2>{settings && <span className="muted">{t("工厂默认：{0} · v{1}", [(ruleName(settings.rule)) ?? "", (settings.version) ?? ""])}</span>}</div>
    <fieldset className="archive-rules" disabled={locked}><legend className="sr-only">{t("选择分类规则")}</legend>{rules.map(item => <label key={item.value} className={rule === item.value ? "archive-rule selected" : "archive-rule"}>
      <input type="radio" name="archive-rule" value={item.value} checked={rule === item.value} onChange={() => { setRule(item.value); invalidate(); setNotice(""); }} /><span><strong>{t(item.label)}</strong><small>{t(item.path)}</small></span>
    </label>)}</fieldset>
    <div className="actions archive-rule-actions">
      {canWrite && <button className="secondary" disabled={locked || !settings || settings.rule === rule} onClick={() => { if (settings) void runCommand({ kind: "save", key: crypto.randomUUID(), body: { rule, expected_version: settings.version } }); }}>{t("保存为工厂默认")}</button>}
      <button className="text-button" disabled={locked} onClick={() => void reloadSettings()}>{t("重新读取默认规则")}</button><span className="muted">{t("默认规则只影响后续整理，不改写旧批次。")}</span>
    </div>
    </section>
    <section id="archive-files" className="work-panel" tabIndex={-1} aria-labelledby="archive-files-heading"><div className="archive-rule-heading work-panel-heading"><h2 id="archive-files-heading">{t("选择文件")}</h2><span className="muted">{t("跨类型共选{0} / 50 份", [(selected.length) ?? ""])}</span></div>
    <div className="list-toolbar"><div className="tabs" role="group" aria-label={t("文件类型")}>{kinds.map(item => <button key={item.value} className={kind === item.value ? "selected" : ""} aria-pressed={kind === item.value} disabled={locked} onClick={() => setKind(item.value)}>{t(item.label)}</button>)}</div>
      <button className="secondary" disabled={locked} onClick={refreshSources}>{t("刷新来源并清除选择")}</button></div>
    {sourceBusy && <p role="status">{t("正在读取文件来源…")}</p>}
    {sourceError && <p role="alert" className="error">{t(sourceError)} <button className="text-button" disabled={locked} onClick={() => void loadSources(kind)}>{t("重试读取来源")}</button></p>}
    {page && !page.items.length && !sourceBusy && <p className="empty-state">{t("当前类型还没有可整理的文件。手工订单不会自动产生原件；对账 Excel 须先在对账页生成。")}</p>}
    {!!page?.items.length && <div className="table-wrap archive-table" tabIndex={0} aria-label={t("文件来源，可横向滚动")}><table><thead><tr><th>{t("选择")}</th><th>{t("文件 / 类型")}</th><th>{t("归类 / 业务日期")}</th><th>{t("状态 / 版本")}</th><th className="numeric">{t("大小")}</th></tr></thead><tbody>{page.items.map(item => <tr key={item.key}>
      <td><input className="archive-checkbox" type="checkbox" aria-label={t("选择 {0}", [sourceTitle(item)])} checked={!!selections[item.key]} disabled={locked || !item.available || (!selections[item.key] && selected.length >= 50)} onChange={() => toggle(item)} /></td>
      <td><strong>{sourceTitle(item)}</strong><small>{item.extension.toUpperCase()}{item.kind === "delivery" ? t(" · 离线 HTML 工作文件") : ""}</small></td>
      <td>{unknown(item) ? <span className="archive-badge">{t("待归类")}</span> : item.customer_name}<small>{item.business_date ?? t("业务日期未确认")}{item.period_end ? t(" 至 {0}", [item.period_end]) : ""}</small></td>
      <td>{!item.available ? t("文件未生成，不能选择") : t(item.state_label)}<small>{sourceVersion(item)} · {!item.current ? t("历史来源快照") : t("读取时来源")}</small></td><td className="numeric">{size(item.byte_size)}</td>
    </tr>)}</tbody></table></div>}
    {page && <div className="archive-page-footer"><span className="muted">{t("本类型已加载{0} 份{1}。其他类型需分别查看。", [(page.items.length) ?? "", (page.cursor ? t("，还有更多未加载") : t("；当前分页已读完")) ?? ""])}</span>{page.cursor && <button className="secondary" disabled={locked} onClick={() => void loadSources(kind, true)}>{t("加载更多文件")}</button>}</div>}
    {!!selected.length && <div className="archive-selection"><strong>{t("已选文件")}</strong><ul>{selected.map(item => <li key={item.key}><span>{sourceTitle(item)}{!item.current ? t(" · 历史快照") : ""}</span><button className="text-button" disabled={locked} aria-label={t("移除 {0}", [sourceTitle(item)])} onClick={() => toggle(item)}>{t("移除")}</button></li>)}</ul></div>}
    <div className="actions archive-preview-actions"><button disabled={locked || !selected.length} onClick={() => void previewPaths()}>{t("预览分类路径")}</button><span className="muted">{t("最多 50 份、50 MiB；仅统计文件，不汇总业务数量或金额。")}</span></div>
    </section>
    {preview && <section className="archive-preview work-panel"><div className="archive-rule-heading work-panel-heading"><h2>{t("路径预览 ·{0}", [(ruleName(rule)) ?? ""])}</h2><span>{t("{0} 份 ·{1}", [(preview.items.length) ?? "", (size(preview.total_bytes)) ?? ""])}</span></div><p className="muted">{t("输出语言：{0}", [outputLanguage(previewBody?.locale ?? "zh-CN")])}</p><FileTable items={preview.items} />
      {preview.items.some(item => !item.current) && <p className="warning">{t("本批包含历史来源；生成的工作文件会保留历史标识。")}</p>}
      <p className="muted">{t("来源或规则变化后须重新预览；创建时会再次校验来源版本。")}</p>
      {canWrite && <button disabled={locked || !settings?.root_configured || !previewBody} onClick={() => { if (previewBody) void runCommand({ kind: "create", key: crypto.randomUUID(), body: { ...previewBody, preview_token: preview.preview_token } }); }}>{t("确认预览并创建批次")}</button>}
    </section>}
    <section id="archive-records" tabIndex={-1} className="archive-records work-panel"><div className="archive-rule-heading work-panel-heading"><h2>{t("整理记录")}</h2><button className="secondary" disabled={locked} onClick={() => void loadBatches()}>{t("刷新记录与当前状态")}</button></div>
      {!batches.length && !busy && <p className="empty-state">{t("还没有整理批次。先选文件并预览路径。")}</p>}
      {!!batches.length && <div className="table-wrap archive-table" tabIndex={0} aria-label={t("整理批次，可横向滚动")}><table><thead><tr><th>{t("创建时间 / 批次")}</th><th>{t("规则")}</th><th>{t("文件")}</th><th>{t("生成状态")}</th><th>{t("当前性")}</th><th>{t("操作")}</th></tr></thead><tbody>{batches.map(item => <tr key={item.id}>
        <td>{dateTime(item.created_at)}<small className="archive-path">{item.id}</small></td><td>{ruleName(item.rule)}</td><td>{t("{0} 份 ·{1}", [(item.items.length) ?? "", (size(item.total_bytes)) ?? ""])}</td><td>{batchState(item)}</td><td>{item.current ? t("来源仍匹配") : t("历史批次")}</td><td><button className="text-button" disabled={locked} onClick={() => void openBatch(item.id)}>{t("查看批次")}</button></td>
      </tr>)}</tbody></table></div>}
      {batchCursor && <div className="archive-page-footer"><span className="muted">{t("还有未加载的整理记录。")}</span><button className="secondary" disabled={locked} onClick={() => void loadBatches(true)}>{t("加载更多整理记录")}</button></div>}
    </section>
    {detail && <section ref={detailSection} tabIndex={-1} className="archive-detail work-panel" aria-label={t("批次详情")}><div className="archive-rule-heading work-panel-heading"><h2>{t("批次详情 ·{0}", [(batchState(detail)) ?? ""])}</h2><button className="text-button" disabled={locked} onClick={() => setDetail(null)}>{t("收起详情")}</button></div>
      <dl className="archive-facts"><div><dt>{t("批次")}</dt><dd>{detail.id}</dd></div><div><dt>{t("创建时间")}</dt><dd>{t("{0}（不代表当前业务状态）", [(dateTime(detail.created_at)) ?? ""])}</dd></div><div><dt>{t("整理规则")}</dt><dd>{ruleName(detail.rule)}</dd></div><div><dt>{t("相对目录")}</dt><dd>{detail.relative_directory}</dd></div><div><dt>{t("当前性")}</dt><dd>{detail.current ? t("刚读取时来源仍匹配") : t("历史快照：来源已有变化")}</dd></div><div><dt>{t("本地副本")}</dt><dd>{detail.local_available === true ? t("刚读取时可用") : detail.local_available === false ? t("不可用，须核对或重建") : t("尚未核验")}</dd></div></dl>
      {(detail.error_code || detail.local_error) && <p className="warning">{t("本地文件未完成或校验失败：{0}。重试同一批次；已有文件冲突时不会覆盖。", [(detail.local_error ?? detail.error_code) ?? ""])}</p>}
      <p className="archive-disclosure">{t("以下路径、版本与状态来自此批次不可变快照。上方当前性在打开 / 刷新时重新读取；已下载文件不会实时更新。")}</p><FileTable items={detail.items} />
      <div className="actions archive-detail-actions"><button className="secondary" disabled={locked} onClick={() => void openBatch(detail.id)}>{t("刷新此批次状态")}</button>
        {canWrite && (detail.status !== "ready" || detail.local_available === false) && <button disabled={locked || !settings?.root_configured} onClick={() => void generate()}>{detail.status === "pending" ? t("生成本地工作文件") : detail.status === "ready" ? t("重建同一批次副本") : t("重试同一批次")}</button>}
        {detail.status === "ready" && <button disabled={locked} onClick={() => void download()}>{detail.current ? t("下载工作文件 ZIP") : t("下载历史 ZIP")}</button>}
      </div>
    </section>}
  </section>;
}
