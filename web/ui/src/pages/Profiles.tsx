import { useCallback, useEffect, useState } from "react";

import { api, type Interface, type Issued, type Profile } from "../api";
import { IssuedConfig } from "./IssuedConfig";
import { fillConfig, generateKeyPair } from "../keys";

export function Profiles() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [interfaces, setInterfaces] = useState<Interface[]>([]);
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

  useEffect(() => {
    void api.interfaces().then((found) => {
      setInterfaces(found);
      setChosen((current) => current ?? found[0]?.id ?? null);
    });
    void reload();
  }, [reload]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (chosen === null) {
      setProblem("there is no interface to issue against");
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
          Interface
          <select
            value={chosen ?? ""}
            onChange={(event) => setChosen(Number(event.target.value))}
          >
            {interfaces.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy || !name}>
          Add profile
        </button>
      </form>

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
