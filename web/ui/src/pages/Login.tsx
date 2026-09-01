import { useState } from "react";

import { api } from "../api";

export function Login({ onSignedIn }: { onSignedIn: (user: string) => void }) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem("");
    try {
      const identity = await api.login(user, password);
      onSignedIn(identity.user);
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="centre">
      <form className="card" onSubmit={(event) => void submit(event)}>
        <h1>awg-keeper</h1>
        <label>
          User
          <input
            value={user}
            autoComplete="username"
            onChange={(event) => setUser(event.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {problem ? <p className="problem">{problem}</p> : null}
        <button type="submit" disabled={busy}>
          Sign in
        </button>
      </form>
    </main>
  );
}
