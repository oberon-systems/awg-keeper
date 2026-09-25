import { useState } from "react";

import { api, type AgentInterface, type Obfuscation } from "../api";
import { Field } from "../fields";
import { describe, type Problem } from "../problem";
import { Banner } from "../tiles";

const GROUPS: { title: string; rows: string[][]; hint?: string; mono?: boolean }[] = [
  { title: "Junk packets", rows: [["Jc", "Jmin", "Jmax"]] },
  {
    title: "Padding",
    rows: [["S1", "S2", "S3", "S4"]],
    hint: "S1 + 56 must differ from S2. With header protection every S is 12 or more",
  },
  {
    title: "Headers",
    rows: [
      ["H1", "H2"],
      ["H3", "H4"],
    ],
    hint: "A number or an a-b range, above 4. The four ranges must not overlap",
    mono: true,
  },
  {
    title: "Timers",
    rows: [["RekeyAfterTime", "RekeyTimeout", "RejectAfterTime", "KeepaliveTimeout"]],
    hint: "Seconds, a number or an a-b range. Empty keeps the WireGuard default",
  },
];
const SIGNATURES = ["I1", "I2", "I3", "I4", "I5"];
const SWITCHES = ["RandomTrailers", "DisableCookies"];

function random(low: number, high: number): number {
  const drawn = new Uint32Array(1);
  crypto.getRandomValues(drawn);
  return low + (drawn[0] % (high - low + 1));
}

