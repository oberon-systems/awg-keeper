import { useState } from "react";

import { api, type AgentInterface } from "../api";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";

function text(value: string | number | null): string {
  return value === null ? "" : String(value);
}

function number(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function Field({
  label,
  value,
  onChange,
  numeric,
  hint,
  locked,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  numeric?: boolean;
  hint?: string;
  locked?: string;
}) {
  return (
    <label className="field">
      {label}
      <span className={locked ? "field-input locked" : "field-input"}>
        <input
          value={value}
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

export function InterfaceForm({
  item,
  agent,
  onSaved,
  onClose,
}: {
  item: AgentInterface;
  agent: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const host = item.address ? item.address.split("/")[0] : null;
  const [enabled, setEnabled] = useState(item.enabled);
  const [endpointHost, setEndpointHost] = useState(text(item.endpoint_host));
  const [dns, setDns] = useState(text(item.dns ?? host));
  const [mtu, setMtu] = useState(text(item.mtu));
  const [allowed, setAllowed] = useState(text(item.client_allowed_ips ?? "0.0.0.0/0"));
  const [keepalive, setKeepalive] = useState(text(item.keepalive));
  const [confirming, setConfirming] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  function ask(event: React.FormEvent) {
    event.preventDefault();
    setConfirming(true);
  }

  async function save() {
    if (item.id === null) {
      return;
    }
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    try {
      await api.updateInterface(item.id, {
        enabled,
        endpoint_host: endpointHost,
        dns,
        mtu: number(mtu),
        client_allowed_ips: allowed,
        keepalive: number(keepalive),
      });
      onSaved();
    } catch (error) {
      setProblem(describe(error, "Could not save the interface"));
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <div className="scrim">
      <form className="modal" onSubmit={ask}>
        <div className="modal-header">
          <div className="modal-heading">
            <h2>Configure {item.name}</h2>
            <p>
              {agent} &middot; port {item.listen_port || "-"} &middot; discovered from the agent
            </p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <label className="check">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <span>
            <span className="check-title">Enabled</span>
            <span className="check-hint">Profiles can be issued on this interface</span>
          </span>
        </label>

        <div className="field-row">
          <Field
            label="Address"
            value={text(item.address)}
            onChange={() => undefined}
            locked={`Read from ${item.name} on the host. The agent reports it on every healthcheck, so change it in the interface config on ${agent}.`}
          />
          <Field
            label="Pool"
            value={text(item.pool)}
            onChange={() => undefined}
            locked={`Derived from the interface address: peers on ${item.name} get addresses from this network.`}
          />
        </div>
        <Field label="Endpoint host" value={endpointHost} onChange={setEndpointHost} />
        <div className="field-row">
          <Field
            label="DNS"
            value={dns}
            onChange={setDns}
            hint="Defaults to the interface address"
          />
          <Field label="MTU" value={mtu} onChange={setMtu} numeric />
        </div>
        <div className="field-row">
          <Field label="Client allowed IPs" value={allowed} onChange={setAllowed} />
          <Field label="Keepalive" value={keepalive} onChange={setKeepalive} numeric />
        </div>

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((shown) => !shown)}
        />

        <div className="modal-footer">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="action">
            Save
          </button>
        </div>
      </form>

      {confirming ? (
        <div className="scrim">
          <div className="modal narrow" role="alertdialog" aria-modal="true">
            <div className="modal-header">
              <div className="modal-heading">
                <h2>Are you sure?</h2>
                <p>
                  Save interface {item.name} on {agent}
                </p>
              </div>
              <button
                type="button"
                className="modal-close"
                aria-label="Close"
                onClick={() => setConfirming(false)}
              >
                &#x2715;
              </button>
            </div>
            <div className="modal-footer">
              <button type="button" className="secondary" onClick={() => setConfirming(false)}>
                No
              </button>
              <button
                type="button"
                className="action wide"
                disabled={busy}
                onClick={() => void save()}
              >
                Yes
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
