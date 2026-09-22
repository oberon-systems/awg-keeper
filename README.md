# awg-keeper

A client/server toolset for managing user profiles for AmneziaWG and
Xray + Reality. It manages peers and accounts on a host that is already
provisioned; it never creates the tunnel interface, the NAT rules or the
sysctls itself.

Two parts. The **Panel** runs in a container, owns the desired state and serves
the web UI. The **Agent** runs on the host as a systemd unit, holds
no capabilities and keeps no state of its own: it adds, removes and reports
single peers and Xray users, and `GET /v1/state` tells the Panel what the host
actually has. AmneziaWG private keys are generated in the browser and never
reach the server.

See [DESIGN.md](DESIGN.md) for the architecture, the data model, the threat
model and the milestones, and [ROADMAP.md](ROADMAP.md) for what is built.

- [Development](#development)
- [Agent](#agent)
- [Panel](#panel)
- [Packaging](#packaging)
- [Commits](#commits)

## Development

```bash
make install   # create .venv, install the tooling, install the git hooks
make           # open a subshell with the venv activated
make lint      # run the pre-commit hooks over every file
```

`make install` installs the `pre-commit`, `commit-msg` and `pre-push` hooks,
and both components' runtime and test dependencies into the same virtualenv. A
bare `make` is `make shell`: an interactive subshell with `.venv` activated
and `PRE_COMMIT_HOME` pointed at `.pre-commit/`, so the cache stays in the
repository instead of `~/.cache/pre-commit`; `make help` lists every target.

Each component is self-contained: `agent/` and `web/` carry their own
`pyproject.toml`, their own suite, their own packaging and their own version.
Neither suite needs root, a tunnel, a node or a container: `agent/tests` puts a
fake `awg` and a fake `xray` on `PATH` and asserts the exact argv each was
handed, and `web/tests` runs against a temporary database and a stub agent.

```bash
make test              # both suites
make -C web test       # one of them
```

Nothing in CI runs the suites, so the `pre-push` hooks do: a push that touches
`agent/` or `web/` runs the matching one first and is refused if it fails. The
interface is checked there too, by `eslint` and `tsc`, and that hook stands
aside on a machine with no node installed.

## Agent

The Agent reads its configuration from the environment only, with the
`AWG_KEEPER_` prefix; `agent/packaging/agent.env.example` lists every variable.
The token is the one secret among them, which is why the systemd unit reads
them from `/etc/awg-keeper/agent.env` at mode 0600.

The Agent needs read and write access to the UAPI socket of every interface it
manages, `/run/amneziawg/<iface>.sock`. `amneziawg-go` creates it `root 0700`,
so the package reaches it through a proxy socket per interface in
`AWG_KEEPER_INTERFACES`, see [DESIGN.md](DESIGN.md#agent). It also needs write
access to `/etc/amnezia/amneziawg` to persist peers; the package grants
`awgkeeper` an ACL there through its tmpfiles entry.

Run it in the foreground against a host that already has `awg`:

```bash
export AWG_KEEPER_TOKEN=$(openssl rand -hex 24)
export AWG_KEEPER_ALLOWED_SUBNETS=127.0.0.0/8
export AWG_KEEPER_INTERFACES=awg-mgmt
make -C agent run
```

Every route but `/v1/health` needs both the token and a source address inside
`AWG_KEEPER_ALLOWED_SUBNETS`:

```bash
curl -s -H "Authorization: Bearer $AWG_KEEPER_TOKEN" \
    http://127.0.0.1:8081/v1/awg/awg-mgmt/peers
```

## Panel

The Panel is the container half: FastAPI serves the JSON API and the built
interface, SQLite on a volume holds the desired state, and alembic runs on
every start. Its settings are environment only, with the `AWG_PANEL_` prefix;
`web/.env.example` lists them and `docker compose` passes them through.

The secrets are minted by one command. It writes the `.env` block to stdout
and the generated admin password to stderr - once, because the panel keeps the
argon2id hash and nothing can give the plaintext back:

```bash
make secrets
make secrets ARGS=--ask > web/.env
```

The session key signs the session cookie, the admin password is stored only as
its hash, and the agent token is the one the Agent must be installed with.

```bash
cp web/.env.example web/.env
docker compose -f web/docker-compose.yaml up -d
```

The compose file puts the Panel on a network of its own and publishes it on
loopback: a reverse proxy in front of it terminates TLS, and the Agent binds
that network's gateway on the host rather than `docker0`. The session cookie is
`Secure`, so a plain-http run needs `AWG_PANEL_COOKIE_SECURE=false` - only ever
for local development.

### Agents

The agents are `AWG_PANEL_AGENTS`, `name=http://host:port` comma separated;
the Panel registers each one on start and logs an error when the list is empty.
Every `AWG_PANEL_PROBE_INTERVAL` seconds (30, `0` turns it off) it asks each
agent's `/v1/status` in the background and records the answer - status,
latency, versions, what `awg` shows per interface - in a healthcheck log kept
for `AWG_PANEL_CHECK_RETENTION` days. The Panel log gets a line on start and
whenever an agent changes state, not on every round.

The Status tab shows every agent, its last healthcheck and that log. An
interface the agent reports is added disabled, with its key, port and
obfuscation taken from the device; setting the server address, the client
pool and the endpoint host and enabling it is what makes it available to
profiles.

The Agent checks every interface on start and logs its port and public key, or
an error naming what is wrong; after that it logs an interface only when its
state changes. Neither half logs a token.

### Key custody

A profile's private key is generated in the browser with
[@noble/curves](https://github.com/paulmillr/noble-curves) and never sent. The
Panel is told the public half, allocates an address, pushes the peer to the
Agent and returns a config template with the private key left as a
placeholder; the interface fills it in locally and renders the `.conf` and the
QR code. That is the only moment the configuration exists, and the interface
says so - afterwards the only option is to issue the profile again.

Released addresses are quarantined for a week before they are handed out
again, so a config still sitting in someone's pocket cannot start pointing at a
different profile.

## Packaging

The Agent ships as an `rpm` for EL10 and a `deb` for Debian 13, built from one
[nfpm](https://nfpm.goreleaser.com/) description. The payload is a
[shiv](https://shiv.readthedocs.io/) zipapp rather than a venv, so the package
depends on the distribution's own `python3`. `pydantic-core` is a compiled
wheel, so each zipapp is built in a container of its target distribution:

```bash
make -C agent package
```

The artifacts land in `agent/dist/`. The version comes from the sub-project
tag - `awg-keeper-agent-v1.2.3` builds `1.2.3` - and an untagged tree builds
`0.0.0`.

The tag is written by commitizen, not by hand. `agent/.cz.yaml` gives the agent
a version of its own, so a bump moves `agent/pyproject.toml`, the `__version__`
the health endpoint reports and the sub-project tag in `ROADMAP.md`, then tags
the result:

```bash
make -C agent bump
```

The bump is the agent's alone. commitizen cannot filter commits by path, so
`agent/scripts/bump.sh` derives the increment from the commits that touched
`agent/` and hands it over: `feat` moves the minor, `fix` and `refactor` the
patch, `build` and `docs` move nothing. A commit against another sub-project
never moves the agent.

Pushing that tag is what publishes a release: `.github/workflows/agent-release.yml`
runs the test suite, builds one zipapp per distribution with a Buildx cache of
its own, packages both through the same `make` targets used here, and attaches
the `rpm` and the `deb` to a GitHub release named after the tag.

```bash
git tag awg-keeper-agent-v0.1.0
git push origin awg-keeper-agent-v0.1.0
```

A `workflow_dispatch` run builds the same artifacts and publishes nothing,
which is how a packaging change is tested without spending a version.

The Panel ships as a container image instead, built the same way and released
by its own sub-project tag. `make -C web bump` moves `web/pyproject.toml`, the
`__version__`, `web/ui/package.json` and the tag in `ROADMAP.md`; pushing the
tag makes `.github/workflows/web-release.yml` build the image and push it to
`ghcr.io` as that version and as `latest`.

```bash
make -C web image     # locally
git push origin awg-keeper-web-v0.1.0
```

Both packages create the `awgkeeper` system user, `/etc/awg-keeper`,
`/var/lib/awg-keeper` and the `awg-keeper-agent` systemd unit. On a first
install the postinstall script generates a token into
`/etc/awg-keeper/agent.env`; an upgrade never rewrites it. Read that token and
hand it to the Panel:

```bash
sudo systemctl enable --now awg-keeper-agent
sudo grep AWG_KEEPER_TOKEN /etc/awg-keeper/agent.env
```

## Commits

Commit messages are produced by commitizen with the
[wyld-cz](https://pypi.org/project/wyld-cz/) provider, giving
`[type][scope]: subject` with a four-space-indented body:

```bash
.venv/bin/cz commit
```

The known types are `fix`, `feat`, `build`, `docs` and `refactor`. The
`commit-msg` hook enforces the shape and rejects attribution trailers; the
`pre-commit` hook refuses to run at all unless this clone carries its own
author identity:

```bash
git config --local user.name "Your Name"
git config --local user.email "your.email@example.com"
```

There is no repository-wide version, so `cz bump` is not wired up.
