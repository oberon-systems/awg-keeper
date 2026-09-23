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
  const totals = stats.buckets.map((bucket) => bucket.rx + bucket.tx);
  const peak = Math.max(0, ...totals);
  const top = niceMax(peak);
  const peakIndex = totals.indexOf(peak);
  const labelled = hourly ? 3 : stats.buckets.length > 10 ? 5 : 1;
  const current = (start: string) =>
    now - new Date(start).getTime() < (hourly ? 3600_000 : 86400_000);

  return (
    <div className="chart">
      <div className="chart-header">
        <span className="chart-title">Traffic per {hourly ? "hour" : "day"}</span>
        <span className="chart-legend">
          <span className="swatch received" /> Received
          <span className="swatch sent" /> Sent
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
          {stats.buckets.map((bucket, index) => (
            <div key={bucket.start} className="plot-column">
              <div className="plot-stack">
                {index === peakIndex && peak > 0 ? (
                  <span className="plot-peak">{bytes(peak)}</span>
                ) : null}
                <div className="bar sent" style={{ height: `${(bucket.tx / top) * 100}%` }} />
                <div
                  className="bar received"
                  style={{ height: `${(bucket.rx / top) * 100}%` }}
                />
              </div>
              <span className={current(bucket.start) ? "plot-day current" : "plot-day"}>
                {index % labelled === 0 || current(bucket.start)
                  ? hourly
                    ? stamp(bucket.start).slice(-5)
                    : day(bucket.start, false)
                  : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
