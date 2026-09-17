import { useCallback, useEffect, useState } from "react";

import { api, type Agent, type Check, type ReportedInterface } from "../api";
import { InterfaceForm } from "./InterfaceForm";

const REFRESH_MS = 30_000;

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "never";
}

function age(value: string | null, now: number): string {
  if (!value) {
    return "";
  }
  const seconds = Math.max(0, Math.round((now - new Date(value).getTime()) / 1000));
  if (seconds < 120) {
    return `${seconds}s ago`;
  }
  if (seconds < 7200) {
    return `${Math.round(seconds / 60)}m ago`;
  }
  return `${Math.round(seconds / 3600)}h ago`;
}

function ms(value: number | null): string {
  return value === null ? "-" : `${Math.round(value)}ms`;
}

function summary(items: ReportedInterface[]): string {
  return items
    .map((item) => {
      if (item.error) {
        return `${item.name}: ${item.error}`;
      }
      return item.present ? `${item.name}: ${item.peers ?? 0} peers` : `${item.name}: absent`;
    })
    .join("; ");
}

export function Status() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const current = agents.find((item) => item.id === selected) ?? agents[0] ?? null;

  const refresh = useCallback(
    async (probe = false) => {
      setProblem("");
      try {
        const found = probe ? await api.probe() : await api.agents();
        setAgents(found);
        const id = selected ?? found[0]?.id ?? null;
        setChecks(id === null ? [] : await api.checks(id));
      } catch (error) {
        setProblem(error instanceof Error ? error.message : "could not load the agents");
      } finally {
        setLoaded(true);
        setNow(Date.now());
      }
    },
    [selected],
  );

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function probeNow() {
    setBusy(true);
    await refresh(true);
    setBusy(false);
  }

  return (
    <section>
      <div className="row">
        <button type="button" disabled={busy} onClick={() => void probeNow()}>
          {busy ? "Probing" : "Probe now"}
        </button>
        <span className="muted">
          refreshed {new Date(now).toLocaleTimeString()}, every {REFRESH_MS / 1000}s
        </span>
      </div>

      {problem ? <p className="problem">{problem}</p> : null}
      {loaded && !problem && agents.length === 0 ? (
        <p className="problem">
          No agents: AWG_PANEL_AGENTS is empty on the panel, so nothing is probed.
        </p>
      ) : null}

      <table>
        <thead>
          <tr>
            <th>Agent</th>
            <th>Status</th>
            <th>Last healthcheck</th>
            <th>Last seen up</th>
            <th>Latency</th>
            <th>Versions</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr
              key={agent.id}
              className={agent.id === current?.id ? "selected clickable" : "clickable"}
              onClick={() => {
                setSelected(agent.id);
                setEditing(null);
              }}
            >
              <td>
                {agent.name}
                <div className="key">{agent.endpoint}</div>
                {agent.configured ? null : (
                  <div className="problem">not in AWG_PANEL_AGENTS, not probed</div>
                )}
              </td>
              <td>
                <span className={`badge status-${agent.status}`}>{agent.status}</span>
              </td>
              <td>
                {when(agent.checked_at)}
                <div className="muted">{age(agent.checked_at, now)}</div>
              </td>
              <td>
                {when(agent.last_seen)}
                <div className="muted">{age(agent.last_seen, now)}</div>
              </td>
              <td>{ms(agent.latency_ms)}</td>
              <td>
                <div>agent {agent.version ?? "-"}</div>
                <div>{agent.awg ?? "awg -"}</div>
                <div>{agent.xray ?? "xray -"}</div>
              </td>
              <td className="problem">{agent.error ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {current ? (
        <>
          <h2>{current.name}: interfaces</h2>
          {current.interfaces.length === 0 ? (
            <p className="warning">
              The agent reported no interfaces. Check AWG_KEEPER_INTERFACES and the agent log.
            </p>
          ) : null}
          <table>
            <thead>
              <tr>
                <th>Interface</th>
                <th>On host</th>
                <th>Port</th>
                <th>Public key</th>
                <th>Profiles</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {current.interfaces.map((item) => (
                <tr key={item.name}>
                  <td>{item.name}</td>
                  <td className={item.error || !item.present ? "problem" : ""}>
                    {item.error ?? (item.present ? `up, ${item.peers} peers` : "absent")}
                  </td>
                  <td>{item.listen_port || "-"}</td>
                  <td className="key">{item.public_key ?? "-"}</td>
                  <td>
                    {item.enabled ? (
                      <span className="badge status-up">enabled</span>
                    ) : (
                      <span className="badge status-unknown">disabled</span>
                    )}
                    {item.address ? <div className="muted">{item.address}</div> : null}
                  </td>
                  <td>
                    {item.id === null ? (
                      <span className="muted">agent reports no key</span>
                    ) : (
                      <button type="button" onClick={() => setEditing(item.name)}>
                        Configure
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {current.interfaces
            .filter((item) => item.name === editing)
            .map((item) => (
              <InterfaceForm
                key={`${current.id}-${item.name}`}
                item={item}
                onClose={() => setEditing(null)}
                onSaved={() => {
                  setEditing(null);
                  void refresh();
                }}
              />
            ))}

          <h2>{current.name}: healthcheck log</h2>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {checks.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No healthcheck recorded yet.
                  </td>
                </tr>
              ) : null}
              {checks.map((check) => (
                <tr key={check.id} className={check.status === "up" ? "" : "failed"}>
                  <td>{when(check.checked_at)}</td>
                  <td>
                    <span className={`badge status-${check.status}`}>{check.status}</span>
                  </td>
                  <td>{ms(check.latency_ms)}</td>
                  <td>
                    {check.error ? <div className="problem">{check.error}</div> : null}
                    {check.interfaces.length ? <div>{summary(check.interfaces)}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
