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
