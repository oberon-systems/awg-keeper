import { useEffect, useState } from "react";

import { api, type Period, type Profile, type ProfileStats as Stats } from "../api";
import { Chart, PERIODS, PROTOCOLS, Tile } from "../charts";
import { age, bytes, day, duration, stamp } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Pill } from "../tiles";

function seen(protocol: string): string {
  return protocol === "awg" ? "handshake" : "traffic";
}

export function ProfileStats({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const [period, setPeriod] = useState<Period>("7d");
  const [stats, setStats] = useState<Stats | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let live = true;
    api
      .profileStats(profile.id, period)
      .then((found) => {
        if (live) {
          setStats(found);
          setProblem(null);
          setNow(Date.now());
        }
      })
      .catch((error: unknown) => {
        if (live) {
          setProblem(describe(error, "Could not load the profile stats"));
        }
      });
    return () => {
      live = false;
    };
  }, [profile.id, period]);

  const span = PERIODS.find(([key]) => key === period)?.[1] ?? period;
  const latest = stats?.protocols
    .filter((item) => item.last_seen_at)
    .sort((a, b) => (b.last_seen_at ?? "").localeCompare(a.last_seen_at ?? ""))[0];
  const subtitle = [profile.node, profile.note, `created ${day(profile.created_at)}`]
    .filter(Boolean)
    .join(" \u00b7 ");

  return (
    <div className="scrim">
      <div className="modal stats-modal" role="dialog" aria-modal="true">
        <div className="modal-header">
          <div className="modal-heading">
            <h2>{profile.name}</h2>
            <p>{subtitle}</p>
          </div>
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &#x2715;
          </button>
        </div>

        <div className="controls">
          {stats?.online && latest ? (
            <Pill tone="ok" dot>
              online &middot; {seen(latest.protocol)} {age(latest.last_seen_at, now)}
            </Pill>
          ) : (
            <Pill tone="idle" dot>
              offline
              {stats?.last_seen_at ? ` \u00b7 seen ${age(stats.last_seen_at, now)}` : ""}
            </Pill>
          )}
          <div className="segmented" role="tablist">
            {PERIODS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={key === period}
                className={key === period ? "active" : undefined}
                onClick={() => setPeriod(key)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {stats ? (
          <>
            <div className="tiles">
              <Tile
                label="Last connection"
                value={stats.last_seen_at ? age(stats.last_seen_at, now) : "never"}
                sub={
                  stats.last_seen_at
                    ? [stamp(stats.last_seen_at), stats.last_source]
                        .filter(Boolean)
                        .join(" \u00b7 ")
                    : "-"
                }
              />
              <Tile
                label={`Traffic, ${span}`}
                value={bytes(stats.rx + stats.tx)}
                sub={`\u2193 ${bytes(stats.rx)} received \u00b7 \u2191 ${bytes(stats.tx)} sent`}
              />
              <Tile
                label={`Connected, ${span}`}
                value={duration(stats.connected_seconds)}
                sub={`${stats.session_count} sessions`}
              />
            </div>

            <Chart stats={stats} hourly={period === "24h"} now={now} />

            <div className="protocols">
              {stats.protocols.map((item) => (
                <div key={item.protocol} className="protocol">
                  <div className="protocol-head">
                    <span className="cell-name">{PROTOCOLS[item.protocol] ?? item.protocol}</span>
                    <span className="key">{item.key}</span>
                  </div>
                  <div className="protocol-values">
                    <span>&#x2193; {bytes(item.rx)}</span>
                    <span>&#x2191; {bytes(item.tx)}</span>
                  </div>
                  <span className="muted">
                    last {seen(item.protocol)}{" "}
                    {item.last_seen_at ? age(item.last_seen_at, now) : "never"}
                  </span>
                </div>
              ))}
            </div>

            <div className="sessions">
              <div className="sessions-title">
                <h3>Recent sessions</h3>
                <span className="muted">
                  {stats.session_count} in {span}
                </span>
              </div>
              <table className="sessions-table">
                <thead>
                  <tr>
                    <th>Started</th>
                    <th>Ended</th>
                    <th>Duration</th>
                    <th>Via</th>
                    <th>From</th>
                    <th>Traffic</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.sessions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="cell-empty">
                        No session in {span}.
                      </td>
                    </tr>
                  ) : null}
                  {stats.sessions.map((item) => {
                    const end = item.ended_at ? new Date(item.ended_at).getTime() : now;
                    const length = Math.max(0, (end - new Date(item.started_at).getTime()) / 1000);
                    return (
                      <tr key={item.started_at + item.protocol}>
                        <td>{stamp(item.started_at)}</td>
                        <td>
                          {item.ended_at ? (
                            stamp(item.ended_at)
                          ) : (
                            <span className="now">
                              <span className="pill-dot" /> now
                            </span>
                          )}
                        </td>
                        <td>{duration(Math.round(length))}</td>
                        <td>{PROTOCOLS[item.protocol] ?? item.protocol}</td>
                        <td className="key">{item.source ?? "-"}</td>
                        <td className="cell-name">{bytes(item.traffic)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        ) : null}

        <Banner
          problem={problem}
          shown={detailShown}
          onToggle={() => setDetailShown((value) => !value)}
        />

        <div className="modal-footer spread">
          <span className="muted">Sessions are derived from handshakes sampled every 30s</span>
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
