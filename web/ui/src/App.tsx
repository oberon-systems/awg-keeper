import { useEffect, useState } from "react";

import { api } from "./api";
import { Login } from "./pages/Login";
import { Profiles } from "./pages/Profiles";

export function App() {
  const [user, setUser] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

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
        <Profiles />
      </main>
    </>
  );
}
