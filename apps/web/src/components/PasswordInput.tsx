import { useEffect, useId, useState } from "react";
import { t } from "../i18n";

export function PasswordInput({ value, onChange, disabled }: { value: string; onChange: (value: string) => void; disabled: boolean }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  useEffect(() => { if (!value) setVisible(false); }, [value]);

  return <div className="password-field">
    <label htmlFor={id}>{t("密码")}</label>
    <div className="password-input-row">
      <input id={id} type={visible ? "text" : "password"} value={value} onChange={event => onChange(event.target.value)} autoComplete="current-password" required maxLength={128} disabled={disabled} />
      <button type="button" className="password-toggle" aria-controls={id} aria-pressed={visible} aria-label={t(visible ? "隐藏密码" : "显示密码")} disabled={disabled} onClick={() => setVisible(previous => !previous)}>{visible ? t("隐藏") : t("显示")}</button>
    </div>
  </div>;
}
