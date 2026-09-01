// Every call carries the session cookie, and every write echoes the CSRF token
// back out of the cookie the panel set beside it.
export interface Peer {
  public_key: string;
  assigned_ip: string;
  allowed_ips: string;
  interface_id: number;
  enabled: boolean;
}

export interface Profile {
  id: number;
  name: string;
  note: string | null;
  enabled: boolean;
  created_at: string;
  peer: Peer | null;
}

export interface Issued {
  profile: Profile;
  config_template: string;
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
  profiles: () => call<Profile[]>("GET", "/profiles"),
  createProfile: (name: string, note: string, interfaceId: number, key: string) =>
    call<Issued>("POST", "/profiles", {
      name,
      note: note || null,
      interface_id: interfaceId,
      public_key: key,
    }),
  deleteProfile: (id: number) => call<void>("DELETE", `/profiles/${id}`),
};
