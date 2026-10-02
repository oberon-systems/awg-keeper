import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { OwnStats } from "./pages/OwnStats";
import "./styles.css";

const host = document.getElementById("root");
if (host) {
  createRoot(host).render(
    <StrictMode>
      <OwnStats />
    </StrictMode>,
  );
}
