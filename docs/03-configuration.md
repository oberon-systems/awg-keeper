# Configuration

Both parts are configured with environment variables. This page lists all of
them.

- [Agent](#agent)
- [Panel](#panel)
- [Xray traffic](#xray-traffic)

## Agent

The Agent reads `/etc/awg-keeper/agent.env`. Restart it after a change:

```bash
sudo systemctl restart awg-keeper-agent
```

| Variable                     | Default                           | What it is                                |
| ---------------------------- | --------------------------------- | ----------------------------------------- |
| `AWG_KEEPER_TOKEN`           | generated on install              | The secret the Panel signs in with        |
| `AWG_KEEPER_BIND`            | `127.0.0.1`                       | Address to listen on                      |
| `AWG_KEEPER_PORT`            | `8081`                            | Port to listen on                         |
| `AWG_KEEPER_ALLOWED_SUBNETS` | loopback only                     | Who may call the Agent                    |
| `AWG_KEEPER_INTERFACES`      | every AmneziaWG interface         | Interfaces to manage, comma separated     |
| `AWG_KEEPER_AWG_CONF_DIR`    | `/etc/amnezia/amneziawg`          | Where peers are saved for `awg-quick`     |
| `AWG_KEEPER_XRAY_API`        | `127.0.0.1:10085`                 | Address of the Xray API                   |
| `AWG_KEEPER_XRAY_CONFIG`     | `/usr/local/etc/xray/config.json` | Xray config where clients are saved       |
| `AWG_KEEPER_LOG_LEVEL`       | `INFO`                            | Log level                                 |
| `AWG_KEEPER_DOCS`            | `false`                           | Serve the API docs                        |

## Panel

The Panel reads the `.env` next to its `docker-compose.yaml`. Apply a change
with:

```bash
docker compose up -d
```

| Variable                        | Default     | What it is                                         |
| ------------------------------- | ----------- | -------------------------------------------------- |
| `AWG_PANEL_SECRET_KEY`          | required    | Session key, at least 32 characters                |
| `AWG_PANEL_ADMIN_USER`          | `admin`     | Admin login                                        |
| `AWG_PANEL_ADMIN_PASSWORD_HASH` | required    | argon2id hash of the admin password, in quotes     |
| `AWG_PANEL_AGENTS`              | empty       | Agents as `name=http://host:port`, comma separated |
| `AWG_PANEL_AGENT_TOKEN`         | empty       | The Agents' `AWG_KEEPER_TOKEN`                     |
| `AWG_PANEL_PROBE_INTERVAL`      | `30`        | Seconds between health checks, `0` for none        |
| `AWG_PANEL_CHECK_RETENTION`     | `7`         | Days of health checks to keep                      |
| `AWG_PANEL_STATS_RETENTION`     | `30`        | Days of traffic and sessions to keep               |
| `AWG_PANEL_ALLOWED_SUBNETS`     | everyone    | Who may open the panel, comma separated            |
| `AWG_PANEL_SESSION_TTL`         | `43200`     | Seconds a sign-in lasts                            |
| `AWG_PANEL_LOGIN_ATTEMPTS`      | `5`         | Wrong passwords before a lockout                   |
| `AWG_PANEL_LOCKOUT_SECONDS`     | `300`       | How long a lockout lasts                           |
| `AWG_PANEL_COOKIE_SECURE`       | `true`      | Set `false` only to test over plain http           |
| `AWG_PANEL_LOG_LEVEL`           | `INFO`      | Log level                                          |
| `AWG_PANEL_DOCS`                | `false`     | Serve the API docs at `/docs`                      |
| `FORWARDED_ALLOW_IPS`           | `127.0.0.1` | Proxies trusted to pass the client address         |

`AWG_PANEL_ALLOWED_SUBNETS` does not apply to `/stats`: users open that page
through the VPN, from their tunnel address.

## Xray traffic

The Panel shows Xray traffic only when Xray counts it. Add this to your Xray
config and restart Xray:

```json
{
  "stats": {},
  "policy": {
    "levels": {
      "0": {
        "statsUserUplink": true,
        "statsUserDownlink": true,
        "statsUserOnline": true
      }
    }
  }
}
```

Without it Xray profiles still work; they just show no traffic.
