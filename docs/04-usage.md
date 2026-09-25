# Usage

What you do in the Panel once it runs, from the first interface to the users'
stats page.

- [Prepare an interface](#prepare-an-interface)
- [Create a profile](#create-a-profile)
- [Manage profiles](#manage-profiles)
- [Stats](#stats)

## Prepare an interface

Open the **Dashboard** and click your VPN host. The interfaces and Xray
inbounds it has are listed there, all disabled at first: the Panel does not
issue anything until you say where clients should connect.

Click an AmneziaWG interface, set the **Endpoint host** - the domain or IP
clients connect to - and tick **Enabled**. Address, pool, keys and
obfuscation are read from the host and cannot be changed here.

The **Label** is the server name users see in the AmneziaVPN app. Leave it
empty and they see the profile name instead.

An Xray inbound is enabled the same way, by clicking it. It needs Reality
and an endpoint host; pick the flow, the fingerprint and the short id to put
in the links.

## Create a profile

On the **Profiles** tab click **+ New profile**, give it a name, and choose
AmneziaWG, Xray or both. The keys are made in your browser.

The Panel then shows the configuration once:

- **AmneziaWG** - a `.conf` file for the AmneziaWG or AmneziaVPN app.
- **Amnezia key** - a `vpn://` key for the AmneziaVPN app, with the server
  name in it.
- **Xray** - a `vless://` link for v2rayNG, Hiddify or Streisand.

Each comes as a QR code and as text. Send it to the user before you close the
window: the Panel does not keep the private key, so it cannot show this again.

## Manage profiles

Each row of the **Profiles** tab has:

- **The toggle** - turns AmneziaWG access off and on. The profile keeps its
  address and stats. Profiles with only Xray have no toggle.
- **Stats** - traffic, sessions and where the user connected from.
- **Reroll** - makes new keys for the same profile and shows the new QR code.
  Use it when a user lost the config or it leaked; the old one stops working.
- **Delete** - removes the profile, its access and its stats.

The address of a deleted profile is not given to anyone else for seven days.

## Stats

The Panel collects traffic with every health check and keeps it for 30 days by
default.

Users can see their own stats: `https://<your domain>/stats`, opened while
their VPN is on. No sign-in is needed; the page recognises them by their
tunnel address and shows only their own profile. Opened without the VPN, it
says the connection is not recognised.
