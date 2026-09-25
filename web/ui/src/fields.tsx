export interface Option {
  value: string;
  label: string;
}

export function Field({
  label,
  value,
  onChange,
  numeric,
  hint,
  locked,
  placeholder,
  mono,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  numeric?: boolean;
  hint?: string;
  locked?: string;
  placeholder?: string;
  mono?: boolean;
}) {
  const kind = ["field-input", locked ? "locked" : "", mono ? "mono" : ""];
  return (
    <label className="field">
      {label}
      <span className={kind.filter(Boolean).join(" ")}>
        <input
          value={value}
          placeholder={placeholder}
          readOnly={Boolean(locked)}
          inputMode={numeric ? "numeric" : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
        {locked ? (
          <>
            <span className="field-lock" aria-hidden="true">
              i
            </span>
            <span className="tooltip" role="tooltip">
              {locked}
            </span>
          </>
        ) : null}
      </span>
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function Choice({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const known = options.some((option) => option.value === value);
  return (
    <label className="field">
      {label}
      <span className={disabled ? "field-input locked" : "field-input"}>
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          {known ? null : <option value={value}>{value || "none"}</option>}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <span className="field-chevron" aria-hidden="true">
          &#x25BE;
        </span>
      </span>
    </label>
  );
}
