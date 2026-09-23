import { useEffect, useState } from "react";

import { api, type Agent, type AgentInterface, type Check } from "../api";
import { age, ms, summary, when } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Pill, Stat, counted, toneOf, type Part } from "../tiles";
import { InboundForm } from "./InboundForm";
import { InterfaceForm } from "./InterfaceForm";

const LOG_LIMIT = 10;

function label(status: string): string {
  if (status === "up") {
    return "OK";
  }
  return status === "degraded" ? "Warning" : "Error";
}

function needs(missing: string[]): string {
  return `needs ${missing.map((field) => field.replace("_", " ")).join(", ")}`;
}

function peerParts(interfaces: AgentInterface[]): Part[] {
  return interfaces
    .filter((item) => item.present)
    .map((item) => ({ text: `${item.name} ${item.peers}` }));
}

function checkParts(checks: Check[]): Part[] {
  const of = (status: string) => checks.filter((item) => item.status === status).length;
  return counted([
    [of("up"), "ok", "ok"],
    [of("degraded"), "warning", "warn"],
    [of("down"), "error", "down"],
  ]);
}

export function AgentDetail({
  agent,
  busy,
  now,
  problem: listProblem,
  onBack,
  onProbe,
  onSaved,
}: {
  agent: Agent;
  busy: boolean;
  now: number;
  problem: Problem | null;
  onBack: () => void;
  onProbe: () => void;
  onSaved: () => void;
}) {
  const [checks, setChecks] = useState<Check[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [editingInbound, setEditingInbound] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);

  useEffect(() => {
    let live = true;
    setProblem(null);
    api
      .checks(agent.id, LOG_LIMIT)
      .then((found) => {
        if (live) {
          setChecks(found);
        }
      })
      .catch((error: unknown) => {
        if (live) {
          setProblem(describe(error, "Could not load the healthcheck log"));
        }
      });
    return () => {
      live = false;
    };
  }, [agent.id, agent.checked_at]);

  const present = agent.interfaces.filter((item) => item.present).length;
  const peers = agent.interfaces.reduce((total, item) => total + item.peers, 0);
  const sampled = checks
    .map((item) => item.latency_ms)
    .filter((value): value is number => value !== null);
  const average = sampled.length
    ? sampled.reduce((total, value) => total + value, 0) / sampled.length
    : null;
  const versions = [
    `agent ${agent.version ?? "-"}`,
    agent.awg ?? "awg -",
    agent.xray ?? "xray -",
  ].join(" \u00b7 ");

  return (
    <section className="page">
      <nav className="crumbs">
        <button type="button" onClick={onBack}>
          &larr; Dashboard
        </button>
        <span aria-hidden="true">/</span>
        <span>{agent.name}</span>
      </nav>

      <div className="page-header">
        <div className="identity">
          <div className="identity-name">
            <h1>{agent.name}</h1>
            <Pill tone={toneOf(agent.status)}>{agent.status}</Pill>
          </div>
          <div className="identity-meta">
            <span className="key">{agent.endpoint}</span>
            <span>{versions}</span>
          </div>
        </div>
        <button type="button" className="action" disabled={busy} onClick={onProbe}>
          {busy ? "Probing" : "Probe now"}
        </button>
      </div>

      <Banner
        problem={listProblem ?? problem}
        shown={detailShown}
        onToggle={() => setDetailShown((shown) => !shown)}
      />

      <div className="stats">
        <Stat label="Peers" value={`${peers}`} parts={peerParts(agent.interfaces)} />
        <Stat
          label="Interfaces"
          value={`${present} / ${agent.interfaces.length}`}
          parts={[
            { text: "up", tone: "ok" },
            ...counted([[agent.interfaces.length - present, "absent", "warn"]]),
          ]}
        />
        <Stat
          label="Latency"
          value={ms(agent.latency_ms)}
          parts={[{ text: `avg of last ${LOG_LIMIT}: ${ms(average)}` }]}
        />
        <Stat
          label="Last seen up"
          value={age(agent.last_seen, now) || "never"}
          parts={[{ text: when(agent.last_seen) }]}
        />
      </div>

      <div className="panel">
        <div className="panel-title">
          <h2>Interfaces</h2>
        </div>
        <table className="interfaces-table">
          <thead>
            <tr>
              <th>Interface</th>
              <th>On host</th>
              <th>Port</th>
              <th>Public key</th>
              <th>Peers</th>
              <th>Profiles</th>
            </tr>
          </thead>
          <tbody>
            {agent.interfaces.length === 0 ? (
              <tr>
                <td colSpan={6} className="cell-empty">
                  The agent reported no interfaces. Check AWG_KEEPER_INTERFACES and the agent log.
                </td>
              </tr>
            ) : null}
            {agent.interfaces.map((item) => (
              <tr
                key={item.name}
                className={item.id === null ? undefined : "clickable"}
                onClick={() => setEditing(item.id === null ? null : item.name)}
              >
                <td className="cell-name">{item.name}</td>
                <td className={item.error || !item.present ? "problem" : ""}>
                  {item.error ?? (item.present ? "up" : "absent")}
                </td>
                <td>{item.listen_port || "-"}</td>
                <td className="key">{item.public_key ?? "-"}</td>
                <td>{item.present ? item.peers : "-"}</td>
                <td>
                  {item.enabled ? (
                    <Pill tone="ok">enabled</Pill>
                  ) : item.missing.length ? (
                    <Pill tone="warn">not configured</Pill>
                  ) : (
                    <Pill tone="idle">disabled</Pill>
                  )}
                  <div className="muted">
                    {item.enabled
                      ? (item.address ?? "-")
                      : item.missing.length
                        ? `needs ${item.missing.join(", ")}`
                        : (item.address ?? "-")}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {agent.interfaces
        .filter((item) => item.name === editing)
        .map((item) => (
          <InterfaceForm
            key={`${agent.id}-${item.name}`}
            item={item}
            agent={agent.name}
            onClose={() => setEditing(null)}
            onSaved={() => {
              setEditing(null);
              onSaved();
            }}
          />
        ))}

      <div className="panel">
        <div className="panel-title">
          <h2>Inbounds</h2>
        </div>
        <table className="interfaces-table">
          <thead>
            <tr>
              <th>Inbound</th>
              <th>Transport</th>
              <th>Port</th>
              <th>Reality key</th>
              <th>Clients</th>
              <th>Profiles</th>
            </tr>
          </thead>
          <tbody>
            {agent.inbounds.length === 0 ? (
              <tr>
                <td colSpan={6} className="cell-empty">
                  The agent reported no vless inbounds. Check AWG_KEEPER_XRAY_CONFIG and the
                  agent log.
                </td>
              </tr>
            ) : null}
            {agent.inbounds.map((item) => (
              <tr key={item.tag} className="clickable" onClick={() => setEditingInbound(item.tag)}>
                <td className="cell-name">{item.tag}</td>
                <td className={item.present ? "" : "problem"}>
                  {item.present
                    ? [item.protocol, item.network, item.security].join(" \u00b7 ")
                    : "absent"}
                </td>
                <td>{item.port || "-"}</td>
                <td className={item.public_key ? "key" : "cell-empty"}>{item.public_key ?? "-"}</td>
                <td>{item.present ? item.clients : "-"}</td>
                <td>
                  {item.enabled ? (
                    <Pill tone="ok">enabled</Pill>
                  ) : item.missing.length ? (
                    <Pill tone="warn">not configured</Pill>
                  ) : (
                    <Pill tone="idle">disabled</Pill>
                  )}
                  <div className="muted">
                    {!item.enabled && item.missing.length
                      ? needs(item.missing)
                      : item.server_names.length
                        ? `sni ${item.server_names[0]}`
                        : "-"}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {agent.inbounds
        .filter((item) => item.tag === editingInbound && item.id !== null)
        .map((item) => (
          <InboundForm
            key={`${agent.id}-${item.tag}`}
            item={item}
            agent={agent.name}
            onClose={() => setEditingInbound(null)}
            onSaved={() => {
              setEditingInbound(null);
              onSaved();
            }}
          />
        ))}

      <div className="panel">
        <div className="panel-title">
          <div className="panel-heading">
            <h2>Healthcheck log</h2>
            <span className="panel-scope">last {LOG_LIMIT}</span>
          </div>
          <div className="panel-summary">
            {checkParts(checks).map((part) => (
              <Pill key={part.text} tone={part.tone ?? "idle"} dot>
                {part.text}
              </Pill>
            ))}
          </div>
        </div>
        <table className="checks-table">
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
                <td colSpan={4} className="cell-empty">
                  No healthcheck recorded yet.
                </td>
              </tr>
            ) : null}
            {checks.map((check) => (
              <tr
                key={check.id}
                className={
                  check.status === "up"
                    ? undefined
                    : check.status === "degraded"
                      ? "check-warn"
                      : "check-down"
                }
              >
                <td>{when(check.checked_at)}</td>
                <td>
                  <Pill tone={toneOf(check.status)} dot>
                    {label(check.status)}
                  </Pill>
                </td>
                <td>{ms(check.latency_ms)}</td>
                <td>{check.error ?? summary(check.interfaces)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
