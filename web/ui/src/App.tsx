import { useEffect, useState } from "react";

import { api } from "./api";
import { Login } from "./pages/Login";
import { Profiles } from "./pages/Profiles";
import { Status } from "./pages/Status";

export function App() {
  const [user, setUser] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<"status" | "profiles">("status");

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
            className={tab === "status" ? "active" : ""}
            onClick={() => setTab("status")}
          >
            Status
          </button>
          <button
            type="button"
            className={tab === "profiles" ? "active" : ""}
            onClick={() => setTab("profiles")}
          >
            Profiles
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
        {tab === "status" ? <Status /> : <Profiles />}
      </main>
    </>
  );
}
