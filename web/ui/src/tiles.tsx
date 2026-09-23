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
