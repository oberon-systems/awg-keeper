# awg-keeper

A self-hosted web panel for handing out VPN access with
[AmneziaWG](https://docs.amnezia.org/) and [Xray](https://xtls.github.io/)
Reality.

You already run a VPN server. awg-keeper is what you use to give people access
to it: create a profile for a person or a device, show them a QR code, turn
the access off, reissue it, or take it away - from a browser, without editing
configs on the server by hand.

The Agent needs no root and no Linux capabilities. It expects the AmneziaWG
interfaces to be set up already, and manages their peers and obfuscation
through the interfaces' control sockets.

## Demo

[![awg-keeper demo](https://img.youtube.com/vi/_-wSG0xLLyo/maxresdefault.jpg)](https://youtu.be/_-wSG0xLLyo)

The dashboard, issuing a profile with its QR codes, turning access off, reroll
and the stats.

## Features

- Profiles with AmneziaWG, Xray or both, issued as a `.conf`, an Amnezia
  `vpn://` key or a `vless://` link, each with a QR code.
- Private keys are generated in your browser and never stored on the server.
- Turn a profile off and on, or reissue it with new keys on the same address.
- Edit a profile: its name, note, DNS, MTU and allowed IPs, and add or take
  away its AmneziaWG or Xray access. A profile whose config went stale is
  marked for a reroll.
- Change an interface's AmneziaWG 3.1 obfuscation from the Panel, with every
  value generated in the browser on request.
- Traffic and sessions per profile, and a `/stats` page where users see their
  own.
- Health of every VPN host at a glance.

## How it works

```text
  browser --https--> Panel (container) --token--> Agent (rpm/deb on the VPN host)
                                                     |
                                                     +--> AmneziaWG, Xray
```

The **Panel** is a container image with the web UI and the list of profiles.
The **Agent** is a small service on the VPN host that adds and removes peers
and Xray clients, and changes an interface's obfuscation, when the Panel asks. It does not set up the VPN itself:
interfaces, Xray inbounds and firewall rules stay yours.

## Documentation

- [Requirements](docs/01-requirements.md) - what the server needs first.
- [Installation](docs/02-installation.md) - the Agent package and the Panel container.
- [Configuration](docs/03-configuration.md) - every setting of both.
- [Usage](docs/04-usage.md) - interfaces, profiles, issued configs and stats.
- [Design](DESIGN.md) - architecture and threat model.
- [Roadmap](ROADMAP.md) - what is built and what is next.
- [Contributing](CONTRIBUTING.md) - working on the code.

## License

[MIT](LICENSE)
