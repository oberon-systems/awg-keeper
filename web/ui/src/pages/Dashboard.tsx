import { useCallback, useEffect, useState } from "react";

import { api, type Agent } from "../api";
import { age, ms, when } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Pill, Stat, counted, toneOf, type Part } from "../tiles";
import { AgentDetail } from "./AgentDetail";

const REFRESH_MS = 30_000;

function agentParts(agents: Agent[]): Part[] {
  const of = (status: string) => agents.filter((item) => item.status === status).length;
  return counted([
    [of("up"), "up", "ok"],
    [of("degraded"), "degraded", "warn"],
    [of("down"), "down", "down"],
  ]);
}

export function Dashboard() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const refresh = useCallback(async (probe = false) => {
    try {
      setAgents(probe ? await api.probe() : await api.agents());
      setProblem(null);
      setDetailShown(false);
    } catch (error) {
      setProblem(describe(error, "Could not load the agents"));
    } finally {
      setLoaded(true);
      setNow(Date.now());
    }
  }, []);

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

  const current = agents.find((item) => item.id === selected) ?? null;
  if (selected !== null && current) {
    return (
      <AgentDetail
        agent={current}
        busy={busy}
        now={now}
        problem={problem}
        onBack={() => setSelected(null)}
        onProbe={() => void probeNow()}
        onSaved={() => void refresh()}
      />
    );
  }

  const reported = agents.flatMap((item) => item.interfaces);
  const running = agents.filter((item) => item.status === "up");
  const peers = running
    .flatMap((item) => item.interfaces)
    .reduce((total, item) => total + item.peers, 0);
  const latencies = agents
    .map((item) => item.latency_ms)
    .filter((value): value is number => value !== null);
  const average = latencies.length
    ? latencies.reduce((total, value) => total + value, 0) / latencies.length
    : null;

  return (
    <section className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Dashboard</h1>
          <p className="page-note">
            Refreshed {new Date(now).toLocaleTimeString()}, every {REFRESH_MS / 1000}s
          </p>
        </div>
        <button type="button" className="action" disabled={busy} onClick={() => void probeNow()}>
          {busy ? "Probing" : "Probe now"}
        </button>
      </div>

      <Banner
        problem={problem}
        shown={detailShown}
        onToggle={() => setDetailShown((shown) => !shown)}
      />
      {loaded && !problem && agents.length === 0 ? (
        <div className="problem-banner" role="alert">
          <div className="problem-banner-summary">
            <span>No agents: AWG_PANEL_AGENTS is empty on the panel, so nothing is probed</span>
          </div>
        </div>
      ) : null}

      <div className="stats">
        <Stat label="Agents" value={`${agents.length}`} parts={agentParts(agents)} />
        <Stat
          label="Interfaces enabled"
          value={`${reported.filter((item) => item.enabled).length}`}
          parts={[{ text: `of ${reported.length} reported` }]}
        />
        <Stat
          label="Active peers"
          value={`${peers}`}
          parts={[{ text: `on ${running.length} agents up` }]}
        />
        <Stat
          label="Avg latency"
          value={ms(average)}
          parts={[{ text: "last healthcheck" }]}
        />
      </div>

      <div className="panel">
        <div className="panel-title">
          <h2>Agents</h2>
        </div>
        <table className="agents-table">
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
              <tr key={agent.id} className="clickable" onClick={() => setSelected(agent.id)}>
                <td>
                  <div className="cell-name">{agent.name}</div>
                  <div className="key">{agent.endpoint}</div>
                  {agent.configured ? null : (
                    <div className="muted problem">not in AWG_PANEL_AGENTS, not probed</div>
                  )}
                </td>
                <td>
                  <Pill tone={toneOf(agent.status)}>{agent.status}</Pill>
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
                  <div className="muted">{agent.awg ?? "awg -"}</div>
                  <div className="muted">{agent.xray ?? "xray -"}</div>
                </td>
                <td className={agent.error ? "problem" : "cell-empty"}>{agent.error ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
