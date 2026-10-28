import { useEffect, useState } from "react";

import { api, type Backup, type BackupSchedule } from "../api";
import { Field } from "../fields";
import { bytes } from "../format";
import { describe, type Problem } from "../problem";
import { Banner, Pill, type Tone } from "../tiles";

type Mode = "hourly" | "daily" | "weekly" | "monthly";

interface Form {
  mode: Mode | null;
  minute: string;
  time: string;
  days: number[];
  day: string;
}

const MODES: [Mode, string][] = [
  ["hourly", "Every hour"],
  ["daily", "Every day"],
  ["weekly", "On weekdays"],
  ["monthly", "Every month"],
];

// Crontab numbers the week from Sunday; the chips start on Monday.
const DAYS: [number, string, string][] = [
  [1, "Mon", "Monday"],
  [2, "Tue", "Tuesday"],
  [3, "Wed", "Wednesday"],
  [4, "Thu", "Thursday"],
  [5, "Fri", "Friday"],
  [6, "Sat", "Saturday"],
  [0, "Sun", "Sunday"],
];

const KINDS: Record<Backup["kind"], [string, Tone]> = {
  scheduled: ["scheduled", "accent"],
  change: ["before change", "warn"],
  start: ["on start", "idle"],
  manual: ["manual", "idle"],
};

const NUMBER = /^\d{1,2}$/;
const TIME = /^(\d{1,2}):(\d{2})$/;

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function utcDay(moment: Date): string {
  const date = `${pad(moment.getUTCDate())}.${pad(moment.getUTCMonth() + 1)}`;
  return `${date}.${moment.getUTCFullYear()}`;
}

function utcTime(moment: Date): string {
  return `${pad(moment.getUTCHours())}:${pad(moment.getUTCMinutes())}`;
}

function parse(cron: string): Form {
  const custom: Form = { mode: null, minute: "0", time: "03:00", days: [1], day: "1" };
  const [minute, hour, day, month, week, ...rest] = cron.trim().split(/\s+/);
  if (rest.length || month !== "*" || !NUMBER.test(minute ?? "")) {
    return custom;
  }
  if (hour === "*" && day === "*" && week === "*") {
    return { ...custom, mode: "hourly", minute };
  }
  if (!NUMBER.test(hour ?? "")) {
    return custom;
  }
  const time = `${pad(Number(hour))}:${pad(Number(minute))}`;
  if (day === "*" && week === "*") {
    return { ...custom, mode: "daily", time };
  }
  if (day === "*" && /^[0-6](,[0-6])*$/.test(week ?? "")) {
    return { ...custom, mode: "weekly", time, days: week.split(",").map(Number) };
  }
  if (week === "*" && NUMBER.test(day ?? "") && Number(day) >= 1 && Number(day) <= 28) {
    return { ...custom, mode: "monthly", time, day };
  }
  return custom;
}

interface Rule {
  cron: string;
  minute: number;
  hour: number;
  matches: (moment: Date) => boolean;
}

function rule(form: Form): Rule | string {
  if (form.mode === "hourly") {
    const minute = Number(form.minute);
    if (!NUMBER.test(form.minute) || minute > 59) {
      return "The minute is a number from 0 to 59";
    }
    return { cron: `${minute} * * * *`, minute, hour: -1, matches: () => true };
  }
  const time = TIME.exec(form.time.trim());
  const hour = Number(time?.[1]);
  const minute = Number(time?.[2]);
  if (!time || hour > 23 || minute > 59) {
    return "The time is HH:MM, in UTC";
  }
  if (form.mode === "weekly") {
    if (!form.days.length) {
      return "Pick at least one day";
    }
    const days = [...form.days].sort();
    return {
      cron: `${minute} ${hour} * * ${days.join(",")}`,
      minute,
      hour,
      matches: (moment) => days.includes(moment.getUTCDay()),
    };
  }
  if (form.mode === "monthly") {
    const day = Number(form.day);
    if (!NUMBER.test(form.day) || day < 1 || day > 28) {
      return "The day of month is from 1 to 28";
    }
    return {
      cron: `${minute} ${hour} ${day} * *`,
      minute,
      hour,
      matches: (moment) => moment.getUTCDate() === day,
    };
  }
  return { cron: `${minute} ${hour} * * *`, minute, hour, matches: () => true };
}

