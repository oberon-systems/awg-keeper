import { useState } from "react";

import { ApiError, api } from "../api";

interface Problem {
  message: string;
  detail: string;
}

// A refused sign in says the same thing whichever half was wrong; the status
// and what the panel actually answered stay behind the detail toggle.
function describe(error: unknown): Problem {
  if (error instanceof ApiError) {
    return {
      message:
        error.status === 401 ? "Wrong user or password" : error.message,
      detail: `${error.status} - ${error.message}`,
    };
  }
  return {
    message: "Could not reach the panel",
    detail: error instanceof Error ? error.message : String(error),
  };
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
      setProblem(describe(error));
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

        {problem ? (
          <div className="auth-problem" role="alert">
            <div className="auth-problem-summary">
              <span>{problem.message}</span>
              <button
                type="button"
                className="auth-detail-toggle"
                aria-expanded={detailShown}
                aria-label="Show what the panel answered"
                onClick={() => setDetailShown((shown) => !shown)}
              >
                i
              </button>
            </div>
            {detailShown ? (
              <p className="auth-problem-detail">{problem.detail}</p>
            ) : null}
          </div>
        ) : null}

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
