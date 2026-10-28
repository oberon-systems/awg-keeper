import { useEffect, useState } from "react";

import {
  api,
  type AgentInterface,
  type ConfigPreview,
  type ConfigVersion,
  type PortableConfig,
} from "../api";
import { stamp } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Pill, type Tone } from "../tiles";
import { fieldLabel, PreviewDialog } from "./ConfigPreview";

const SOURCES: Record<ConfigVersion["source"], [string, Tone]> = {
  baseline: ["baseline", "idle"],
  import: ["import", "idle"],
  edit: ["edit", "idle"],
  rollback: ["rollback", "accent"],
};

const WORDS: Record<ConfigVersion["source"], string> = {
  baseline: "Baseline of",
  import: "Imported",
  edit: "Edited",
  rollback: "Rolled back",
};

const SETTINGS = ["dns", "mtu", "client_allowed_ips", "keepalive"] as const;

function changed(config: PortableConfig, older: PortableConfig | undefined): string {
  if (!older) {
    return "\u2014";
  }
  const names = new Set([...Object.keys(config.obfuscation), ...Object.keys(older.obfuscation)]);
  const found = [...names].filter((name) => config.obfuscation[name] !== older.obfuscation[name]);
  for (const field of SETTINGS) {
    if (config[field] !== older[field]) {
      found.push(fieldLabel(field));
    }
  }
  return found.join(", ") || "\u2014";
}

function note(item: ConfigVersion): string | null {
  if (item.source === "rollback") {
    return `back to version ${item.rolled_back_from ?? "?"}`;
  }
  if (item.source === "import") {
    return "taken from the host once";
  }
  return item.source === "baseline" ? "what the panel held on upgrade" : null;
}

export function ConfigHistory({
  item,
  onSaved,
  onClose,
}: {
  item: AgentInterface;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [versions, setVersions] = useState<ConfigVersion[]>([]);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [target, setTarget] = useState<ConfigVersion | null>(null);
  const [preview, setPreview] = useState<ConfigPreview | null>(null);
  const [applyProblem, setApplyProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (item.id === null) {
      return;
    }
    let live = true;
    api
      .configVersions(item.id)
      .then((found) => {
        if (live) {
          setVersions(found);
        }
      })
      .catch((error: unknown) => {
        if (live) {
          setProblem(describe(error, "Could not load the history"));
        }
      });
    return () => {
      live = false;
    };
  }, [item.id]);

  function open(version: ConfigVersion) {
    if (item.id === null) {
      return;
    }
    setTarget(version);
    setPreview(null);
    setApplyProblem(null);
    api
      .previewConfig(item.id, { version: version.version })
      .then(setPreview)
      .catch((error: unknown) => setApplyProblem(describe(error, "Could not preview it")));
  }

  async function apply() {
    if (item.id === null || target === null) {
      return;
    }
    setBusy(true);
    setApplyProblem(null);
    try {
      await api.applyVersion(item.id, target.version);
      onSaved();
    } catch (error) {
      setApplyProblem(describe(error, `${item.name} did not take version ${target.version}`));
    } finally {
      setBusy(false);
    }
  }

  const current = versions.find((version) => version.current);
  const twin = versions.find(
    (version) => !version.current && current && version.digest === current.digest,
  );

  return (
    <div className="scrim">
      <div className="modal history-modal">
        <div className="modal-header">
          <div className="modal-heading">
            <h2>History of {item.name}</h2>
            <p>
              Obfuscation and client settings, newest first. Key, port and address belong to
              the host and are not kept here.
            </p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((shown) => !shown)}
        />

        <div className="diff">
          <table className="history-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>When</th>
                <th>By</th>
                <th>Source</th>
                <th>Changed</th>
                <th>Digest</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {versions.length === 0 && !problem ? (
                <tr>
                  <td colSpan={7} className="cell-empty">
                    No version recorded yet.
                  </td>
                </tr>
              ) : null}
              {versions.map((version, index) => {
                const [label, tone] = SOURCES[version.source];
                const extra = note(version);
                return (
                  <tr
                    key={version.version}
                    className={version.current ? "history-current" : undefined}
                  >
                    <td className="cell-name">v{version.version}</td>
                    <td>{stamp(version.created_at, true)}</td>
                    <td className={version.author ? undefined : "muted"}>
                      {version.author ?? "\u2014"}
                    </td>
                    <td>
                      <Pill tone={tone}>{label}</Pill>
                      {extra ? <div className="muted">{extra}</div> : null}
                    </td>
                    <td>{changed(version.config, versions[index + 1]?.config)}</td>
                    <td className="key">{version.digest.slice(0, 8)}</td>
                    <td>
                      {version.current ? (
                        <Pill tone="ok">current</Pill>
                      ) : (
                        <button type="button" className="small" onClick={() => open(version)}>
                          Preview
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {current && twin ? (
          <p className="modal-text">
            v{current.version} and v{twin.version} share a digest: the same config, so profiles
            issued under v{twin.version} need no reroll.
          </p>
        ) : null}

        <div className="modal-footer">
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      {target ? (
        <PreviewDialog
          title={`Roll ${item.name} back to version ${target.version}`}
          subtitle={`${WORDS[target.source]} ${stamp(target.created_at, true)}${
            target.author ? ` by ${target.author}` : ""
          }. The agent applies it first; the panel keeps it only once the interface has it.`}
          preview={preview}
          problem={applyProblem}
          busy={busy}
          applyLabel={`Apply version ${target.version}`}
          onApply={() => void apply()}
          onCancel={() => setTarget(null)}
        />
      ) : null}
    </div>
  );
}
