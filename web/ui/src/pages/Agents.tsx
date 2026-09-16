import { useCallback, useEffect, useState } from "react";

import { api, type Agent } from "../api";

export function Agents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const probe = useCallback(async () => {
    setBusy(true);
    setProblem("");
    try {
      setAgents(await api.agents());
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "could not probe the agents");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void probe();
  }, [probe]);

  return (
    <section>
      <div className="row">
        <button type="button" disabled={busy} onClick={() => void probe()}>
          {busy ? "Probing" : "Refresh"}
        </button>
      </div>

      {problem ? <p className="problem">{problem}</p> : null}
      {!busy && !problem && agents.length === 0 ? (
        <p className="warning">No agents: add a node to the database.</p>
      ) : null}

      <table>
        <thead>
          <tr>
            <th>Agent</th>
            <th>Status</th>
            <th>Last seen</th>
            <th>Versions</th>
            <th>Interfaces</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr key={agent.id}>
              <td>
                {agent.name}
                <div className="key">{agent.endpoint}</div>
              </td>
              <td className={agent.status === "up" ? "" : "problem"}>{agent.status}</td>
              <td>{agent.last_seen ? new Date(agent.last_seen).toLocaleString() : "-"}</td>
              <td>
                <div>agent {agent.version ?? "-"}</div>
                <div>awg {agent.awg ?? "-"}</div>
                <div>xray {agent.xray ?? "-"}</div>
              </td>
              <td>
                {agent.interfaces.length === 0 ? "-" : null}
                {agent.interfaces.map((item) => (
                  <div key={item.name}>
                    {item.name}: {item.present ? `${item.peers} peers` : "absent"}
                    {item.error ? <div className="problem">{item.error}</div> : null}
                  </div>
                ))}
              </td>
              <td className="problem">{agent.error ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
