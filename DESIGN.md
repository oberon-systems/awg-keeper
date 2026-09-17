# AWG Keeper — Design

A client/server toolset for managing user profiles for AmneziaWG and Xray + Reality.

## Goals

- Manage AmneziaWG peers and Xray/Reality accounts from a single web UI.
- Never expose a management surface to the public network.
- Issue a ready-to-use client profile (`.conf` + QR, `vless://` URL) in one click.
- Ship as OS packages for the host part, as a container for the UI part.

## Non-goals (v1)

- Creating or tearing down the AWG interface, NAT/masquerade rules or sysctls —
  these are provisioned beforehand; the Agent only manages peers and Xray users.
- End-user self-service portal, billing, multi-tenancy, HA.
- IPv6 peers (the schema allows them; the UI does not expose them yet).
- TLS termination — a reverse proxy in front of the Panel does it.

## Terminology

| Term        | Meaning                                                          |
|-------------|------------------------------------------------------------------|
| **Agent**   | Host-side service. No capabilities, drives `awg` and Xray.        |
| **Panel**   | Container-side service. Web UI, database, source of truth.        |
| **Node**    | One host running an Agent. v1 supports exactly one.               |
| **Profile** | A person/device. Owns 0..1 AWG peer and 0..N Xray accounts.       |

## Tech

- Python 3.11+ (EL10 and Debian 13 both ship ≥3.12)
- FastAPI + Pydantic v2, SQLAlchemy + Alembic, SQLite (WAL)
- SPA: TypeScript + Vite, built into the Panel image and served as static files

## Architecture

```text
browser ──TLS──> reverse proxy ──> Panel (docker)
                                     │  desired state, idempotent PUT
                                     │  HTTP + bearer token
                                     ▼
                                   Agent (host, systemd)
                                     ├── awg set / awg show dump
                                     └── Xray gRPC API + config.json
```

The Panel owns desired state. The Agent is a stateless executor: every write is a
full, idempotent `PUT` of an interface's peer set (or an inbound's user set), so
recovery after any failure — agent downtime, database restored from backup — is
just a re-push. `GET /v1/state` returns actual state; a mismatch is surfaced in
the UI as drift. On the next apply the Panel wins.

## Agent

Runs on the host as a systemd unit.

**Listener.** Binds the gateway address of a dedicated docker network created for
the Panel (`docker network create --subnet …`), never `docker0` — the default
bridge is reachable by every container on the host. Deployment must also add an
nftables rule dropping the port on external interfaces. There is no other
listener.

**Authentication.** A bearer token read from `/etc/awg-keeper/agent.env` (mode
0600), compared with `hmac.compare_digest`. Never in a URL or a query string.
Rotation: write the new token, restart the Agent, update the Panel — writes fail
closed in between.

**Privileges.** A dedicated system user, not root:

```ini
User=awgkeeper
CapabilityBoundingSet=
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/etc/amnezia /var/lib/awg-keeper
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
```

**Socket access.** `awg` drives the userspace `amneziawg-go` through its UAPI
socket, `/run/amneziawg/<iface>.sock`, which the daemon creates `root 0700`.
Without access to it every call fails with `Unable to access interface:
Permission denied`. The host deployment opens the socket of each interface the
Agent manages to a group (`chgrp` and `chmod 0660` after the interface starts),
and a drop-in adds that group to `SupplementaryGroups=`. Xray is reached over
gRPC on loopback, so nothing the Agent does needs a capability.

Restarting Xray needs a narrowly scoped sudoers entry (or a polkit rule) for that
one unit — nothing broader.

**Subprocess hygiene.** `subprocess` with an argv list only, never `shell=True`.
Every value reaching a command line is validated first: public key = 44 base64
chars, interface name, CIDR, port range. This is the primary injection boundary.

**AmneziaWG.** Peers are applied incrementally with
`awg set <iface> peer <pubkey> allowed-ips <ip/32>` and `… remove`; the interface
is never recreated. `awg-quick down/up` drops every session and is not used.
After a successful apply the Agent persists the interface config file so changes
survive a reboot. Counters and handshakes come from `awg show <iface> dump`.

**Xray.** User add/remove goes through the gRPC API
(`HandlerService.AddUser/RemoveUser`), which requires an `api` inbound. A config
rewrite plus restart would drop every live connection and is reserved for
structural changes (new inbound, Reality key rotation). Note that API changes are
in-memory only: the Agent must *both* call the API and write `config.json`, or
users vanish on the next restart.

## Panel

Runs in docker (compose). FastAPI serves the JSON API and the built SPA.

**Authentication.** Session cookie (`httpOnly`, `SameSite=Strict`, `Secure`),
argon2id password hashes, CSRF token on mutating requests, rate limiting and
lockout on login. Single admin account in v1; the schema leaves room for roles.

**Storage.** SQLite in WAL mode on a mounted volume; Alembic migrations from the
first commit. Single writer, so no pooling concerns. Backup = stop-free file copy
via `sqlite3 .backup`.

### Key custody

The Panel stores **public keys only** for AWG peers. Profile issuance:

1. The SPA generates an X25519 keypair in the browser (`@noble/curves`; WebCrypto
   X25519 where available).
2. It POSTs the public key; the Panel allocates an IP and pushes the peer to the
   Agent.
3. The Panel returns a config template — everything except `PrivateKey`.
4. The SPA injects the private key locally and renders the `.conf` and the QR
   code client-side.

