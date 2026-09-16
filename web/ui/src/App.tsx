import { useEffect, useState } from "react";

import { api } from "./api";
import { Agents } from "./pages/Agents";
import { Login } from "./pages/Login";
import { Profiles } from "./pages/Profiles";

export function App() {
  const [user, setUser] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<"profiles" | "agents">("profiles");

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
      <header>
        <h1>awg-keeper</h1>
        <nav className="tabs">
          <button
            type="button"
            className={tab === "profiles" ? "active" : ""}
            onClick={() => setTab("profiles")}
          >
            Profiles
          </button>
          <button
            type="button"
            className={tab === "agents" ? "active" : ""}
            onClick={() => setTab("agents")}
          >
            Agents
          </button>
        </nav>
        <div className="who">
          <span>{user}</span>
          <button
            type="button"
            onClick={() => {
              void api.logout().then(() => setUser(null));
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main>
        {tab === "profiles" ? <Profiles /> : <Agents />}
      </main>
    </>
  );
}
