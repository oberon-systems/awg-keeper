# Contributing

How to work on awg-keeper: the setup, the checks, the local stand, commits
and releases.

- [Setup](#setup)
- [Tests and checks](#tests-and-checks)
- [Development stand](#development-stand)
- [Mockups](#mockups)
- [Documentation](#documentation)
- [Commits](#commits)
- [Versions and releases](#versions-and-releases)

## Setup

You need Python 3.11 or newer, Docker and git.

```bash
make install
make
```

`make install` creates `.venv` with every tool and both components'
dependencies, and installs the git hooks. A bare `make` opens a shell with the
virtualenv active. `make help` lists all targets.

The repository holds two components, each with its own `pyproject.toml`,
tests, packaging and version:

- `agent/` - the service on the VPN host, shipped as an `rpm` and a `deb`.
- `web/` - the Panel: the API in `web/src`, the React interface in `web/ui`,
  shipped as a container image.

## Tests and checks

```bash
make test
make -C web test
make lint
```

`make test` runs both suites, `make -C agent test` or `make -C web test` one of
them, and `make lint` runs every pre-commit hook over the whole tree. The
suites need no root, VPN or containers: the agent's tests use fake `awg`,
`xray` and `ip` binaries, and the Panel's use a stub agent and a temporary
database.

The hooks run on their own:

- **pre-commit** - formatting, linters, and a check that every file but
  Markdown is plain ASCII.
- **commit-msg** - the commit message rules below.
- **pre-push** - the test suite of each component the push touches, and
  `eslint` and `tsc` for `web/ui` when `node_modules` is present.

Nothing in CI runs the tests, so the pre-push hook is the gate.

## Development stand

The whole product runs locally over a fake VPN host:

```bash
make kickstart
```

Open `http://127.0.0.1:8000` and sign in as `admin` / `admin`. Three
profiles are already there. `http://127.0.0.1:8002/stats` shows the users'
stats page as seen from inside the tunnel.

```bash
make -C dev/stack down
```

The stand keeps nothing between runs. See
[dev/stack/README.md](dev/stack/README.md) for what it runs.

## Mockups

Every screen of the Panel is drawn in Penpot first and built from the mockup.
The mockups live in `dev/web/templates`; see
[dev/web/README.md](dev/web/README.md) for the Penpot stack. Export the file
into `dev/web/templates` before you commit a changed design.

## Documentation

The user documentation is `docs/`, published as a site on GitHub Pages with
the README as its home page. The pages are listed in file name order, so a new
page gets the next number: `docs/05-<topic>.md`.

```bash
make docs
make docs-build
```

`make docs` serves the site on `http://127.0.0.1:8003` and rebuilds it on
every edit; `make docs-build` builds it into `site/` once, the way the
workflow does, and fails on a broken link.
A push to `main` that changes `docs/`, `README.md` or the site's own files
publishes it through `.github/workflows/docs.yml`; there are no versions, the
site is always the latest `main`. The site's look lives in
`docs/.theme`, drawn in the Penpot file exported to `dev/web/templates/docs`.

## Commits

Every commit is made with commitizen:

```bash
.venv/bin/cz commit
```

It asks for a type, a scope, a subject and a body, and writes
`[type][scope]: subject` with the body indented by four spaces:

```text
[feat][web]: issue amnezia keys, toggle and reroll profiles
    Name the server in a vpn:// key from a new interface label, turn the
    AmneziaWG peer of a profile off and on, and reissue its keys.
```

The rules:

- **Type** - one of these five:

  | Type       | Use it for                                          | Version |
  | ---------- | --------------------------------------------------- | ------- |
  | `feat`     | a new feature                                       | minor   |
  | `fix`      | a bug fix                                           | patch   |
  | `refactor` | a code change that neither fixes nor adds anything  | patch   |
  | `build`    | CI, packaging, tooling, mockups, version bumps      | none    |
  | `docs`     | documentation only                                  | none    |

- **Scope** - the one part the commit is about: `agent`, `web`, `tooling`,
  `design` and so on.
- **Subject** - short, lower case, in the imperative: "add", not "added".
- **Body** - one short paragraph on what changed and why.
- **One subject per commit.** Split the design, the code and the tooling of a
  change into separate commits.
- **No attribution trailers.** `Co-Authored-By`, "Generated with" and similar
  lines are rejected by the commit-msg hook.
- **Your own author.** The pre-commit hook refuses to run until this clone has
  a local identity:

```bash
git config --local user.name "Your Name"
git config --local user.email "your.email@example.com"
```

## Versions and releases

There is no version for the repository as a whole: the Agent and the Panel
are versioned and released separately. Each has its own `.cz.yaml`, and
`cz bump` run from the component's directory counts only the commits that
touched that directory.

```bash
cd agent
../.venv/bin/cz bump
```

It picks the next version from those commits' types, updates
`pyproject.toml`, `__version__`, the component's `CHANGELOG.md` and its tag in
`ROADMAP.md`, commits that as `[build][agent]: bump version X -> Y`, and tags
it `awg-keeper-agent-vY`. For the Panel, run the same from `web/`; its tags are
`awg-keeper-web-vY`. Add `--dry-run` to see the result first.

Pushing the tag publishes the release:

```bash
git push origin main awg-keeper-agent-v0.4.0
```

- **`awg-keeper-agent-v*`** - builds the `rpm` and the `deb` and attaches them
  to a GitHub release named after the tag.
- **`awg-keeper-web-v*`** - builds the Panel image and pushes it to
  `ghcr.io/oberon-systems/awg-keeper/panel` with the version and `latest`.

Both workflows can also be started by hand from the Actions tab; such a run
builds everything and publishes nothing.
