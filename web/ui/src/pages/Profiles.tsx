import { useCallback, useEffect, useState } from "react";

import {
  api,
  type Agent,
  type AgentInterface,
  type Interface,
  type Issued,
  type Profile,
} from "../api";
import { IssuedConfig } from "./IssuedConfig";
import { fillConfig, generateKeyPair } from "../keys";

function why(item: AgentInterface): string {
  if (item.id === null) {
    return `${item.name}: agent reports no key`;
  }
  if (item.missing.length) {
    return `${item.name}: not configured (needs ${item.missing.join(", ")})`;
  }
  return `${item.name}: disabled`;
}

export function Profiles() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [interfaces, setInterfaces] = useState<Interface[]>([]);
  const [nodes, setNodes] = useState<Agent[]>([]);
  const [node, setNode] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [chosen, setChosen] = useState<number | null>(null);
  const [issued, setIssued] = useState<{ profile: Profile; config: string } | null>(
    null,
  );
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setProfiles(await api.profiles());
  }, []);

  const offered = interfaces.filter((item) => item.node_id === node);
  const idle = (nodes.find((item) => item.id === node)?.interfaces ?? []).filter(
    (item) => !item.enabled,
  );

  function pickNode(id: number) {
    setNode(id);
    setChosen(interfaces.find((item) => item.node_id === id)?.id ?? null);
  }

  useEffect(() => {
    void Promise.all([api.agents(), api.interfaces()]).then(([agents, found]) => {
      const first = agents[0]?.id ?? null;
      setNodes(agents);
      setInterfaces(found);
      setNode(first);
      setChosen(found.find((item) => item.node_id === first)?.id ?? null);
    });
    void reload();
  }, [reload]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (chosen === null) {
      setProblem("this agent has no interface to issue against");
      return;
    }

    setBusy(true);
    setProblem("");
    // Generated before the call and kept only in this closure: the panel is
    // told the public half and the private one dies with the page.
    const pair = generateKeyPair();
    try {
      const answer: Issued = await api.createProfile(
        name,
        note,
        chosen,
        pair.publicKey,
      );
      setIssued({
        profile: answer.profile,
        config: fillConfig(answer.config_template, pair.privateKey),
      });
      setName("");
      setNote("");
      await reload();
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "could not create");
    } finally {
      setBusy(false);
    }
  }

  async function remove(profile: Profile) {
    setProblem("");
    try {
      await api.deleteProfile(profile.id);
      await reload();
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "could not delete");
    }
  }

  return (
    <section>
      <form className="card row" onSubmit={(event) => void create(event)}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Note
          <input value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <label>
          Agent
          <select
            value={node ?? ""}
            onChange={(event) => pickNode(Number(event.target.value))}
          >
            {nodes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Interface
          <select
            value={chosen ?? ""}
            disabled={offered.length === 0}
            onChange={(event) => setChosen(Number(event.target.value))}
          >
            {offered.length === 0 ? <option value="">none configured</option> : null}
            {offered.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy || !name || chosen === null}>
          Add profile
        </button>
      </form>

      {nodes.length === 0 ? (
        <p className="warning">No agents: set AWG_PANEL_AGENTS on the panel.</p>
      ) : null}
      {node !== null && offered.length === 0 ? (
        <div className="warning">
          {idle.map((item) => (
            <p key={item.name}>{why(item)}</p>
          ))}
          <p>
            {idle.length
              ? "Configure it on the Dashboard page."
              : "This agent reports no interface: check AWG_KEEPER_INTERFACES and the agent log."}
          </p>
        </div>
      ) : null}
      {problem ? <p className="problem">{problem}</p> : null}

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Address</th>
            <th>Public key</th>
            <th>Note</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {profiles.map((profile) => (
            <tr key={profile.id}>
              <td>{profile.name}</td>
              <td>{profile.peer?.assigned_ip ?? "-"}</td>
              <td className="key">{profile.peer?.public_key ?? "-"}</td>
              <td>{profile.note ?? ""}</td>
              <td>
                <button type="button" onClick={() => void remove(profile)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {issued ? (
        <IssuedConfig
          name={issued.profile.name}
          config={issued.config}
          onClose={() => setIssued(null)}
        />
      ) : null}
    </section>
  );
}