The private key never crosses the network and is never persisted. The UI must say
plainly that the config is downloadable **only at this moment**; afterwards the
only option is reissue.

Two asymmetries are deliberate and worth stating:

- **Xray/Reality is not like AWG.** A client identity is a UUID — a shared secret
  the server must hold in `config.json`. Public-key-only applies to AWG.
- **WireGuard PSK is also a shared secret.** If enabled, it lands in the database.
  v1 does not use it.

The Reality server private key stays on the node; clients receive only the public
key, a `shortId`, the SNI and the fingerprint.

### Data model

- `node` — id, name, endpoint, token ref, last_seen, status. One row per agent,
  added by hand.
- `interface` — node_id, name, listen_port, address CIDR, DNS, MTU, server public
  key, **obfuscation params**, peer pool CIDR.
- `profile` — name, note, enabled, created_at, expires_at.
- `awg_peer` — profile_id, interface_id, public_key, assigned_ip, allowed_ips,
  enabled.
- `xray_inbound` — node_id, tag, port, protocol, Reality settings (dest,
  serverNames, shortIds, public key, fingerprint).
- `xray_account` — profile_id, inbound_id, uuid, flow, short_id, email tag.
- `audit_log` — actor, action, target, before/after summary, timestamp.
- `peer_stat` — peer_id, rx, tx, last_handshake, sampled_at (with retention).

`node_id` is a foreign key everywhere from day one so multi-node needs no schema
migration later, even though v1 accepts a single agent.

### Obfuscation parameters

`Jc`, `Jmin`, `Jmax`, `S1`, `S2`, `H1`–`H4` (plus `I1`–`I5`/`Itime` on newer
builds) must be **identical** on both ends. They are stored per interface and
emitted into every client config. A config missing them looks correct and never
completes a handshake — this is the single most common failure.

### IP allocation

Allocated from the interface's pool, `/32` per peer on the server side; the client
config's `AllowedIPs` is a separate, per-profile setting (full or split tunnel).
Released addresses are quarantined before reuse so a stale config cannot collide
with a new profile.

## API

**Agent** (`/v1`, bearer token, internal):

| Method | Path                    | Purpose                           |
|--------|-------------------------|-----------------------------------|
| GET    | `/health`               | liveness, versions                |
| GET    | `/state`                | actual peers, users, stats        |
| PUT    | `/awg/{iface}/peers`    | full desired peer set, idempotent |
| PUT    | `/xray/{inbound}/users` | full desired user set, idempotent |

**Panel** (`/api/v1`, session cookie): `auth/*`, `profiles`, `profiles/{id}/awg`,
`profiles/{id}/xray`, `nodes`, `nodes/{id}/drift`, `audit`, `stats`.

## Threat model

| Asset               | Exposure                           | Mitigation                                    |
|---------------------|------------------------------------|-----------------------------------------------|
| Agent token         | Any container on the shared bridge | Dedicated docker network, nftables, rotation  |
| Xray UUIDs          | Stored in DB and on host           | Volume permissions, host hardening            |
| AWG private keys    | Browser only, never stored         | Public-key-only design                        |
| Reality private key | Host only                          | Never returned by any API                     |
| Admin session       | Browser                            | httpOnly/SameSite/Secure, CSRF, lockout       |

Compromise of the host is total compromise — the Agent can reconfigure the tunnel
by design. The Panel is deliberately *not* able to escalate beyond the Agent's API.

## Failure modes

- **Agent unreachable** — node marked offline; writes are rejected, not queued;
  the UI states that desired and actual state have diverged.
- **Manual edit on the host** — reported as drift; the next apply overwrites it.
- **Panel database restored from backup** — a full re-push reconciles both sides.
- **Xray restarted out of band** — API-only users would be lost; prevented by
  always writing `config.json` alongside the API call.

## Observability

Structured JSON logs on both sides, request id propagated from Panel to Agent.
Audit log for every mutation. Peer stats sampled from `awg show dump` and Xray's
`StatsService`; counters reset on restart, so deltas are accumulated rather than
stored raw.

## Packaging and deployment

- Agent: `rpm` for EL10, `deb` for Debian 13. A venv under `/opt/awg-keeper` is
  not portable across those two, so each is built in its own container
  (`quay.io/rockylinux/rockylinux:10`, `debian:13`); one `nfpm.yaml` emits both
  artifacts. Ships the systemd unit, a sysusers entry, config in
  `/etc/awg-keeper`, state in `/var/lib/awg-keeper`.
- Panel: container image; `docker compose` with the dedicated network, a volume
  for SQLite, and a reverse proxy terminating TLS.

## Testing

- Agent command layer against a fake `awg` binary on `PATH`, asserting exact argv.
- Integration tests inside a network namespace with a real interface.
- Panel API tests against a stub agent; a golden test that a generated client
  config round-trips every obfuscation parameter.

## Milestones

1. Agent: AWG peer CRUD, state, health. Packages.
2. Panel: auth, profiles, browser-side key generation, config and QR.
3. Xray/Reality accounts via gRPC API + config persistence.
4. Stats, drift detection, audit UI.
5. Multi-node (the schema is already ready).

## Open questions

- Per-peer PSK: worth the shared-secret storage, or permanently out?
- Traffic quotas and expiry — enforce by disabling the peer, or only report?
- Agent enrollment for multi-node: manual token, or a bootstrap handshake?
- Which `dest`/SNI for Reality, and who is responsible for keeping it plausible?
