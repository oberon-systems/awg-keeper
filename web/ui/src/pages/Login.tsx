import { useState } from "react";

import { ApiError, api } from "../api";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";

// A refused sign in says the same thing whichever half was wrong.
function describeSignIn(error: unknown): Problem {
  if (error instanceof ApiError && error.status === 401) {
    return describe(error, "Wrong user or password");
  }
  return describe(error);
}

export function Login({ onSignedIn }: { onSignedIn: (user: string) => void }) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    try {
      const identity = await api.login(user, password);
      onSignedIn(identity.user);
    } catch (error) {
      setProblem(describeSignIn(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <form className="auth-card" onSubmit={(event) => void submit(event)}>
        <div className="auth-header">
          <div className="auth-brand">
            <span className="auth-logo" aria-hidden="true">
              A
            </span>
            <h1>awg-keeper</h1>
          </div>
          <p className="auth-subtitle">
            Sign in to manage AmneziaWG and Xray nodes
          </p>
        </div>

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((shown) => !shown)}
        />

        <label className="auth-field">
          User
          <input
            value={user}
            autoComplete="username"
            placeholder="Enter user"
            onChange={(event) => setUser(event.target.value)}
          />
        </label>
        <label className="auth-field">
          Password
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            placeholder="Enter password"
            className={problem ? "wrong" : undefined}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button type="submit" className="auth-submit" disabled={busy}>
          Sign in
        </button>
      </form>
      <p className="auth-footnote">Credentials are pre-set on the panel host</p>
    </main>
  );
}
