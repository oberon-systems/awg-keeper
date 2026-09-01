# awg-keeper

A client/server toolset for managing user profiles for AmneziaWG and
Xray + Reality. It manages peers and accounts on a host that is already
provisioned; it never creates the tunnel interface, the NAT rules or the
sysctls itself.

Two parts. The **Panel** runs in a container, owns the desired state and serves
the web UI. The **Agent** runs on the host as a systemd unit, holds
`CAP_NET_ADMIN` and keeps no state of its own: it adds, removes and reports
single peers and Xray users, and `GET /v1/state` tells the Panel what the host
actually has. AmneziaWG private keys are generated in the browser and never
reach the server.

See [DESIGN.md](DESIGN.md) for the architecture, the data model, the threat
model and the milestones, and [ROADMAP.md](ROADMAP.md) for what is built.

- [Development](#development)
- [Agent](#agent)
- [Packaging](#packaging)
- [Commits](#commits)

## Development

```bash
make init   # create .venv, install the tooling, install the git hooks
make lint   # run the pre-commit hooks over every file
```

`make init` installs the `pre-commit`, `commit-msg` and `pre-push` hooks, and
the agent's runtime and test dependencies into the same virtualenv. The
`pre-commit` cache lives in `.pre-commit/` when `PRE_COMMIT_HOME` points there.

The Agent lives in `agent/` and is self-contained: its own `pyproject.toml`,
its own test suite, its own packaging. The suite needs neither root nor a real
tunnel - `agent/tests/conftest.py` puts a fake `awg` and a fake `xray` on
`PATH` and asserts the exact argv each was handed.

```bash
make test
```

Nothing in CI runs the suite, so the `pre-push` hook does: a push that touches
`agent/` runs it first and is refused if it fails. `make init` installs that
hook along with the others.

## Agent

The Agent reads its configuration from the environment only, with the
`AWG_KEEPER_` prefix; `agent/packaging/agent.env.example` lists every variable.
The token is the one secret among them, which is why the systemd unit reads
them from `/etc/awg-keeper/agent.env` at mode 0600.

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
