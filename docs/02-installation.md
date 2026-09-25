# Installation

This guide sets up the Agent on your VPN host and the Panel next to it. Do the
steps in order: the Agent package creates the token the Panel needs, and the
Agent listens on the Panel's network, which appears once the Panel runs.

- [Before you start](#before-you-start)
- [1. Install the Agent package](#1-install-the-agent-package)
- [2. Start the Panel](#2-start-the-panel)
- [3. Start the Agent](#3-start-the-agent)
- [4. Put a reverse proxy in front](#4-put-a-reverse-proxy-in-front)
- [Upgrade](#upgrade)

## Before you start

Prepare the server as described in [Requirements](01-requirements.md): the
AmneziaWG interfaces up, forwarding and the firewall in place, and Xray
configured if you use it.

## 1. Install the Agent package

Download the `rpm` or the `deb` from the
[releases page](https://github.com/oberon-systems/awg-keeper/releases) and
install it. Do not start it yet.

On EL10:

```bash
sudo dnf install ./awg-keeper-agent-*.rpm
```

On Debian 13:

```bash
sudo apt install ./awg-keeper-agent_*.deb
```

The package generated a token. You will need it in the next step:

```bash
sudo grep AWG_KEEPER_TOKEN /etc/awg-keeper/agent.env
```

## 2. Start the Panel

Make a directory for the Panel and put a `docker-compose.yaml` in it:

```yaml
services:
  panel:
    image: ghcr.io/oberon-systems/awg-keeper/panel:latest
    restart: unless-stopped
    env_file: .env
    volumes:
      - panel-data:/var/lib/awg-keeper
    networks:
      - panel
    ports:
      - "127.0.0.1:8000:8000"

networks:
  panel:
    ipam:
      config:
        - subnet: 172.30.0.0/24

volumes:
  panel-data:
```

Make a session key:

```bash
openssl rand -hex 32
```

Choose the admin password and hash it with the Panel image. It asks for the
password without showing it:

```bash
docker run --rm -it --entrypoint python ghcr.io/oberon-systems/awg-keeper/panel:latest -c "import argon2, getpass; print(argon2.PasswordHasher().hash(getpass.getpass()))"
```

Put both into a `.env` next to `docker-compose.yaml`, with the Agent's token:

```text
AWG_PANEL_SECRET_KEY=<session key>
AWG_PANEL_ADMIN_USER=admin
AWG_PANEL_ADMIN_PASSWORD_HASH='<password hash>'
AWG_PANEL_AGENT_TOKEN=<token from step 1>
AWG_PANEL_AGENTS=vpn-1=http://172.30.0.1:8081
FORWARDED_ALLOW_IPS=172.30.0.1
```

Keep the single quotes around the hash. Without them compose treats every `$`
in it as a variable, and the password stops working.

Start the Panel:

```bash
docker compose up -d
```

## 3. Start the Agent

Edit `/etc/awg-keeper/agent.env` so the Agent listens only on the Panel's
network, and list the interfaces it should manage:

```text
AWG_KEEPER_BIND=172.30.0.1
AWG_KEEPER_ALLOWED_SUBNETS=172.30.0.0/24
AWG_KEEPER_INTERFACES=awg0
```

Then start it:

```bash
sudo systemctl enable --now awg-keeper-agent
```

Do not bind the Agent to `0.0.0.0` or to `docker0`: other containers on the
host could reach it there.

## 4. Put a reverse proxy in front

Proxy your domain to `http://127.0.0.1:8000` and pass the client address in
`X-Forwarded-For`. The users' `/stats` page tells people apart by that address.

Open the domain, sign in as `admin`, and continue with [Usage](04-usage.md).

## Upgrade

The Panel updates its database by itself on start:

```bash
docker compose pull
docker compose up -d
```

For the Agent, install the new package the same way as in step 1. Your
`agent.env` and its token are kept, and a running Agent restarts.
