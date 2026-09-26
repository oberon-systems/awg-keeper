import { useState } from "react";

import { api, type Profile, type ProfileReissue } from "../api";
import { generateKeyPair, newUuid } from "../keys";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";
import { type Issue, issueOf } from "./IssuedConfig";
import { Option } from "./ProfileNew";

export function ProfileReroll({
  profile,
  onClose,
  onIssued,
}: {
  profile: Profile;
  onClose: () => void;
  onIssued: (issue: Issue) => void;
}) {
  const [awg, setAwg] = useState(profile.peer !== null);
  const [xray, setXray] = useState(profile.xray !== null && profile.peer === null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  async function reroll() {
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    try {
      // New keys for the chosen halves, generated here like the first ones.
      const pair = awg ? generateKeyPair() : null;
      const body: ProfileReissue = {};
      if (pair) {
        body.awg = { public_key: pair.publicKey };
      }
      if (xray) {
        body.xray = { id: newUuid() };
      }
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
          Pick what to reissue. The chosen config stops working; the name, the address and
          the stats are kept.
        </p>
        <Option
          title="AmneziaWG"
          hint={
            profile.peer
              ? "New key pair; the .conf and the Amnezia key are shown once"
              : "The profile has no AmneziaWG peer"
          }
          checked={awg}
          disabled={!profile.peer}
          onToggle={setAwg}
        />
        <Option
          title="Xray (VLESS + Reality)"
          hint={
            profile.xray
              ? "New UUID; the vless link is shown once"
              : "The profile has no Xray client"
          }
          checked={xray}
          disabled={!profile.xray}
          onToggle={setXray}
        />
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
            disabled={busy || !(awg || xray)}
            onClick={() => void reroll()}
          >
            Yes
          </button>
        </div>
      </div>
    </div>
  );
}
