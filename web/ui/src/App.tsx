import { useEffect, useState } from "react";

import { api } from "./api";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Profiles } from "./pages/Profiles";

export function App() {
  const [user, setUser] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<"dashboard" | "profiles">("dashboard");

  useEffect(() => {
    api
      .me()
      .then((identity) => setUser(identity.user))
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return <main className="centre">Loading</main>;
  }

  if (!user) {
    return <Login onSignedIn={setUser} />;
  }

  return (
    <>
      <header className="chrome">
        <div className="chrome-left">
          <div className="chrome-brand">
            <span className="chrome-logo" aria-hidden="true">
              A
            </span>
            <h1>awg-keeper</h1>
          </div>
          <nav className="chrome-tabs">
            <button
              type="button"
              className={tab === "dashboard" ? "active" : ""}
              onClick={() => setTab("dashboard")}
            >
              Dashboard
            </button>
            <button
              type="button"
              className={tab === "profiles" ? "active" : ""}
              onClick={() => setTab("profiles")}
            >
              Profiles
            </button>
          </nav>
        </div>
        <div className="chrome-who">
          <span className="chrome-avatar" aria-hidden="true">
            {user.slice(0, 1).toUpperCase()}
          </span>
          <span className="chrome-user">{user}</span>
          <button
            type="button"
            className="chrome-signout"
            onClick={() => {
              void api.logout().then(() => setUser(null));
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flush">
        {tab === "dashboard" ? <Dashboard /> : <Profiles />}
      </main>
    </>
  );
}
