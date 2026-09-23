import { useState } from "react";

import { api, type AgentInbound } from "../api";
import { Choice, Field } from "../fields";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";

const FLOWS = [
  { value: "xtls-rprx-vision", label: "xtls-rprx-vision" },
  { value: "", label: "none" },
];
const FINGERPRINTS = [
  "chrome",
  "firefox",
  "safari",
  "ios",
  "android",
  "edge",
  "360",
  "qq",
  "random",
  "randomized",
].map((value) => ({ value, label: value }));

export function InboundForm({
  item,
  agent,
  onSaved,
  onClose,
}: {
  item: AgentInbound;
  agent: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [enabled, setEnabled] = useState(item.enabled);
  const [endpointHost, setEndpointHost] = useState(item.endpoint_host ?? "");
  const [flow, setFlow] = useState(item.flow ?? "");
  const [fingerprint, setFingerprint] = useState(item.fingerprint ?? "");
  const [shortId, setShortId] = useState(item.short_id ?? "");
  const [label, setLabel] = useState(item.label ?? "");
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
      await api.updateInbound(item.id, {
        enabled,
        endpoint_host: endpointHost,
        flow: flow || null,
        fingerprint: fingerprint || null,
        short_id: shortId || null,
        label,
      });
      onSaved();
    } catch (error) {
      setProblem(describe(error, "Could not save the inbound"));
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  const transport = [item.protocol, item.network, item.security].join(" \u00b7 ");

  return (
    <div className="scrim">
      <form className="modal" onSubmit={ask}>
        <div className="modal-header">
          <div className="modal-heading">
            <h2>Configure {item.tag}</h2>
            <p>
              {agent} &middot; {transport} &middot; port {item.port || "-"} &middot; discovered
              from the agent
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
            <span className="check-hint">Profiles can be issued on this inbound</span>
          </span>
        </label>

        <div className="field-row">
          <Field
            label="Server names"
            value={item.server_names.join(", ")}
            onChange={() => undefined}
            locked={`Read from config.json on ${agent}. Change serverNames in the Xray config on the host.`}
          />
          <Field
            label="Public key"
            value={item.public_key ?? ""}
            onChange={() => undefined}
            locked={`Derived on the host from the Reality private key, which never leaves ${agent}.`}
          />
        </div>
        <Field label="Endpoint host" value={endpointHost} onChange={setEndpointHost} />
        <div className="field-row">
          <Choice label="Flow" value={flow} options={FLOWS} onChange={setFlow} />
          <Choice
            label="Fingerprint"
            value={fingerprint}
            options={FINGERPRINTS}
            onChange={setFingerprint}
          />
        </div>
        <div className="field-row">
          <Choice
            label="Short id"
            value={shortId}
            options={item.short_ids.map((value) => ({ value, label: value }))}
            onChange={setShortId}
          />
          <Field label="Label" value={label} onChange={setLabel} />
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
                  Save inbound {item.tag} on {agent}
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
