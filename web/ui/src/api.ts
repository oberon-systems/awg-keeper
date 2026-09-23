// Every call carries the session cookie, and every write echoes the CSRF token
// back out of the cookie the panel set beside it.
export interface Peer {
  public_key: string;
  assigned_ip: string;
  allowed_ips: string;
  interface_id: number;
  interface: string;
  enabled: boolean;
}

export interface XrayClient {
  inbound_id: number;
  inbound: string;
  email: string;
  flow: string | null;
  enabled: boolean;
}

export interface Profile {
  id: number;
  name: string;
  note: string | null;
  enabled: boolean;
  created_at: string;
  node: string | null;
  peer: Peer | null;
  xray: XrayClient | null;
}

export interface Issued {
  profile: Profile;
  config_template: string | null;
  link: string | null;
}

export interface ProfileCreate {
  name: string;
  note: string | null;
  awg?: { interface_id: number; public_key: string };
  xray?: { inbound_id: number; id: string };
}

export interface Inbound {
  id: number;
  node_id: number;
  tag: string;
  port: number;
  network: string;
  security: string;
  endpoint_host: string;
}

export type Period = "24h" | "7d" | "30d";

export interface ProfileStats {
  period: Period;
  online: boolean;
  last_seen_at: string | null;
  last_source: string | null;
  rx: number;
  tx: number;
  connected_seconds: number;
  session_count: number;
  buckets: { start: string; rx: number; tx: number }[];
  protocols: {
    protocol: string;
    key: string;
    rx: number;
    tx: number;
    last_seen_at: string | null;
  }[];
  sessions: {
    started_at: string;
    ended_at: string | null;
    protocol: string;
    source: string | null;
    traffic: number;
  }[];
}

export interface Interface {
  id: number;
  node_id: number;
  name: string;
  address: string;
  pool: string;
  listen_port: number;
  endpoint_host: string;
  client_allowed_ips: string;
  obfuscation: Record<string, unknown>;
}

export interface Node {
  id: number;
  name: string;
  endpoint: string;
  status: string;
  last_seen: string | null;
}

export interface AgentInterface {
  id: number | null;
  name: string;
  present: boolean;
  peers: number;
  public_key: string | null;
  listen_port: number;
  error: string | null;
  enabled: boolean;
  address: string | null;
  pool: string | null;
  endpoint_host: string | null;
  dns: string | null;
  mtu: number | null;
  client_allowed_ips: string | null;
  keepalive: number | null;
  obfuscation: Record<string, unknown>;
  addresses: string[];
  missing: string[];
}

export interface AgentInbound {
  id: number | null;
  tag: string;
  present: boolean;
  clients: number;
  protocol: string;
  port: number;
  network: string;
  security: string;
  server_names: string[];
  short_ids: string[];
  public_key: string | null;
  enabled: boolean;
  endpoint_host: string | null;
  flow: string | null;
  fingerprint: string | null;
  short_id: string | null;
  label: string | null;
  missing: string[];
}

export interface Agent extends Node {
  configured: boolean;
  checked_at: string | null;
  latency_ms: number | null;
  version: string | null;
  awg: string | null;
  xray: string | null;
  interfaces: AgentInterface[];
  inbounds: AgentInbound[];
  error: string | null;
}

export interface Check {
  id: number;
  checked_at: string;
  status: string;
  latency_ms: number | null;
  error: string | null;
  version: string | null;
  awg: string | null;
  xray: string | null;
  interfaces: ReportedInterface[];
}

// An interface exactly as the agent reported it in one healthcheck.
export interface ReportedInterface {
  name: string;
  present: boolean;
  peers?: number;
  error?: string | null;
}

export interface InterfaceUpdate {
  enabled?: boolean;
  address?: string | null;
  pool?: string | null;
  endpoint_host?: string | null;
  dns?: string | null;
  mtu?: number | null;
  client_allowed_ips?: string | null;
  keepalive?: number | null;
}

export interface InboundUpdate {
  enabled?: boolean;
  endpoint_host?: string | null;
  flow?: string | null;
  fingerprint?: string | null;
  short_id?: string | null;
  label?: string | null;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

function csrfToken(): string {
  const entry = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("awg_csrf="));
  return entry ? decodeURIComponent(entry.slice("awg_csrf=".length)) : "";
}

async function call<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET") {
    headers["X-CSRF-Token"] = csrfToken();
  }

  const answer = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!answer.ok) {
    let detail = answer.statusText;
    try {
      const problem = (await answer.json()) as { detail?: string };
      detail = problem.detail ?? detail;
    } catch {
      // A proxy error page is not json, and the status is enough.
    }
    throw new ApiError(answer.status, detail);
  }

  if (answer.status === 204) {
    return undefined as T;
  }
  return (await answer.json()) as T;
}

export const api = {
  login: (user: string, password: string) =>
    call<{ user: string }>("POST", "/auth/login", { user, password }),
  logout: () => call<void>("POST", "/auth/logout"),
  me: () => call<{ user: string }>("GET", "/auth/me"),
  interfaces: () => call<Interface[]>("GET", "/interfaces"),
  nodes: () => call<Node[]>("GET", "/nodes"),
  agents: () => call<Agent[]>("GET", "/agents"),
  probe: () => call<Agent[]>("POST", "/agents/probe"),
  checks: (nodeId: number, limit = 100) =>
    call<Check[]>("GET", `/agents/${nodeId}/checks?limit=${limit}`),
  updateInterface: (id: number, body: InterfaceUpdate) =>
    call<Agent>("PATCH", `/interfaces/${id}`, body),
  updateInbound: (id: number, body: InboundUpdate) =>
    call<Agent>("PATCH", `/inbounds/${id}`, body),
  profiles: () => call<Profile[]>("GET", "/profiles"),
  inbounds: () => call<Inbound[]>("GET", "/inbounds"),
  createProfile: (body: ProfileCreate) => call<Issued>("POST", "/profiles", body),
  profileStats: (id: number, period: Period) =>
    call<ProfileStats>("GET", `/profiles/${id}/stats?period=${period}`),
  deleteProfile: (id: number) => call<void>("DELETE", `/profiles/${id}`),
};
