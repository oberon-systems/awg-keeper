import { useState } from "react";

import { api, type AgentInterface } from "../api";

function text(value: string | number | null): string {
  return value === null ? "" : String(value);
}

function number(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

export function InterfaceForm({
  item,
  onSaved,
  onClose,
}: {
  item: AgentInterface;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [enabled, setEnabled] = useState(item.enabled);
  const [address, setAddress] = useState(text(item.address));
  const [pool, setPool] = useState(text(item.pool));
  const [endpointHost, setEndpointHost] = useState(text(item.endpoint_host));
  const [dns, setDns] = useState(text(item.dns));
  const [mtu, setMtu] = useState(text(item.mtu));
  const [allowed, setAllowed] = useState(text(item.client_allowed_ips));
  const [keepalive, setKeepalive] = useState(text(item.keepalive));
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (item.id === null) {
      return;
    }
    setBusy(true);
    setProblem("");
    try {
      await api.updateInterface(item.id, {
        enabled,
        address,
        pool,
        endpoint_host: endpointHost,
        dns,
        mtu: number(mtu),
        client_allowed_ips: allowed,
        keepalive: number(keepalive),
      });
      onSaved();
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={(event) => void save(event)}>
      <h3>{item.name}</h3>
      <div className="row">
        <label>
          Server address
          <input
            value={address}
            placeholder="100.127.252.1/24"
            onChange={(event) => setAddress(event.target.value)}
          />
        </label>
        <label>
          Client pool
          <input
            value={pool}
            placeholder="100.127.252.0/24"
            onChange={(event) => setPool(event.target.value)}
          />
        </label>
        <label>
          Endpoint host
          <input
            value={endpointHost}
            placeholder="vpn.example.com"
            onChange={(event) => setEndpointHost(event.target.value)}
          />
        </label>
      </div>
      <div className="row">
        <label>
          DNS
          <input value={dns} onChange={(event) => setDns(event.target.value)} />
        </label>
        <label>
          MTU
          <input
            value={mtu}
            inputMode="numeric"
            onChange={(event) => setMtu(event.target.value)}
          />
        </label>
        <label>
          Client AllowedIPs
          <input
            value={allowed}
            placeholder="0.0.0.0/0"
            onChange={(event) => setAllowed(event.target.value)}
          />
        </label>
        <label>
          Keepalive
          <input
            value={keepalive}
            inputMode="numeric"
            onChange={(event) => setKeepalive(event.target.value)}
          />
        </label>
      </div>
      <label className="inline">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        Enabled: profiles can be issued on this interface
      </label>
      {problem ? <p className="problem">{problem}</p> : null}
      <div className="row">
        <button type="submit" disabled={busy}>
          {busy ? "Saving" : "Save"}
        </button>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </form>
  );
}
