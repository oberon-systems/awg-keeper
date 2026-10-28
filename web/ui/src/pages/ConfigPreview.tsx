import { useState } from "react";

import type { ConfigChange, ConfigPreview } from "../api";
import type { Problem } from "../problem";
import { Banner } from "../tiles";

const LABELS: Record<string, string> = {
  dns: "DNS",
  mtu: "MTU",
  client_allowed_ips: "Client allowed IPs",
  keepalive: "Keepalive",
  endpoint_host: "Endpoint host",
};

export function fieldLabel(field: string): string {
  return LABELS[field] ?? field;
}

function Value({ value, strong }: { value: string | number | null; strong?: boolean }) {
  if (value === null) {
    return <span className="diff-unset">not set</span>;
  }
  const text = String(value);
  const mono = text.length > 12 || text.startsWith("<");
  const kind = [mono ? "key diff-long" : "", strong ? "diff-after" : ""];
  return (
    <span className={kind.filter(Boolean).join(" ")} title={mono ? text : undefined}>
      {text}
    </span>
  );
}

function Impact({ count, label, tone }: { count: number; label: string; tone: string }) {
  return (
    <div className={`impact impact-${count ? tone : "idle"}`}>
      <span className="impact-count">{count}</span>
      <span className="impact-label">{label}</span>
    </div>
  );
}

function Row({ change, blocked }: { change: ConfigChange; blocked: boolean }) {
  const kind = blocked ? "diff-blocked" : change.changed ? "diff-changed" : undefined;
  return (
    <tr className={kind}>
      <td className="cell-name">
        {fieldLabel(change.field)}
        {blocked ? <div className="muted problem">awg cannot unset it</div> : null}
      </td>
      <td>
        <Value value={change.before} />
      </td>
      <td>
        <Value value={change.after} strong={change.changed} />
      </td>
    </tr>
  );
}

export function PreviewDialog({
  title,
  subtitle,
  preview,
  problem,
  busy,
  applyLabel,
  cancelLabel = "Cancel",
  onApply,
  onCancel,
}: {
  title: string;
  subtitle: string;
  preview: ConfigPreview | null;
  problem: Problem | null;
  busy: boolean;
  applyLabel: string;
  cancelLabel?: string;
  onApply: () => void;
  onCancel: () => void;
}) {
  const [unchangedShown, setUnchangedShown] = useState(false);
  const [detailShown, setDetailShown] = useState(false);
  const changes = preview?.changes ?? [];
  const blocked = preview?.blocked ?? [];
  const changed = changes.filter((item) => item.changed || blocked.includes(item.field));
  const unchanged = changes.filter((item) => !changed.includes(item));

  return (
    <div className="scrim">
      <div className="modal wide" role="alertdialog" aria-modal="true">
        <div className="modal-header">
          <div className="modal-heading">
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onCancel}>
            &#x2715;
          </button>
        </div>

        {blocked.length ? (
          <div className="problem-banner" role="alert">
            <div className="problem-banner-summary">
              <span>This cannot be applied: awg cannot unset {blocked.join(" and ")}.</span>
            </div>
            <p className="problem-banner-detail">
              The interface has them and this config has none. Restart the interface from a
              file without them, or pick a config that sets them.
            </p>
          </div>
        ) : null}

        {preview ? (
          <>
            <div className="impacts">
              <Impact
                count={preview.current}
                label="profiles match their issued config"
                tone="ok"
              />
              <Impact count={preview.stale} label="profiles need a reroll" tone="warn" />
            </div>

            <section className="section-caps">
              <h3>
                Changes <span className="section-count">
                  {changed.length} of {changes.length}
                </span>
              </h3>
              <div className="diff">
                <table>
                  <thead>
                    <tr>
                      <th>Parameter</th>
                      <th>Now</th>
                      <th>After</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changed.map((change) => (
                      <Row
                        key={change.field}
                        change={change}
                        blocked={blocked.includes(change.field)}
                      />
                    ))}
                    {unchangedShown
                      ? unchanged.map((change) => (
                          <Row key={change.field} change={change} blocked={false} />
                        ))
                      : null}
                    {unchanged.length ? (
                      <tr>
                        <td colSpan={3}>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => setUnchangedShown((shown) => !shown)}
                          >
                            {unchangedShown
                              ? "\u25BE  Hide unchanged"
                              : `\u25B8  Show ${unchanged.length} unchanged`}
                          </button>
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : problem ? null : (
          <p className="modal-text">Working out what changes&hellip;</p>
        )}

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((shown) => !shown)}
        />

        <div className="modal-footer">
          <button type="button" className="secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className="action wide"
            disabled={busy || !preview || blocked.length > 0}
            onClick={onApply}
          >
            {applyLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