function headerKey(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

// One range per quarter of the space, in a shuffled order, so they never overlap.
function headers(): string[] {
  const band = Math.floor((2 ** 31 - 5) / 4);
  const order = [0, 1, 2, 3].sort(() => random(0, 1) - 0.5);
  return order.map((slot) => {
    const width = random(2 ** 16, 2 ** 24);
    const low = 5 + slot * band + random(0, band - width - 1);
    return `${low}-${low + width}`;
  });
}

function generated(trailers: boolean): Record<string, string> {
  const jmin = random(40, 90);
  let s1 = random(15, 150);
  let s2 = random(15, 150);
  while (s1 + 56 === s2) {
    s2 = random(15, 150);
  }
  const [s3, s4] = [random(12, 64), random(12, 32)];
  if (trailers) {
    s1 = s2 = random(15, 150);
  }
  const [h1, h2, h3, h4] = headers();
  const padding = random(2, 4);
  return {
    Jc: String(random(4, 12)),
    Jmin: String(jmin),
    Jmax: String(random(jmin + 400, 1000)),
    S1: String(s1),
    S2: String(s2),
    S3: String(trailers ? s1 : s3),
    S4: String(trailers ? s1 : s4),
    H1: h1,
    H2: h2,
    H3: h3,
    H4: h4,
    HeaderProtectionKey: headerKey(),
    ContentPaddingAddition: `${padding}-${padding + random(4, 8)}`,
  };
}

function text(value: unknown): string {
  return value === undefined || value === null ? "" : String(value);
}

export function summary(obfuscation: Record<string, unknown>): string {
  const parts = [obfuscation.HeaderProtectionKey ? "AmneziaWG 3.1" : "AmneziaWG"];
  if (obfuscation.Jc !== undefined) {
    parts.push(`Jc ${text(obfuscation.Jc)}`);
  }
  if (["H1", "H2", "H3", "H4"].some((key) => text(obfuscation[key]).includes("-"))) {
    parts.push("header ranges");
  }
  if (obfuscation.HeaderProtectionKey) {
    parts.push("header protection");
  }
  const signed = SIGNATURES.filter((key) => obfuscation[key]);
  if (signed.length) {
    parts.push(signed.join(" "));
  }
  return parts.length > 1 ? parts.join(" \u00b7 ") : "none: plain WireGuard";
}

export function ObfuscationForm({
  item,
  agent,
  onSaved,
  onClose,
}: {
  item: AgentInterface;
  agent: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const original = item.obfuscation;
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(original).map(([key, value]) => [key, text(value)])),
  );
  const [switches, setSwitches] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(SWITCHES.map((key) => [key, original[key] === "on"])),
  );
  const [confirming, setConfirming] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [busy, setBusy] = useState(false);

  const set = (key: string) => (value: string) =>
    setValues((current) => ({ ...current, [key]: value }));
  const field = (key: string, mono = false) => (
    <Field key={key} label={key} value={values[key] ?? ""} onChange={set(key)} mono={mono} />
  );

  function changes(): Obfuscation {
    const found: Obfuscation = {};
    for (const [key, value] of Object.entries(values)) {
      if (value.trim() !== "" && value.trim() !== text(original[key])) {
        found[key] = value.trim();
      }
    }
    for (const key of SWITCHES) {
      if (switches[key] !== (original[key] === "on")) {
        found[key] = switches[key];
      }
    }
    return found;
  }

  function ask(event: React.FormEvent) {
    event.preventDefault();
    setConfirming(true);
  }

  async function save() {
    if (item.id === null) {
      return;
    }
    setBusy(true);
    setProblem(null);
    setDetailShown(false);
    try {
      await api.setObfuscation(item.id, changes());
      onSaved();
    } catch (error) {
      setProblem(describe(error, "Could not save the obfuscation"));
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <div className="scrim">
      <form className="modal wide" onSubmit={ask}>
        <div className="modal-header">
          <div className="modal-heading">
            <h2>Obfuscation of {item.name}</h2>
            <p>AmneziaWG 3.1 &middot; the same on the interface and in every profile</p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <p className="notice">
          Saving changes the interface at once. Every profile issued on it stops connecting
          until it is rerolled.
        </p>

        {GROUPS.slice(0, 3).map((group) => (
          <section key={group.title} className="section-caps">
            <h3>{group.title}</h3>
            {group.rows.map((row) => (
              <div key={row.join()} className="field-row">
                {row.map((key) => field(key, group.mono))}
              </div>
            ))}
            {group.hint ? <span className="field-hint">{group.hint}</span> : null}
          </section>
        ))}

        <section className="section-caps">
          <h3>Header protection</h3>
          <div className="field-action">
            {field("HeaderProtectionKey", true)}
            <button
              type="button"
              className="secondary"
              onClick={() => set("HeaderProtectionKey")(headerKey())}
            >
              Generate
            </button>
          </div>
          <div className="field-row">
            {field("ContentPaddingAddition")}
            {field("MaxHandshakeAttempts")}
          </div>
          <span className="field-hint">
            A key cannot be removed, only replaced. Ranges are a-b
          </span>
        </section>

        {GROUPS.slice(3).map((group) => (
          <section key={group.title} className="section-caps">
            <h3>{group.title}</h3>
            {group.rows.map((row) => (
              <div key={row.join()} className="field-row">
                {row.map((key) => field(key))}
              </div>
            ))}
            <span className="field-hint">{group.hint}</span>
          </section>
        ))}

        <section className="section-caps">
          <h3>Signature packets</h3>
          {field("I1", true)}
          <div className="field-row">
            {field("I2", true)}
            {field("I3", true)}
          </div>
          <div className="field-row">
            {field("I4", true)}
            {field("I5", true)}
          </div>
          <span className="field-hint">
            Tags: &lt;b 0x...&gt; &lt;r n&gt; &lt;rc n&gt; &lt;rd n&gt; &lt;t&gt;. &lt;c&gt; is
            refused by amneziawg-go
          </span>
        </section>

        <section className="section-caps">
          <h3>Switches</h3>
          <div className="field-row">
            {SWITCHES.map((key) => (
              <label key={key} className="check">
                <input
                  type="checkbox"
                  checked={switches[key]}
                  onChange={(event) =>
                    setSwitches((current) => ({ ...current, [key]: event.target.checked }))
                  }
                />
                <span>
                  <span className="check-title">
                    {key === "RandomTrailers" ? "Random trailers" : "Disable cookies"}
                  </span>
                  <span className="check-hint">
                    {key === "RandomTrailers"
                      ? "Random bytes after every packet"
                      : "No cookie reply under load"}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </section>

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((shown) => !shown)}
        />

        <div className="modal-footer">
          <button
            type="button"
            className="secondary footer-start"
            onClick={() =>
              setValues((current) => ({ ...current, ...generated(switches.RandomTrailers) }))
            }
          >
            Generate all
          </button>
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            className="action"
            disabled={Object.keys(changes()).length === 0}
          >
            Save
          </button>
        </div>
      </form>

      {confirming ? (
        <div className="scrim">
          <div className="modal narrow" role="alertdialog" aria-modal="true">
            <div className="modal-header">
              <div className="modal-heading">
                <h2>Are you sure?</h2>
                <p>
                  Save the obfuscation of {item.name} on {agent}. The {item.peers} profiles
                  issued on it stop connecting until they are rerolled
                </p>
              </div>
              <button
                type="button"
                className="modal-close"
                aria-label="Close"
                onClick={() => setConfirming(false)}
              >
                &#x2715;
              </button>
            </div>
            <div className="modal-footer">
              <button type="button" className="secondary" onClick={() => setConfirming(false)}>
                No
              </button>
              <button
                type="button"
                className="action wide"
                disabled={busy}
                onClick={() => void save()}
              >
                Yes
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
