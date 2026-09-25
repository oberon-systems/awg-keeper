import { useEffect, useState } from "react";

import {
  api,
  type Agent,
  type Inbound,
  type Interface,
  type Profile,
  type ProfileEdit as Edit,
} from "../api";
import { day } from "../format";
import { Choice, Field } from "../fields";
import { generateKeyPair } from "../keys";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";
import { type Issue, issueOf } from "./IssuedConfig";
import { Option } from "./ProfileNew";

function text(value: string | number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

export function ProfileEdit({
  profile,
  onClose,
  onSaved,
}: {
  profile: Profile;
  onClose: () => void;
  onSaved: (issue: Issue | null) => void;
}) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [interfaces, setInterfaces] = useState<Interface[]>([]);
  const [inbounds, setInbounds] = useState<Inbound[]>([]);
  const [name, setName] = useState(profile.name);
  const [note, setNote] = useState(text(profile.note));
  const [dns, setDns] = useState(text(profile.dns));
  const [mtu, setMtu] = useState(text(profile.mtu));
  const [allowed, setAllowed] = useState("");
  const [awg, setAwg] = useState(profile.peer !== null);
  const [xray, setXray] = useState(profile.xray !== null);
  const [interfaceId, setInterfaceId] = useState("");
  const [inboundId, setInboundId] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  const node = agents.find((item) => item.name === profile.node) ?? null;
  const own = node?.interfaces.find((item) => item.id === profile.peer?.interface_id);
  const offered = interfaces.filter((item) => !node || item.node_id === node.id);
  const reached = inbounds.filter((item) => !node || item.node_id === node.id);
  const chosen = own ?? node?.interfaces.find((item) => String(item.id) === interfaceId);

  useEffect(() => {
    Promise.all([api.agents(), api.interfaces(), api.inbounds()])
      .then(([found, open, reachable]) => {
        const home = found.find((item) => item.name === profile.node);
        const mine = home?.interfaces.find((item) => item.id === profile.peer?.interface_id);
        const first = open.find((item) => !home || item.node_id === home.id);
        const tag = reachable.find((item) => !home || item.node_id === home.id);
        setAgents(found);
        setInterfaces(open);
        setInbounds(reachable);
        setInterfaceId(first ? String(first.id) : "");
        setInboundId(tag ? String(tag.id) : "");
        if (profile.peer && profile.peer.allowed_ips !== mine?.client_allowed_ips) {
          setAllowed(profile.peer.allowed_ips);
        }
      })
      .catch((error: unknown) => setProblem(describe(error, "Could not load the agents")));
  }, [profile]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    const pair = awg && !profile.peer ? generateKeyPair() : null;
    const body: Edit = {
      name: name.trim(),
      note: note.trim() || null,
      dns: dns.trim() || null,
      mtu: mtu.trim() ? Number(mtu) : null,
      allowed_ips: allowed.trim() || null,
    };
    if (profile.peer && !awg) {
      body.awg = null;
    } else if (pair) {
      body.awg = { interface_id: Number(interfaceId), public_key: pair.publicKey };
    }
    if (profile.xray && !xray) {
      body.xray = null;
    } else if (xray && !profile.xray) {
      body.xray = { inbound_id: Number(inboundId), id: crypto.randomUUID() };
    }
    try {
      const answer = await api.editProfile(profile.id, body);
      const added = answer.config_template || answer.link;
      onSaved(added ? await issueOf(answer, pair) : null);
    } catch (error) {
      setProblem(describe(error, "Could not save the profile"));
    } finally {
      setBusy(false);
    }
  }

  const keepsAwg = awg && (profile.peer || interfaceId);
  const keepsXray = xray && (profile.xray || inboundId);
  const ready = name.trim() && (keepsAwg || keepsXray);
  const defaults = (value: string | number | null | undefined) =>
    value === null || value === undefined ? "none" : `${value} \u00b7 interface`;

  return (
    <div className="scrim">
      <form className="modal" onSubmit={(event) => void save(event)}>
        <div className="modal-header">
          <div className="modal-heading">
            <h2>Edit {profile.name}</h2>
            <p>
              Created {day(profile.created_at)} on {profile.node ?? "-"}. Name and note apply
              at once, the client config on reroll
            </p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <div className="field-row">
          <Field label="Name" value={name} onChange={setName} />
          <Field label="Note" value={note} onChange={setNote} />
        </div>
        <Field
          label="Agent"
          value={profile.node ?? ""}
          onChange={() => undefined}
          locked="A profile stays on the agent it was issued on"
        />

        <span className="section-label">Client config</span>
        <div className="field-row">
          <Field label="DNS" value={dns} onChange={setDns} placeholder={defaults(chosen?.dns)} />
          <Field
            label="MTU"
            value={mtu}
            onChange={setMtu}
            numeric
            placeholder={defaults(chosen?.mtu)}
          />
        </div>
        <Field
          label="Allowed IPs"
          value={allowed}
          onChange={setAllowed}
          placeholder={defaults(chosen?.client_allowed_ips)}
          hint="Empty takes the interface value. A change here needs the profile rerolled"
        />

        <span className="section-label">Access</span>
        <Option
          title="AmneziaWG"
          hint={
            profile.peer
              ? "Unchecking removes the peer from the interface"
              : "Checking adds a peer, its config is shown once"
          }
          checked={awg}
          disabled={!profile.peer && offered.length === 0}
          onToggle={setAwg}
        >
          {profile.peer ? (
            <Field
              label="Interface and address"
              value={`${profile.peer.interface} \u00b7 ${profile.peer.assigned_ip}`}
              onChange={() => undefined}
              locked="Moving a peer means removing it and adding a new one"
            />
          ) : (
            <Choice
              label="Interface"
              value={interfaceId}
              disabled={!awg}
              options={offered.map((item) => ({
                value: String(item.id),
                label: `${item.name} \u00b7 ${item.pool}`,
              }))}
              onChange={setInterfaceId}
            />
          )}
        </Option>
        <Option
          title="Xray (VLESS + Reality)"
          hint={
            profile.xray
              ? "Unchecking removes the client from the inbound"
              : "Checking adds a client, its link is shown once"
          }
          checked={xray}
          disabled={!profile.xray && reached.length === 0}
          onToggle={setXray}
        >
          {profile.xray ? (
            <Field
              label="Inbound"
              value={profile.xray.inbound}
              onChange={() => undefined}
              locked="The client stays on its inbound; its tag follows the name"
            />
          ) : (
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
          )}
        </Option>

        <p className="notice">
          Name and note are saved at once. Added access shows its config once, after saving.
          DNS, MTU and allowed IPs reach the device only after a reroll.
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
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
