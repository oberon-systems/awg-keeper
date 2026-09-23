import { useState } from "react";

import { api, type Profile } from "../api";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";

export function ProfileDelete({
  profile,
  onClose,
  onDeleted,
}: {
  profile: Profile;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  async function remove() {
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    try {
      await api.deleteProfile(profile.id);
      onDeleted();
    } catch (error) {
      setProblem(describe(error, "Could not delete the profile"));
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
            <p>Delete profile {profile.name}</p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>
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
            className="danger wide"
            disabled={busy}
            onClick={() => void remove()}
          >
            Yes
          </button>
        </div>
      </div>
    </div>
  );
}
