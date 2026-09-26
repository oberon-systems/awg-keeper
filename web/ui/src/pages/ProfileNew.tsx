import { useEffect, useState } from "react";

import { api, type Agent, type Inbound, type Interface, type ProfileCreate } from "../api";
import { Choice, Field } from "../fields";
import { generateKeyPair, newUuid } from "../keys";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";
import { type Issue, issueOf } from "./IssuedConfig";

export function Option({
  title,
  hint,
  checked,
  disabled,
  onToggle,
  children,
}: {
  title: string;
  hint: string;
  checked: boolean;
  disabled: boolean;
  onToggle: (checked: boolean) => void;
  children?: React.ReactNode;
}) {
  return (
    <div className={checked ? "option chosen" : "option"}>
      <label className="check">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onToggle(event.target.checked)}
        />
        <span>
          <span className="check-title">{title}</span>
          <span className="check-hint">{hint}</span>
        </span>
      </label>
      {children}
    </div>
  );
}

function choose(id: number | null, found: Interface[], open: Inbound[]) {
  const own = found.find((item) => item.node_id === id);
  const reached = open.find((item) => item.node_id === id);
  return {
    interfaceId: own ? String(own.id) : "",
    inboundId: reached ? String(reached.id) : "",
  };
}

export function ProfileNew({
  onClose,
  onIssued,
}: {
  onClose: () => void;
  onIssued: (issue: Issue) => void;
}) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [interfaces, setInterfaces] = useState<Interface[]>([]);
  const [inbounds, setInbounds] = useState<Inbound[]>([]);
  const [node, setNode] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [awg, setAwg] = useState(true);
  const [xray, setXray] = useState(true);
  const [interfaceId, setInterfaceId] = useState("");
  const [inboundId, setInboundId] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  const offered = interfaces.filter((item) => item.node_id === node);
  const reached = inbounds.filter((item) => item.node_id === node);

  function pick(id: number) {
    const chosen = choose(id, interfaces, inbounds);
    setNode(id);
    setInterfaceId(chosen.interfaceId);
    setInboundId(chosen.inboundId);
    setAwg(Boolean(chosen.interfaceId));
    setXray(Boolean(chosen.inboundId));
  }

  useEffect(() => {
    Promise.all([api.agents(), api.interfaces(), api.inbounds()])
      .then(([found, open, reachable]) => {
        const first = found[0]?.id ?? null;
        const chosen = choose(first, open, reachable);
        setAgents(found);
        setInterfaces(open);
        setInbounds(reachable);
        setNode(first);
        setInterfaceId(chosen.interfaceId);
        setInboundId(chosen.inboundId);
        setAwg(Boolean(chosen.interfaceId));
        setXray(Boolean(chosen.inboundId));
      })
      .catch((error: unknown) => setProblem(describe(error, "Could not load the agents")));
  }, []);

  const peersOn = (item: Interface) =>
    agents
      .find((agent) => agent.id === item.node_id)
      ?.interfaces.find((reported) => reported.name === item.name)?.peers ?? 0;

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    // Generated here and kept only in this closure: the panel is told the
    // public half and the UUID, and neither private key nor UUID is stored.
    const pair = awg ? generateKeyPair() : null;
    const body: ProfileCreate = { name, note: note || null };
    if (pair) {
      body.awg = { interface_id: Number(interfaceId), public_key: pair.publicKey };
    }
    if (xray) {
      body.xray = { inbound_id: Number(inboundId), id: newUuid() };
    }
    try {
      const answer = await api.createProfile(body);
      onIssued(await issueOf(answer, pair));
    } catch (error) {
      setProblem(describe(error, "Could not create the profile"));
    } finally {
      setBusy(false);
    }
  }

  const ready = name.trim() && ((awg && interfaceId) || (xray && inboundId));

  return (
    <div className="scrim">
      <form className="modal" onSubmit={(event) => void create(event)}>
        <div className="modal-header">
          <div className="modal-heading">
            <h2>New profile</h2>
            <p>Keys are generated in this browser; the panel never sees the private half</p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <div className="field-row">
          <Field label="Name" value={name} onChange={setName} />
          <Field label="Note" value={note} onChange={setNote} />
        </div>
        <Choice
          label="Agent"
          value={node === null ? "" : String(node)}
          options={agents.map((item) => ({ value: String(item.id), label: item.name }))}
          onChange={(value) => pick(Number(value))}
        />

        <span className="section-label">Access</span>
        <Option
          title="AmneziaWG"
          hint="Peer with an address from the interface pool"
          checked={awg}
          disabled={offered.length === 0}
          onToggle={setAwg}
        >
          <Choice
            label="Interface"
            value={interfaceId}
            disabled={!awg}
            options={offered.map((item) => ({
              value: String(item.id),
              label: `${item.name} \u00b7 ${item.pool} \u00b7 ${peersOn(item)} peers`,
            }))}
            onChange={setInterfaceId}
          />
        </Option>
        <Option
          title="Xray (VLESS + Reality)"
          hint="Client on an inbound, issued as a vless:// link"
          checked={xray}
          disabled={reached.length === 0}
          onToggle={setXray}
        >
          <Choice
            label="Inbound"
            value={inboundId}
            disabled={!xray}
            options={reached.map((item) => ({
              value: String(item.id),
              label: `${item.tag} \u00b7 ${item.network} \u00b7 ${item.security}`,
            }))}
            onChange={setInboundId}
          />
        </Option>

        <p className="notice">
          The configuration is shown once, right after creation. Lost configs cannot be
          recovered, only reissued.
        </p>

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((value) => !value)}
        />

        <div className="modal-footer">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="action" disabled={busy || !ready}>
            Create profile
          </button>
        </div>
      </form>
    </div>
  );
}
