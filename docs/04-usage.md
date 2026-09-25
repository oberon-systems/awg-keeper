# Usage

What you do in the Panel once it runs, from the first interface to the users'
stats page.

- [Prepare an interface](#prepare-an-interface)
- [Change the obfuscation](#change-the-obfuscation)
- [Create a profile](#create-a-profile)
- [Manage profiles](#manage-profiles)
- [Edit a profile](#edit-a-profile)
- [Stats](#stats)

## Prepare an interface

Open the **Dashboard** and click your VPN host. The interfaces and Xray
inbounds it has are listed there, all disabled at first: the Panel does not
issue anything until you say where clients should connect.

Click an AmneziaWG interface, set the **Endpoint host** - the domain or IP
clients connect to - and tick **Enabled**. Address, pool, port and keys are
read from the host and cannot be changed here. The obfuscation has a dialog
of its own, behind **Edit** in the **Obfuscation** row.

The **Label** is the server name users see in the AmneziaVPN app. Leave it
empty and they see the profile name instead.

An Xray inbound is enabled the same way, by clicking it. It needs Reality
and an endpoint host; pick the flow, the fingerprint and the short id to put
in the links.

## Change the obfuscation

The obfuscation is what makes AmneziaWG traffic look like something other
than WireGuard. Change it when a network starts blocking the tunnel, or to
move an interface to the AmneziaWG 3.1 set.

1. On the **Dashboard**, click the host, then the interface.
2. In the **Obfuscation** row, click **Edit**.
3. Click **Generate all** for a fresh set, or type the values. **Generate**
   next to **HeaderProtectionKey** makes a new key only.
4. Click **Save** and confirm.

The Agent applies the values to the running interface at once, without
dropping it, and writes them into the interface's config file. A value can be
changed but not removed.

Every profile issued on the interface stops connecting until it is rerolled:
its config still carries the old values. The **Profiles** tab marks each of
them with **reroll**. Check that the users' apps are new enough first, see
[Client apps](01-requirements.md#client-apps).

To test that it worked, run on the VPN host:

```bash
sudo awg show awg0
```

The output lists the new values, with the header protection key hidden.

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
- **reroll** - a badge next to the status: the profile's config no longer
  matches what the Panel would issue now, after a change to the profile, the
  interface or its obfuscation. Reroll the profile and send the user the new
  config.
- **Edit** - see [Edit a profile](#edit-a-profile).
- **Stats** - traffic, sessions and where the user connected from.
- **Reroll** - makes new keys for the same profile and shows the new QR code.
  Use it when a user lost the config or it leaked; the old one stops working.
- **Delete** - removes the profile, its access and its stats.

The address of a deleted profile is not given to anyone else for seven days.

## Edit a profile

Click **Edit** in the profile's row. What you change reaches the user at
different times:

- **Name** and **Note** are saved at once. Renaming a profile with Xray renames
  its Xray client too; the link keeps working.
- **DNS**, **MTU** and **Allowed IPs** override the interface's values for this
  profile. Leave a field empty to use the interface's value, shown in grey.
  They reach the device only with the next config, so the profile is marked
  **reroll**.
- **Access** - tick AmneziaWG or Xray to add it; the Panel then shows the new
  config or link once, as for a new profile. Untick one to take it away. A
  profile keeps at least one of the two.

A profile stays on the agent it was created on, and its AmneziaWG address and
Xray inbound do not change. To move either, take the access away and add it
again.

## Stats

The Panel collects traffic with every health check and keeps it for 30 days by
default.

Users can see their own stats: `https://<your domain>/stats`, opened while
their VPN is on. No sign-in is needed; the page recognises them by their
tunnel address and shows only their own profile. Opened without the VPN, it
says the connection is not recognised.
