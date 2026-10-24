import { t } from "../i18n";
type Identity = { description: string; item_code?: string | null; item_name?: string | null; specification?: string | null };

export function ItemIdentity({ line }: { line: Identity }) {
  if (line.item_code == null && line.item_name == null && line.specification == null) return <span className="item-identity">{line.description}</span>;
  return <div className="item-identity">
    {line.item_code && <small>{t("货物编号：{0}", [(line.item_code) ?? ""])}</small>}
    <strong>{line.item_name || t("名称未提供")}</strong>
    {line.specification && <span>{t("规格型号：{0}", [(line.specification) ?? ""])}</span>}
  </div>;
}
