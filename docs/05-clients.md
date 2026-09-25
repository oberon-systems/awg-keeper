# Phone setup

How a user puts an issued profile on an Android phone or an iPhone, and how to
tell that it works.

The admin creates the profile in the Panel and sends the user what it showed
once: a QR code or text for AmneziaWG, the Amnezia key, or the Xray link.
Everything below happens on the phone.

- [Pick an app](#pick-an-app)
- [AmneziaWG with AmneziaVPN](#amneziawg-with-amneziavpn)
- [Xray on Android](#xray-on-android)
- [Xray on iPhone](#xray-on-iphone)
- [Check that it works](#check-that-it-works)
- [When it does not connect](#when-it-does-not-connect)

## Pick an app

| What the profile has | Android | iPhone |
| -------------------- | ------- | ------ |
| AmneziaWG, `vpn://` key or `.conf` | AmneziaVPN | AmneziaVPN |
| Xray, `vless://` link | v2rayNG or Hiddify | v2RayTun, Streisand or Hiddify |

Start with AmneziaWG where the profile has it: it is the faster of the two.
Keep Xray as the fallback for networks that block AmneziaWG. Mobile networks
do this more often than Wi-Fi.

A profile with both can be installed in both apps. Only one VPN runs on a phone
at a time, so switch between them rather than running both.

## AmneziaWG with AmneziaVPN

The interface may use the AmneziaWG 3.1 obfuscation. Only
[AmneziaVPN](https://amnezia.org/) 5.0.1.5 or newer understands it: an older
app imports the profile and never connects.

1. Install AmneziaVPN from Google Play or the App Store, or update it.
2. Open it and tap **+** (on first start: **Let's get started**).
3. Choose how the profile came:
   - a QR code: tap **Scan QR code** and point the camera at it;
   - an Amnezia key (`vpn://...`): copy it, tap **Insert key** and paste it;
   - a `.conf` file: tap **Open config file** and pick it.
4. Tap **Continue**, then **Connect**. Allow the VPN request the phone shows.

The Amnezia key carries the server name, so the server shows up under that
name. A `.conf` shows up as "Server 1" or similar; rename it in its settings.

## Xray on Android

Use [v2rayNG](https://github.com/2dust/v2rayNG) or
[Hiddify](https://github.com/hiddify/hiddify-app).

In v2rayNG:

1. Install it from Google Play, or take the APK from its GitHub releases.
2. Copy the `vless://` link, open v2rayNG, tap **+** and **Import config from
   Clipboard**. For a QR code, tap **+** and **Import config from QRcode**.
3. Tap the new entry to select it, then the round **V** button at the bottom.
   Allow the VPN request.

In Hiddify, tap **+** or **New profile**, then **Add from clipboard** or **Scan
QR code**, and tap the big connect button.

## Xray on iPhone

Use [v2RayTun](https://apps.apple.com/app/v2raytun/id6476628951),
[Streisand](https://apps.apple.com/app/streisand/id6450534064) or Hiddify from
the App Store. The steps are the same in each:

1. Copy the `vless://` link, or have the QR code ready.
2. Open the app and tap **+**, then **Import from clipboard** or **Scan QR
   code**.
3. Select the new entry and turn the connection on. Allow the VPN
   configuration when iOS asks.

## Check that it works

With the VPN on, open in the phone's browser:

```text
https://<panel domain>/stats
```

The page shows the profile's name, its traffic and its sessions. "Connection
not recognised" means the traffic does not go through the tunnel: the VPN is
off, or it connected to a different server.

## When it does not connect

- **AmneziaVPN connects but no traffic passes.** The app is older than
  5.0.1.5, or the admin changed the interface's obfuscation since the profile
  was issued. Update the app; if it still fails, ask the admin to reroll the
  profile and import the new config.
- **Works on Wi-Fi, not on mobile data.** The mobile network blocks AmneziaWG.
  Use the Xray link on that network.
- **Sites do not open while the VPN is on (Android).** A Private DNS server
  set by hand bypasses the tunnel's resolver. Set **Settings > Network &
  internet > Private DNS** to **Automatic** or **Off**.
- **The Xray app says the link is invalid.** The link was cut while copying.
  Copy it again in full, or use the QR code.
- **A config was lost or leaked.** Ask the admin to reroll the profile: the old
  config stops working and a new one is issued for the same profile.
