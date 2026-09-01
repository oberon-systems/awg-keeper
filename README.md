# awg-keeper

A client/server toolset for managing user profiles for AmneziaWG and
Xray + Reality. It manages peers and accounts on a host that is already
provisioned; it never creates the tunnel interface, the NAT rules or the
sysctls itself.

Two parts. The **Panel** runs in a container, owns the desired state and serves
the web UI. The **Agent** runs on the host as a systemd unit, holds
`CAP_NET_ADMIN` and is a stateless executor: every write is a full, idempotent
`PUT` of an interface's peer set, so recovery after any failure is just a
re-push. AmneziaWG private keys are generated in the browser and never reach
the server.

See [DESIGN.md](DESIGN.md) for the architecture, the data model, the threat
model and the milestones.

## Development

```bash
make init   # create .venv, install the tooling, install the git hooks
make lint   # run the pre-commit hooks over every file
```

`make init` installs the `pre-commit`, `commit-msg` and `pre-push` hooks. The
`pre-commit` cache lives in `.pre-commit/` when `PRE_COMMIT_HOME` points there.

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
