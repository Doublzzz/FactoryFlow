import { t, type UiMessage } from "../i18n";
import { useEffect, useState } from "react";
import { api, message, type Schemas } from "../api";
import { ItemIdentity } from "./ItemIdentity";

type Kind = "approvals" | "reviews";
type Row = Schemas["StatementApproval"] | Schemas["StatementReview"];
type Page = { items: Row[]; next_cursor: string | null };
const positive = (quantity: string) => /^\d+(?:\.\d+)?$/.test(quantity) && /[1-9]/.test(quantity);
const pending = (row: Row) => "available_quantity" in row
  ? positive(row.available_quantity) || positive(row.reserved_quantity)
  : positive(row.remaining_quantity);

export function StatementFollowUp({ customerId, disabled, onOpen }: {
  customerId: string; disabled: boolean; onOpen: (statementId: string) => void;
}) {
  const [kind, setKind] = useState<Kind>("approvals");
  const [cursor, setCursor] = useState<string | undefined>();
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<UiMessage>("");

  useEffect(() => {
    let active = true;
    setBusy(true); setError("");
    if (!cursor) setPage(null);
    const read = kind === "approvals" ? api.statementApprovals : api.statementReviews;
    read(customerId, cursor).then(result => {
      if (active) setPage(previous => ({
        items: cursor ? [...(previous?.items ?? []), ...result.items] : result.items,
        next_cursor: result.next_cursor,
      }));
    }).catch(failure => { if (active) setError(message(failure)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [customerId, kind, cursor, attempt]);

  function choose(next: Kind) {
    if (next === kind) return;
    setPage(null); setError(""); setBusy(true); setCursor(undefined); setKind(next);
  }
  const rows = page?.items.filter(pending) ?? [];
  const label = kind === "approvals" ? t("认可") : t("待核对");

  return <section className="work-panel statement-follow-up" aria-label={t("待结与待核对")}>
    <div className="work-panel-heading"><h2>{t("待结与待核对")}</h2>
      <button type="button" className="secondary" disabled={busy || disabled}
        onClick={() => { setCursor(undefined); setAttempt(value => value + 1); }}>{t("刷新待处理事项")}</button>
    </div>
    <p className="muted">{t("按客户查看跨期余量，不受上方新建草稿期间限制。处理余量时，进入目标期间草稿的「认可与结算」。")}</p>
    <div className="tabs follow-up-tabs" role="group" aria-label={t("待处理类别")}>
      <button type="button" className={kind === "approvals" ? "selected" : ""} aria-pressed={kind === "approvals"} onClick={() => choose("approvals")}>{t("已认可待结")}</button>
      <button type="button" className={kind === "reviews" ? "selected" : ""} aria-pressed={kind === "reviews"} onClick={() => choose("reviews")}>{t("待核对")}</button>
    </div>
    {error && <p role="alert" className="error">{t("读取{0}记录失败：{1}", [(label) ?? "", (t(error)) ?? ""])}<button type="button" className="text-button" disabled={busy} onClick={() => setAttempt(value => value + 1)}>{t("重试读取{0}记录", [(label) ?? ""])}</button>
    </p>}
    {busy && <p role="status">{t("正在读取{0}记录…", [(label) ?? ""])}</p>}
    {!!rows.length && <div className="table-wrap" tabIndex={0} role="region" aria-label={t("{0}待处理明细，可横向滚动", [label])}>
      <table><thead><tr><th>{t("来源明细")}</th><th>{kind === "approvals" ? t("认可后的结算余量") : t("待核对数量")}</th><th>{t("期间与原因")}</th><th>{t("操作")}</th></tr></thead>
        <tbody>{rows.map(row => {
          const unit = row.source.canonical_unit ?? row.source.source_unit ?? t("单位未提供");
          return <tr key={row.id}>
            <td><ItemIdentity line={row.source} /><small>{t("原送货日期：{0}", [(row.source.delivery_date) ?? ""])}</small></td>
            <td>{"available_quantity" in row ? <>
              <strong className="remaining">{t("待选{0} {1}", [(row.available_quantity) ?? "", (unit) ?? ""])}</strong>
              <small>{t("已选待正式结算：{0} {1}", [(row.reserved_quantity) ?? "", (unit) ?? ""])}</small>
              <small>{t("已正式结算：{0} {1}", [(row.settled_quantity) ?? "", (unit) ?? ""])}</small>
              <small>{t("认可单价：{0} {1} / {2}", [row.unit_price, row.source.currency, unit])}</small>
            </> : <strong className="remaining">{row.remaining_quantity} {unit}</strong>}</td>
            <td>{"target_start" in row && <p className="follow-up-period">{t("{0} 至{1}", [(row.target_start) ?? "", (row.target_end) ?? ""])}</p>}
              <span>{row.reason || t("未填写原因")}</span></td>
            <td><button type="button" className="text-button" disabled={busy || disabled} onClick={() => onOpen(row.statement_id)}>{t("查看来源对账单")}</button></td>
          </tr>;
        })}</tbody>
      </table>
    </div>}
    {page && !busy && !error && !rows.length && <p className="empty-state">{page.next_cursor
      ? t("已加载记录中暂无待处理的{0}事项，后面仍有记录，请继续加载。", [label])
      : kind === "approvals" ? t("该客户暂无已认可未结算的余量。") : t("该客户暂无剩余待核对事项。")}</p>}
    {page && <div className="follow-up-pagination">
      <p className="muted">{t("已读取{0} 条{1}记录，显示其中{2} 条待处理事项。{3}", [(page.items.length) ?? "", (label) ?? "", (rows.length) ?? "", (page.next_cursor ? t("仍有记录未读取。") : t("已读取全部记录。")) ?? ""])}</p>
      {page.next_cursor && <button type="button" className="secondary" disabled={busy || disabled || !!error} onClick={() => setCursor(page.next_cursor ?? undefined)}>{t("加载更多{0}记录", [(label) ?? ""])}</button>}
    </div>}
  </section>;
}
