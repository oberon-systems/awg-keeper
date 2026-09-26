import { Fragment, type ReactNode } from "react";

import type { Problem } from "./problem";

export type Tone = "ok" | "warn" | "down" | "idle";

export interface Part {
  text: string;
  tone?: Tone;
}

export function counted(parts: [number, string, Tone][]): Part[] {
  return parts
    .filter(([count]) => count > 0)
    .map(([count, text, tone]) => ({ text: `${count} ${text}`, tone }));
}

export function toneOf(status: string): Tone {
  if (status === "up") {
    return "ok";
  }
  if (status === "degraded") {
    return "warn";
  }
  return status === "down" ? "down" : "idle";
}

export function Pill({
  tone,
  dot,
  children,
}: {
  tone: Tone;
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`pill pill-${tone}`}>
      {dot ? <span className="pill-dot" /> : null}
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  parts,
}: {
  label: string;
  value: string;
  parts: Part[];
}) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      <span className="stat-caption">
        {parts.map((part, index) => (
          <Fragment key={index}>
            {index ? <span aria-hidden="true">&middot;</span> : null}
            <span className={part.tone}>{part.text}</span>
          </Fragment>
        ))}
      </span>
    </div>
  );
}

export function Banner({
  problem,
  shown,
  onToggle,
}: {
  problem: Problem | null;
  shown: boolean;
  onToggle: () => void;
}) {
  if (!problem) {
    return null;
  }
  return (
    <div className="problem-banner" role="alert">
      <div className="problem-banner-summary">
        <span>{problem.message}</span>
        <button
          type="button"
          className="problem-banner-toggle"
          aria-expanded={shown}
          aria-label="Show what the panel answered"
          onClick={onToggle}
        >
          i
        </button>
      </div>
      {shown ? <p className="problem-banner-detail">{problem.detail}</p> : null}
    </div>
  );
}

// The mark is mark-github from Octicons, MIT licensed.
const GITHUB_MARK =
  "M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z";

export function Footer() {
  return (
    <footer className="footer">
      <a
        href="https://github.com/oberon-systems/awg-keeper"
        target="_blank"
        rel="noopener noreferrer"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d={GITHUB_MARK} />
        </svg>
        awg-keeper
      </a>
    </footer>
  );
}

export function Refresh({
  busy,
  onClick,
  label,
}: {
  busy: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      className={busy ? "icon-button spinning" : "icon-button"}
      aria-label={label}
      title={label}
      disabled={busy}
      onClick={onClick}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 12a9 9 0 1 1-2.64-6.36" />
        <path d="M21 3v6h-6" />
      </svg>
    </button>
  );
}
