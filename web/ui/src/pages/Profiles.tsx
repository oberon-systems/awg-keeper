import { useCallback, useEffect, useState } from "react";

import { api, type Profile } from "../api";
import { day, shortKey } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Pill, Refresh, Stat, counted, type Part } from "../tiles";
import { IssuedConfig, type Issue } from "./IssuedConfig";
import { ProfileDelete } from "./ProfileDelete";
import { ProfileEdit } from "./ProfileEdit";
import { ProfileNew } from "./ProfileNew";
import { ProfileReroll } from "./ProfileReroll";
import { ProfileStats } from "./ProfileStats";

const WEEK_MS = 7 * 24 * 3600 * 1000;

function on(names: string[]): Part[] {
  const unique = [...new Set(names)].sort();
  return unique.length ? [{ text: `on ${unique.join(", ")}` }] : [];
}

function Empty() {
  return <span className="cell-empty">-</span>;
}

export function Profiles() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [issued, setIssued] = useState<Issue | null>(null);
  const [deleting, setDeleting] = useState<Profile | null>(null);
  const [rerolling, setRerolling] = useState<Profile | null>(null);
  const [editing, setEditing] = useState<Profile | null>(null);
  const [switching, setSwitching] = useState<number | null>(null);
  const [inspected, setInspected] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setProfiles(await api.profiles());
      setProblem(null);
      setDetailShown(false);
    } catch (error) {
      setProblem(describe(error, "Could not load the profiles"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function toggle(item: Profile, enabled: boolean) {
    setSwitching(item.id);
    try {
      await api.setProfileEnabled(item.id, enabled);
      await reload();
    } catch (error) {
      setProblem(describe(error, `Could not turn ${item.name} ${enabled ? "on" : "off"}`));
    } finally {
      setSwitching(null);
    }
  }

  const wanted = query.trim().toLowerCase();
  const shown = profiles.filter(
    (item) =>
      !wanted ||
      item.name.toLowerCase().includes(wanted) ||
      (item.note ?? "").toLowerCase().includes(wanted),
  );
  const enabled = profiles.filter((item) => item.enabled).length;
  const peers = profiles.flatMap((item) => (item.peer ? [item.peer.interface] : []));
  const clients = profiles.flatMap((item) => (item.xray ? [item.xray.inbound] : []));
  const now = Date.now();
  const recent = profiles.filter(
    (item) => now - new Date(item.created_at).getTime() < WEEK_MS,
  );
  const latest = profiles
    .map((item) => item.created_at)
    .sort()
    .pop();

  return (
    <section className="page">
      <div className="page-header">
        <div className="page-heading">
          <h1>Profiles</h1>
          <p className="page-note">Access issued to people and devices</p>
        </div>
        <div className="page-actions">
          <input
            className="search"
            type="search"
            placeholder="Search by name or note"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Refresh busy={loading} label="Reload the profiles" onClick={() => void reload()} />
          <button type="button" className="action" onClick={() => setCreating(true)}>
            + New profile
          </button>
        </div>
      </div>

      <Banner
        problem={problem}
        shown={detailShown}
        onToggle={() => setDetailShown((value) => !value)}
      />

      <div className="stats">
        <Stat
          label="Profiles"
          value={`${profiles.length}`}
          parts={counted([
            [enabled, "enabled", "ok"],
            [profiles.length - enabled, "disabled", "idle"],
          ])}
        />
        <Stat label="AmneziaWG peers" value={`${peers.length}`} parts={on(peers)} />
        <Stat label="Xray clients" value={`${clients.length}`} parts={on(clients)} />
        <Stat
          label="Issued this week"
          value={`${recent.length}`}
          parts={latest ? [{ text: `last: ${day(latest)}` }] : []}
        />
      </div>

      <div className="panel">
        <div className="panel-title">
          <h2>All profiles</h2>
        </div>
        <table className="profiles-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Agent</th>
              <th>AmneziaWG</th>
              <th>Xray</th>
              <th>Note</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {shown.map((item) => (
              <tr key={item.id}>
                <td>
                  <div className="cell-name">{item.name}</div>
                  <div className="muted">created {day(item.created_at)}</div>
                </td>
                <td>{item.node ?? <Empty />}</td>
                <td>
                  {item.peer ? (
                    <>
                      <div>{item.peer.assigned_ip}</div>
                      <div className="key">{shortKey(item.peer.public_key)}</div>
                    </>
                  ) : (
                    <Empty />
                  )}
                </td>
                <td>
                  {item.xray ? (
                    <>
                      <div>{item.xray.inbound}</div>
                      <div className="key">{item.xray.email}</div>
                    </>
                  ) : (
                    <Empty />
                  )}
                </td>
                <td>{item.note || <Empty />}</td>
                <td>
                  <div className="status-cell">
                    {item.peer ? (
                      <button
                        type="button"
                        role="switch"
                        aria-checked={item.peer.enabled}
                        aria-label={`AmneziaWG of ${item.name}`}
                        className={item.peer.enabled ? "toggle on" : "toggle"}
                        disabled={switching === item.id}
                        onClick={() => void toggle(item, !item.peer?.enabled)}
                      />
                    ) : (
                      <span className="toggle-space" />
                    )}
                    <Pill tone={item.enabled ? "ok" : "idle"}>
                      {item.enabled ? "enabled" : "disabled"}
                    </Pill>
                    {item.peer?.reroll ? <Pill tone="warn">reroll</Pill> : null}
                  </div>
                </td>
                <td>
                  <div className="row-actions">
                    <button type="button" className="small" onClick={() => setEditing(item)}>
                      Edit
                    </button>
                    <button type="button" className="small" onClick={() => setInspected(item)}>
                      Stats
                    </button>
                    <button type="button" className="small" onClick={() => setRerolling(item)}>
                      Reroll
                    </button>
                    <button
                      type="button"
                      className="small danger-outline"
                      onClick={() => setDeleting(item)}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {creating ? (
        <ProfileNew
          onClose={() => setCreating(false)}
          onIssued={(issue) => {
            setCreating(false);
            setIssued(issue);
            void reload();
          }}
        />
      ) : null}
      {issued ? <IssuedConfig issue={issued} onClose={() => setIssued(null)} /> : null}
      {deleting ? (
        <ProfileDelete
          profile={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => {
            setDeleting(null);
            void reload();
          }}
        />
      ) : null}
      {rerolling ? (
        <ProfileReroll
          profile={rerolling}
          onClose={() => setRerolling(null)}
          onIssued={(issue) => {
            setRerolling(null);
            setIssued(issue);
            void reload();
          }}
        />
      ) : null}
      {editing ? (
        <ProfileEdit
          profile={editing}
          onClose={() => setEditing(null)}
          onSaved={(issue) => {
            setEditing(null);
            if (issue) {
              setIssued(issue);
            }
            void reload();
          }}
        />
      ) : null}
      {inspected ? (
        <ProfileStats profile={inspected} onClose={() => setInspected(null)} />
      ) : null}
    </section>
  );
}
