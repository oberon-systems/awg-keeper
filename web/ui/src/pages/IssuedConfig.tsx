import { useEffect, useState } from "react";
import QRCode from "qrcode";

import type { Profile } from "../api";
import { stamp } from "../format";

export interface Issue {
  profile: Profile;
  config: string | null;
  link: string | null;
}

type Protocol = "awg" | "xray";

function Segments<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: [T, string][];
  onChange: (value: T) => void;
}) {
  return (
    <div className="segmented" role="tablist">
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={key === value}
          className={key === value ? "active" : undefined}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Highlighted({ text }: { text: string }) {
  return (
    <pre className="text-view-body">
      {text.split("\n").map((line, index) => (
        <span key={index} className={line.startsWith("[") ? "section" : undefined}>
          {line}
          {"\n"}
        </span>
      ))}
    </pre>
  );
}

function save(name: string, text: string) {
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

// The only moment this configuration exists anywhere: the private key was
// generated in this tab and is not stored by the panel. Closing the dialog
// loses it, and the only way back is to issue the profile again.
export function IssuedConfig({ issue, onClose }: { issue: Issue; onClose: () => void }) {
  const { profile, config, link } = issue;
  const [protocol, setProtocol] = useState<Protocol>(config ? "awg" : "xray");
  const [view, setView] = useState<"qr" | "text">("qr");
  const [image, setImage] = useState("");

  const text = (protocol === "awg" ? config : link) ?? "";
  const file = `${profile.name}.${protocol === "awg" ? "conf" : "txt"}`;

  useEffect(() => {
    if (text) {
      void QRCode.toDataURL(text, { width: 528, margin: 1 }).then(setImage);
    }
  }, [text]);

  const issued: [Protocol, string][] = [];
  if (config) {
    issued.push(["awg", "AmneziaWG"]);
  }
  if (link) {
    issued.push(["xray", "Xray"]);
  }

  const endpoint =
    protocol === "awg"
      ? /^Endpoint = (.*)$/m.exec(text)?.[1]
      : /@([^?]+)\?/.exec(text)?.[1];
  const details =
    protocol === "awg"
      ? [file, profile.peer?.assigned_ip, endpoint]
      : [profile.name, profile.xray?.inbound, endpoint];

  return (
    <div className="scrim">
      <div className="modal wide" role="dialog" aria-modal="true">
        <div className="modal-header">
          <div className="modal-heading">
            <h2>{profile.name}</h2>
            <p>
              Created on {profile.node ?? "-"} &middot; {stamp(profile.created_at, true)} &middot;{" "}
              {issued.map(([, label]) => label).join(" + ")}
            </p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <p className="notice">
          {protocol === "awg"
            ? "This is the only time this configuration can be taken. The private key was generated in your browser and the panel never saw it."
            : "This is the only time this link can be taken. The client id was generated in your browser and the panel never stores it."}
        </p>

        <div className="controls">
          <Segments value={protocol} options={issued} onChange={setProtocol} />
          <Segments
            value={view}
            options={[
              ["qr", "QR code"],
              ["text", "Text"],
            ]}
            onChange={setView}
          />
        </div>

        {view === "qr" ? (
          <div className="qr-view">
            {image ? <img src={image} alt="QR code" width={264} height={264} /> : null}
            <span className="qr-caption">
              {protocol === "awg"
                ? "Scan with the AmneziaVPN or AmneziaWG app"
                : "Scan with a VLESS client: v2rayNG, Hiddify or Streisand"}
            </span>
            <span className="key">{details.filter(Boolean).join(" \u00b7 ")}</span>
          </div>
        ) : (
          <div className="text-view">
            <div className="text-view-bar">
              <span className="key">{file}</span>
              <button
                type="button"
                className="small"
                onClick={() => void navigator.clipboard.writeText(text)}
              >
                Copy
              </button>
            </div>
            <Highlighted text={text} />
          </div>
        )}

        <div className="modal-footer spread">
          <div className="modal-footer-group">
            <button type="button" className="secondary" onClick={() => save(file, text)}>
              Download .{protocol === "awg" ? "conf" : "txt"}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => void navigator.clipboard.writeText(text)}
            >
              Copy
            </button>
          </div>
          <button type="button" className="action" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
