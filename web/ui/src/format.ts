import type { ReportedInterface } from "./api";

export function when(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "never";
}

export function age(value: string | null, now: number): string {
  if (!value) {
    return "";
  }
  const seconds = Math.max(0, Math.round((now - new Date(value).getTime()) / 1000));
  if (seconds < 120) {
    return `${seconds}s ago`;
  }
  if (seconds < 7200) {
    return `${Math.round(seconds / 60)}m ago`;
  }
  return `${Math.round(seconds / 3600)}h ago`;
}

export function ms(value: number | null): string {
  return value === null ? "-" : `${Math.round(value)} ms`;
}

export function summary(items: ReportedInterface[]): string {
  return items
    .map((item) => {
      if (item.error) {
        return `${item.name}: ${item.error}`;
      }
      return item.present ? `${item.name}: ${item.peers ?? 0} peers` : `${item.name}: absent`;
    })
    .join("; ");
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

// The mockups write dates day first with dots, whatever the browser locale.
export function day(value: string, year = true): string {
  const moment = new Date(value);
  const date = `${pad(moment.getDate())}.${pad(moment.getMonth() + 1)}`;
  return year ? `${date}.${moment.getFullYear()}` : date;
}

export function stamp(value: string, year = false): string {
  const moment = new Date(value);
  return `${day(value, year)}, ${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
}

export function bytes(value: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const shown = unit === 0 || size >= 100 ? Math.round(size) : Math.round(size * 10) / 10;
  return `${shown} ${units[unit]}`;
}

export function duration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours) {
    return `${hours} h ${minutes} m`;
  }
  return minutes ? `${minutes} m` : `${seconds}s`;
}

export function shortKey(key: string): string {
  return key.length > 16 ? `${key.slice(0, 8)}\u2026${key.slice(-7)}` : key;
}
