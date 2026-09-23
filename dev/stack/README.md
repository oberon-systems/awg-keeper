# Development stand

The whole product on one machine: the panel, one agent, and a fake host for
the agent to manage. It exists so a change can be seen working end to end -
sign in, discover an interface, issue a profile - without a server, a tunnel
or root.

One command brings it up, and it keeps no state. There is no volume, no
generated settings file and nothing written outside the containers, so
`make down` leaves the machine as it was.

- [Kickstart](#kickstart)
- [Commands](#commands)
- [What is running](#what-is-running)
- [The fake host](#the-fake-host)
- [Working against the stand](#working-against-the-stand)
- [What this is not](#what-this-is-not)

## Kickstart

Docker is the only thing it needs:

```bash
make kickstart
```

It builds both images from the tree, brings compose up, waits for the panel
and the agent to answer, and prints where to go. Anything that fails after
compose is up takes the stand back down rather than leaving half of it
running.

```text
panel http://127.0.0.1:8000     admin / admin
agent http://127.0.0.1:8081/v1/health
```

The panel is published on port 8000. When that port is taken on the host,
pick another one: `make kickstart LISTEN_PORT=8090`, or export `LISTEN_PORT`
before running it.

Both interfaces come up disabled. That is the real behaviour: the panel
discovers an interface from the agent but refuses to issue against one that
has no endpoint host, so fill that in and enable it before creating a
profile.

## Commands

| Target                      | What it does                                  |
| --------------------------- | --------------------------------------------- |
| `make kickstart`            | Build, start, wait, report                     |
| `make -C dev/stack down`    | Stop it; nothing is left behind                |
| `make -C dev/stack restart` | Restart both, picking up edited python sources |
| `make -C dev/stack logs`    | Follow both services                           |
| `make -C dev/stack calls`   | Show every `awg` and `xray` command so far     |

`make kickstart` at the repository root is the same as
`make -C dev/stack kickstart`. The Makefile here is a delegator: the work is
in `kickstart.sh`, which is where to go to change what the stand does.

There is no `clean`. `down` is the whole of it.

## What is running

Two containers on a network of their own, `172.31.0.0/24`:

```text
  127.0.0.1:8000 -> panel ---- http ----> agent -> /host/bin/awg
  127.0.0.1:8081 --------------------^            /host/bin/xray
                                                  /host/bin/ip
```

The panel is built from `web/`, the same image a deployment runs. The agent
is built from `dev/stack/Dockerfile.agent` over the repository root and
exists only here: a real agent is installed from the rpm or the deb in
`agent/packaging` and runs on the host it tunnels for.

Every setting is in `stand.env`, committed and fixed. The compose file reads
it with `format: raw`, which matters: compose interpolates an env file by
default, and the argon2id password hash in there is full of dollar signs it
would otherwise read as variables. Nothing else in the compose file is
interpolated, so there is no `.env` beside it either.

The panel's database is inside its container rather than on a volume, so
every run starts on an empty schema that `alembic upgrade head` builds at
boot.

## The fake host

`bin/fakehost.py` runs at image build time and lays `/host` out inside the
agent container:

```text
/host/bin/awg               stand-ins, taken from the agent's own tests
/host/bin/xray
/host/bin/ip
/host/awg-state.json        the interfaces, their keys, ports and peers
/host/etc/xray/config.json  the inbounds
/host/etc/amneziawg/        where the agent persists interface configs
/host/awg.log               every argv the stand-ins were called with
/host/xray.log
```

The stand-ins are not written there by hand. They are lifted out of
`agent/tests/conftest.py`, where the same fakes already exist for the unit
tests, so the stand and the suite cannot drift into disagreeing about what
the host answers.

Two interfaces are seeded, `awg0` on `10.8.0.1/24` and `awg1` on
`10.9.0.1/24`, plus one Reality inbound tagged `reality-443`. A write through
the panel reaches the state file, so a peer added in the browser is visible
afterwards:

```bash
make -C dev/stack calls
```

A restart keeps what the fake host recorded; a `down` throws it away along
with everything else.

## Working against the stand

The panel's python sources and the agent's are mounted in read-only, so a
change to either is picked up by a restart:

```bash
make -C dev/stack restart
```

The browser interface is different. It is built by `npm` inside the panel
image, so a change under `web/ui` needs the image rebuilt, which is what
`make kickstart` does every time it runs.

Both APIs serve their own documentation on the stand, which a deployment does
not:

```bash
xdg-open http://127.0.0.1:8000/api/v1/docs
xdg-open http://127.0.0.1:8081/docs
```

## What this is not

The stand is not a deployment and nothing in `stand.env` may be copied into
one. The password is `admin`, the session key and the agent token are rows of
zeroes and ones published in this repository,
`AWG_PANEL_COOKIE_SECURE=false` because the stand is plain http on loopback,
and `AWG_KEEPER_ALLOWED_SUBNETS` spans the private docker ranges. A
deployment mints its own secrets with `make secrets`, terminates TLS in front
of the panel, and names the one bridge the panel is on.

For the shape that deploys, read `web/docker-compose.yaml` and
`agent/packaging`.
