import { useState } from "react";

import { api, type Profile, type ProfileReissue } from "../api";
import { generateKeyPair } from "../keys";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";
import { type Issue, issueOf } from "./IssuedConfig";

export function ProfileReroll({
  profile,
  onClose,
  onIssued,
}: {
  profile: Profile;
  onClose: () => void;
  onIssued: (issue: Issue) => void;
}) {
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  async function reroll() {
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    // New keys for every half the profile owns, generated here like the first ones.
    const pair = profile.peer ? generateKeyPair() : null;
    const body: ProfileReissue = {};
    if (pair) {
      body.awg = { public_key: pair.publicKey };
    }
    if (profile.xray) {
      body.xray = { id: crypto.randomUUID() };
    }
    try {
      const answer = await api.reissueProfile(profile.id, body);
      onIssued(await issueOf(answer, pair));
    } catch (error) {
      setProblem(describe(error, "Could not reroll the profile"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scrim">
      <div className="modal narrow" role="alertdialog" aria-modal="true">
        <div className="modal-header">
          <div className="modal-heading">
            <h2>Are you sure?</h2>
            <p>Reroll profile {profile.name}</p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>
        <p className="modal-text">
          A new configuration will be issued. The current one stops working; the name, the
          address and the stats are kept.
        </p>
        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((value) => !value)}
        />
        <div className="modal-footer">
          <button type="button" className="secondary" onClick={onClose}>
            No
          </button>
          <button
            type="button"
            className="action wide"
            disabled={busy}
            onClick={() => void reroll()}
          >
            Yes
          </button>
        </div>
      </div>
    </div>
  );
}
