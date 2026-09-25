# Requirements

What has to be set up on the server before you install awg-keeper.

awg-keeper does not build your VPN. The Agent runs without root and without
any Linux capabilities: it adds and removes peers on AmneziaWG interfaces that
already exist, changes their obfuscation, and manages clients on Xray inbounds
that are already configured. Everything on this page is yours to prepare.

- [Server](#server)
- [AmneziaWG](#amneziawg)
- [Routing and firewall](#routing-and-firewall)
- [Xray](#xray)
- [Panel access](#panel-access)
- [Client apps](#client-apps)

## Server

- EL10 or Debian 13 with systemd and `python3`.
- Docker with the compose plugin, for the Panel.
- A domain name for the Panel, and a reverse proxy with TLS.

## AmneziaWG

Install `amneziawg-tools` and `amneziawg-go`, 3.1 or newer for the AmneziaWG
3.1 obfuscation: header ranges, header protection and the timer ranges. Each
interface runs on
`amneziawg-go`, which opens a control socket,
`/run/amneziawg/<interface>.sock`, that only root may use. The Agent package
puts a socket proxy in front of it for every interface in
`AWG_KEEPER_INTERFACES`, and that is how the Agent manages the interface
without root.

Write one config per interface in `/etc/amnezia/amneziawg/` and bring it up
with `awg-quick`. The `Address` is the server's side of the tunnel: the Panel
hands out client addresses from the same network.

```ini
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
PrivateKey = <server private key>
Jc = 4
Jmin = 50
Jmax = 1000
S1 = 86
S2 = 574
H1 = 1077035230
H2 = 1147626846
H3 = 1382769431
H4 = 1517982439
```

```bash
sudo systemctl enable --now awg-quick@awg0
```

Leave the peers to the Agent. It keeps your `[Interface]` section and rewrites
the peers below it, so peers added by hand disappear. The obfuscation lines of
`[Interface]` are the one exception: once you change the obfuscation in the
Panel, the Agent writes the new values over them.

The example uses the older obfuscation. Starting with it is fine: you can move
the interface to the 3.1 set from the Panel later, see
[Change the obfuscation](04-usage.md#change-the-obfuscation).

## Routing and firewall

Clients only get anywhere if the server forwards their traffic:

```bash
echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/90-amneziawg.conf
sudo sysctl --system
```

The firewall has to let three things through. The example is for nftables,
with `awg0` as the tunnel and `eth0` as the internet side:

```text
# input: clients reach the listen port
udp dport 51820 accept

# forward: keep TCP segments small enough for the tunnel, first
iifname "awg0" tcp flags syn / syn,rst tcp option maxseg size set rt mtu
oifname "awg0" tcp flags syn / syn,rst tcp option maxseg size set rt mtu

# forward: from the tunnel out, and the replies back
iifname "awg0" oifname "eth0" accept
ct state established,related accept

# nat postrouting: clients leave with the server's address
oifname "eth0" ip saddr 10.8.0.0/24 masquerade
```

If clients should not reach each other, drop `iifname "awg0" oifname "awg0"`
in the forward chain before the other rules.

The MSS clamp matters because the tunnel MTU is smaller than the internet
side's. Without it, a large TCP answer can be dropped on its way into the
tunnel, and some sites load halfway or not at all.

## Xray

Only if you issue Xray profiles. Xray runs on the same host as the Agent,
because the Agent calls the `xray` binary.

Its `config.json` needs:

- a VLESS inbound with Reality: a unique `tag`, `serverNames`, `shortIds` and
  the private key;
- the API the Agent uses to add and remove clients, on `127.0.0.1:10085`;
- `stats` and `policy`, if you want traffic in the Panel.

```json
{
  "api": { "tag": "api", "services": ["HandlerService", "StatsService"] },
  "stats": {},
  "policy": {
    "levels": {
      "0": {
        "statsUserUplink": true,
        "statsUserDownlink": true,
        "statsUserOnline": true
      }
    }
  },
  "inbounds": [
    {
      "tag": "api",
      "listen": "127.0.0.1",
      "port": 10085,
      "protocol": "dokodemo-door",
      "settings": { "address": "127.0.0.1" }
    }
  ],
  "routing": {
    "rules": [{ "type": "field", "inboundTag": ["api"], "outboundTag": "api" }]
  }
}
```

The Agent writes new clients into `config.json` so they survive a restart of
Xray. Its service is sandboxed, so give it write access to the config
directory with a drop-in:

```bash
sudo systemctl edit awg-keeper-agent
```

```ini
[Service]
SupplementaryGroups=xray
ReadWritePaths=/usr/local/etc/xray
```

Xray must still be able to read the file the Agent writes. Make the directory
belong to a group both services share, with the setgid bit, so every new file
gets that group:

```bash
sudo chown root:xray /usr/local/etc/xray
sudo chmod 2770 /usr/local/etc/xray
```

Here `xray` is the group Xray runs with; use yours.

## Panel access

The Panel runs in Docker on its own network, `172.30.0.0/24`, and the Agent
listens on that network's gateway, `172.30.0.1:8081`. If the host firewall
filters input, allow that network to reach the port.

Users open their stats page, `/stats`, through the VPN. Their traffic to the
Panel's domain must go through the tunnel and reach the reverse proxy, and the
firewall must let it.

## Client apps

The obfuscation has to match on both ends, so a client app must understand
every value the interface uses:

- the older set (`Jc`-`Jmax`, `S1`, `S2`, single `H1`-`H4`): any AmneziaWG or
  AmneziaVPN app;
- the AmneziaWG 3.1 set (header ranges, `HeaderProtectionKey`, the timer
  ranges): [AmneziaVPN](https://amnezia.org/) 5.0.1.5 or newer, or an AmneziaWG
  app with 3.1 support.

An app too old for the interface imports the config and never completes a
handshake.
