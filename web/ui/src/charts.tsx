import { useState } from "react";

import type { Period, ProfileStats as Stats } from "./api";
import { bytes, day, stamp } from "./format";

export const PERIODS: [Period, string][] = [
  ["24h", "24 h"],
  ["7d", "7 days"],
  ["30d", "30 days"],
];
export const PROTOCOLS: Record<string, string> = { awg: "AmneziaWG", xray: "Xray" };

export function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
      <span className="tile-sub">{sub}</span>
    </div>
  );
}

export function niceMax(value: number): number {
  if (value <= 0) {
    return 1024 * 1024;
  }
  const step = 2 ** Math.floor(Math.log2(value));
  return Math.ceil(value / step) * step;
}

export function Chart({ stats, hourly, now }: { stats: Stats; hourly: boolean; now: number }) {
  const [shown, setShown] = useState({ rx: true, tx: true });
  const totals = stats.buckets.map(
    (bucket) => (shown.rx ? bucket.rx : 0) + (shown.tx ? bucket.tx : 0),
  );
  const peak = Math.max(0, ...totals);
  const top = niceMax(peak);
  const peakIndex = totals.indexOf(peak);
  const dense = stats.buckets.length > 10;
  const labelled = hourly ? 3 : dense ? 5 : 1;
  const current = (start: string) =>
    now - new Date(start).getTime() < (hourly ? 3600_000 : 86400_000);
  const series = (key: "rx" | "tx", label: string, tone: string) => (
    <button
      type="button"
      className={shown[key] ? "series" : "series off"}
      aria-pressed={shown[key]}
      onClick={() => setShown((value) => ({ ...value, [key]: !value[key] }))}
    >
      <span className={`swatch ${tone}`} /> {label}
    </button>
  );

  return (
    <div className="chart">
      <div className="chart-header">
        <span className="chart-title">Traffic per {hourly ? "hour" : "day"}</span>
        <span className="chart-legend">
          {series("rx", "Received", "received")}
          {series("tx", "Sent", "sent")}
        </span>
      </div>
      <div className="plot">
        <div className="plot-grid">
          {[1, 0.75, 0.5, 0.25, 0].map((share) => (
            <div key={share} className="plot-line">
              <span>{share ? bytes(top * share) : "0"}</span>
            </div>
          ))}
        </div>
        <div className="plot-bars">
          {stats.buckets.map((bucket, index) => {
            const total = totals[index];
            const pinned = !dense || (index === peakIndex && peak > 0);
            return (
              <div key={bucket.start} className="plot-column">
                <div className="plot-stack">
                  {total > 0 ? (
                    <div className="plot-fill" style={{ height: `${(total / top) * 100}%` }}>
                      <span className={pinned ? "plot-total" : "plot-total hover"}>
                        {bytes(total)}
                      </span>
                      {shown.tx && bucket.tx > 0 ? (
                        <div className="bar sent" style={{ flexGrow: bucket.tx }} />
                      ) : null}
                      {shown.rx && bucket.rx > 0 ? (
                        <div className="bar received" style={{ flexGrow: bucket.rx }} />
                      ) : null}
                    </div>
                  ) : null}
                </div>
                <span className={current(bucket.start) ? "plot-day current" : "plot-day"}>
                  {index % labelled === 0 || current(bucket.start)
                    ? hourly
                      ? stamp(bucket.start).slice(-5)
                      : day(bucket.start, false)
                    : ""}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