function next(found: Rule, count = 3): Date[] {
  const now = Date.now();
  const runs: Date[] = [];
  const start = new Date(now);
  start.setUTCSeconds(0, 0);
  const hourly = found.hour < 0;
  for (let step = 0; runs.length < count && step < 24 * 120; step += 1) {
    const moment = new Date(start);
    if (hourly) {
      moment.setUTCHours(start.getUTCHours() + step, found.minute);
    } else {
      moment.setUTCDate(start.getUTCDate() + step);
      moment.setUTCHours(found.hour, found.minute);
    }
    if (moment.getTime() > now && found.matches(moment)) {
      runs.push(moment);
    }
  }
  return runs;
}

function listed(moments: Date[]): string {
  let shown = "";
  return moments
    .map((moment) => {
      const day = utcDay(moment);
      const text = day === shown ? utcTime(moment) : `${day}, ${utcTime(moment)}`;
      shown = day;
      return text;
    })
    .join(" \u00b7 ");
}

function joined(names: string[]): string {
  if (names.length < 2) {
    return names.join("");
  }
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function ordinal(day: number): string {
  const tails: Record<number, string> = { 1: "st", 2: "nd", 3: "rd" };
  return `${day}${(day < 11 || day > 13) && tails[day % 10] ? tails[day % 10] : "th"}`;
}

function words(form: Form, found: Rule): string {
  const at = `at ${pad(found.hour)}:${pad(found.minute)} UTC`;
  if (form.mode === "hourly") {
    return `Every hour at minute ${found.minute}`;
  }
  if (form.mode === "weekly") {
    const names = DAYS.filter(([value]) => form.days.includes(value)).map(([, , name]) => name);
    return `Every ${joined(names)} ${at}`;
  }
  if (form.mode === "monthly") {
    return `On the ${ordinal(Number(form.day))} of every month ${at}`;
  }
  return `Every day ${at}`;
}

export function Backups({ onClose }: { onClose: () => void }) {
  const [schedule, setSchedule] = useState<BackupSchedule | null>(null);
  const [form, setForm] = useState<Form>(() => parse("0 3 * * *"));
  const [enabled, setEnabled] = useState(true);
  const [keep, setKeep] = useState("30");
  const [backups, setBackups] = useState<Backup[]>([]);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [detailShown, setDetailShown] = useState(false);
  const [saveProblem, setSaveProblem] = useState<Problem | null>(null);
  const [saveDetailShown, setSaveDetailShown] = useState(false);
  const [taking, setTaking] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    Promise.all([api.backupSchedule(), api.backups()])
      .then(([found, taken]) => {
        if (live) {
          setSchedule(found);
          setForm(parse(found.cron));
          setEnabled(found.enabled);
          setKeep(String(found.keep));
          setBackups(taken);
        }
      })
      .catch((error: unknown) => {
        if (live) {
          setProblem(describe(error, "Could not load the backups"));
        }
      });
    return () => {
      live = false;
    };
  }, []);

  async function backUpNow() {
    setTaking(true);
    setProblem(null);
    try {
      await api.backUpNow();
      setBackups(await api.backups());
    } catch (error) {
      setProblem(describe(error, "Could not back up the database"));
    } finally {
      setTaking(false);
    }
  }

  const found = form.mode === null ? null : rule(form);
  const cron = found === null ? schedule?.cron : typeof found === "string" ? null : found.cron;
  const copies = Number(keep);
  const keepValid = /^\d{1,4}$/.test(keep) && copies >= 1 && copies <= 1000;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!cron || !keepValid) {
      return;
    }
    setBusy(true);
    setSaveProblem(null);
    try {
      await api.saveBackupSchedule({ cron, enabled, keep: copies });
      onClose();
    } catch (error) {
      setSaveProblem(describe(error, "Could not save the schedule"));
    } finally {
      setBusy(false);
    }
  }

  function pick(mode: Mode) {
    setForm((current) => ({ ...current, mode }));
  }

  function toggle(day: number) {
    setForm((current) => ({
      ...current,
      days: current.days.includes(day)
        ? current.days.filter((value) => value !== day)
        : [...current.days, day],
    }));
  }

  let rulePart: React.ReactNode;
  if (!enabled) {
    rulePart = (
      <>
        <span className="schedule-rule">Scheduled backups are off</span>
        <span className="schedule-next">
          Copies are still taken on every start and before an obfuscation change, a rollback or
          a profile delete
        </span>
      </>
    );
  } else if (found === null) {
    rulePart = (
      <>
        <span className="schedule-rule">Custom schedule: {schedule?.cron}</span>
        <span className="schedule-next">
          {schedule?.next_runs.length
            ? `Next: ${listed(schedule.next_runs.map((run) => new Date(run)))}`
            : "Pick a mode above to replace it"}
        </span>
      </>
    );
  } else if (typeof found === "string") {
    rulePart = <span className="schedule-rule problem">{found}</span>;
  } else {
    rulePart = (
      <>
        <span className="schedule-rule">{words(form, found)}</span>
        <span className="schedule-next">Next: {listed(next(found))}</span>
      </>
    );
  }

  const total = backups.reduce((sum, item) => sum + item.size, 0);

  return (
    <div className="scrim">
      <form className="modal backups-modal" onSubmit={(event) => void save(event)}>
        <div className="modal-header">
          <div className="modal-heading">
            <h2>Backups</h2>
            <p>Copies of panel.sqlite, kept in backups/ next to the database on the panel host</p>
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

        <label className="check">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <span>
            <span className="check-title">Back up on a schedule</span>
            <span className="check-hint">
              A copy is also taken on every start and before an obfuscation change, a rollback or
              a profile delete
            </span>
          </span>
        </label>

        <fieldset className="schedule-fields" disabled={!enabled}>
          <div className="field">
            Repeat
            <div className="segmented">
              {MODES.map(([mode, label]) => (
                <button
                  key={mode}
                  type="button"
                  className={form.mode === mode ? "active" : undefined}
                  onClick={() => pick(mode)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {form.mode === null ? null : (
            <div className="field-row">
              {form.mode === "hourly" ? (
                <div className="field-narrow">
                  <Field
                    label="At minute"
                    value={form.minute}
                    numeric
                    onChange={(minute) => setForm((current) => ({ ...current, minute }))}
                  />
                </div>
              ) : null}
              {form.mode === "weekly" ? (
                <div className="field field-auto">
                  Days
                  <div className="days">
                    {DAYS.map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        className={form.days.includes(value) ? "active" : undefined}
                        onClick={() => toggle(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {form.mode === "monthly" ? (
                <div className="field-narrow">
                  <Field
                    label="Day of month"
                    value={form.day}
                    numeric
                    hint="1 to 28, so every month has it"
                    onChange={(day) => setForm((current) => ({ ...current, day }))}
                  />
                </div>
              ) : null}
              {form.mode === "hourly" ? null : (
                <div className="field-narrow">
                  <Field
                    label="At, UTC"
                    value={form.time}
                    placeholder="03:00"
                    onChange={(time) => setForm((current) => ({ ...current, time }))}
                  />
                </div>
              )}
            </div>
          )}
        </fieldset>

        <div className="schedule-summary">{rulePart}</div>

        <div className="field-narrow">
          <Field
            label="Keep"
            value={keep}
            numeric
            onChange={setKeep}
            hint={
              keepValid
                ? "Copies of each kind: on start, scheduled, before a change. The oldest go first"
                : "From 1 to 1000 copies of each kind"
            }
          />
        </div>

        <div className="section-head">
          <div className="section-heading">
            <h3>Snapshots</h3>
            <span>
              {backups.length
                ? `${backups.length} ${backups.length === 1 ? "copy" : "copies"} \u00b7 ${bytes(total)}`
                : "none yet"}
            </span>
          </div>
          <button
            type="button"
            className="small"
            disabled={taking}
            onClick={() => void backUpNow()}
          >
            {taking ? "Backing up" : "Back up now"}
          </button>
        </div>

        <div className="diff">
          <table className="backups-table">
            <thead>
              <tr>
                <th>Kind</th>
                <th>Taken</th>
                <th>Schema</th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              {backups.length === 0 ? (
                <tr>
                  <td colSpan={4} className="backups-empty">
                    <span className="schedule-rule">No snapshots yet</span>
                    <span className="schedule-next">
                      The first one is taken on the next start, or now with Back up now
                    </span>
                  </td>
                </tr>
              ) : null}
              {backups.map((item) => {
                const [label, tone] = KINDS[item.kind];
                const moment = new Date(item.taken_at);
                return (
                  <tr key={item.name} title={item.name}>
                    <td>
                      <Pill tone={tone}>{label}</Pill>
                    </td>
                    <td>
                      {utcDay(moment)}, {utcTime(moment)}
                    </td>
                    <td>{item.revision}</td>
                    <td>{bytes(item.size)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="modal-text">
          Restoring is done on the host: stop the panel, copy a snapshot over panel.sqlite, remove
          panel.sqlite-wal and -shm, start it. Copy backups/ off the host too: it shares the
          volume with the database.
        </p>

        <Banner
          problem={saveProblem}
          shown={saveDetailShown}
          onToggle={() => setSaveDetailShown((shown) => !shown)}
        />

        <div className="modal-footer">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="action" disabled={busy || !cron || !keepValid}>
            {busy ? "Saving" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
