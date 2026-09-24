import { useEffect, useState } from "react";

import { api, type OwnStats as Own, type Period, type ProfileStats as Stats } from "../api";
import { Chart, PERIODS, PROTOCOLS, Tile } from "../charts";
import { age, bytes, duration, stamp } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Footer, Pill } from "../tiles";

function NotRecognised({ source }: { source: string }) {
  return (
    <main className="own-centre">
      <div className="own-card">
        <span className="own-card-icon" aria-hidden="true">
          !
        </span>
        <h2>We don't recognise this connection</h2>
        <p>
          Stats are shown only for requests coming through the VPN tunnel. Turn on your
          AmneziaWG connection and reload the page.
        </p>
        <div className="own-seen">
          <span>Request came from</span>
          <span className="key">{source}</span>
        </div>
        <button type="button" className="action" onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    </main>
  );
}

function Sessions({ stats, span, now }: { stats: Stats; span: string; now: number }) {
  return (
    <div className="sessions">
      <div className="sessions-title">
        <h3>Recent sessions</h3>
        <span className="muted">
          {stats.session_count} in {span}
        </span>
      </div>
      <table className="sessions-table own-sessions">
        <thead>
          <tr>
            <th>Started</th>
            <th>Ended</th>
            <th>Duration</th>
            <th>Via</th>
            <th>Traffic</th>
          </tr>
        </thead>
        <tbody>
          {stats.sessions.length === 0 ? (
            <tr>
              <td colSpan={5} className="cell-empty">
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
                      now <span className="pill-dot" />
                    </span>
                  )}
                </td>
                <td>{duration(Math.round(length))}</td>
                <td>{PROTOCOLS[item.protocol] ?? item.protocol}</td>
                <td className="cell-name">{bytes(item.traffic)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function OwnStats() {
  const [period, setPeriod] = useState<Period>("7d");
  const [own, setOwn] = useState<Own | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let live = true;
    api
      .ownStats(period)
      .then((found) => {
        if (live) {
          setOwn(found);
          setProblem(null);
          setNow(Date.now());
        }
      })
      .catch((error: unknown) => {
        if (live) {
          setProblem(describe(error, "Could not load the stats"));
        }
      });
    return () => {
      live = false;
    };
  }, [period]);

  const span = PERIODS.find(([key]) => key === period)?.[1] ?? period;
  const stats = own?.stats ?? null;

  return (
    <>
      <header className="chrome">
        <div className="chrome-left">
          <div className="chrome-brand">
            <span className="chrome-logo" aria-hidden="true">
              A
            </span>
            <h1>awg-keeper</h1>
          </div>
          <nav className="chrome-tabs">
            <button type="button" className="active">
              Stats
            </button>
          </nav>
        </div>
      </header>

      {own && !stats ? (
        <NotRecognised source={own.source} />
      ) : (
        <main className="own">
          {own && stats ? (
            <div className="page-header">
              <div className="own-heading">
                <div className="own-name">
                  <h1>{own.name}</h1>
                  {stats.online ? (
                    <Pill tone="ok" dot>
                      online
                    </Pill>
                  ) : (
                    <Pill tone="idle" dot>
                      offline
                    </Pill>
                  )}
                </div>
                <div className="own-who">
                  <span>Recognised by your tunnel address</span>
                  <span className="key">{own.address}</span>
                  <span>&middot; {own.node}</span>
                </div>
              </div>
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
          ) : null}

          <Banner
            problem={problem}
            shown={detailShown}
            onToggle={() => setDetailShown((value) => !value)}
          />

          {stats ? (
            <>
              <div className="tiles">
                <Tile
                  label="Last connection"
                  value={stats.last_seen_at ? age(stats.last_seen_at, now) : "never"}
                  sub={stats.last_seen_at ? stamp(stats.last_seen_at) : "-"}
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
              <Sessions stats={stats} span={span} now={now} />
              <p className="own-footnote">
                Only your own profile is shown. The page is available while you are connected
                to the VPN.
              </p>
            </>
          ) : null}
        </main>
      )}
      <Footer />
    </>
  );
}
